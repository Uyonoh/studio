"""Replicate provider adapter using the Replicate HTTP predictions API."""

import base64
import hashlib
import hmac
import json
import logging
import time
from collections.abc import Mapping
from typing import Any

import httpx

from studio_core.models import AssetKind
from studio_providers.base import (
    PermanentProviderError,
    ProviderError,
    ProviderJobRef,
    ProviderJobState,
    ProviderOutput,
    ProviderRequest,
    ProviderStatus,
    RateLimitedError,
    TransientProviderError,
    WebhookEvent,
)

logger = logging.getLogger(__name__)

# Replicate status → internal state mapping
_STATUS_MAP: dict[str, ProviderJobState] = {
    "starting": ProviderJobState.PENDING,
    "processing": ProviderJobState.RUNNING,
    "succeeded": ProviderJobState.SUCCEEDED,
    "failed": ProviderJobState.FAILED,
    "canceled": ProviderJobState.CANCELED,
}

# Replay protection: reject webhook timestamps older than this (seconds)
_WEBHOOK_TOLERANCE_SECONDS = 300

# Replicate models do not share a single input schema. These maps keep the
# model-specific input names in one place instead of leaking them into the
# catalog or the worker. A model missing from these maps falls back to the
# generic ``image`` slot, which is what Topaz, CodeFormer, and FLUX.1 dev use.
# Single-image slot: only the first source image is sent under this key.
_IMAGE_INPUT_KEY: dict[str, str] = {
    "black-forest-labs/flux-kontext-pro": "input_image",
    "black-forest-labs/flux-kontext-max": "input_image",
    "black-forest-labs/flux-1.1-pro": "image_prompt",
    "xlabs-ai/flux-dev-controlnet": "control_image",
    "tencentarc/gfpgan": "img",
}
# List-style image slots: every source image is sent as a list under this key.
_IMAGE_LIST_INPUT_KEY: dict[str, str] = {
    "black-forest-labs/flux-2-pro": "input_images",
    "black-forest-labs/flux-2-max": "input_images",
    "google/nano-banana": "image_input",
    "google/nano-banana-pro": "image_input",
    "openai/gpt-image-2": "input_images",
    "bytedance/seedream-4.5": "image_input",
    "bytedance/seedream-4": "image_input",
}
_FIRST_FRAME_INPUT_KEY: dict[str, str] = {
    "minimax/video-01": "first_frame_image",
    "minimax/hailuo-2.3": "first_frame_image",
    "bytedance/seedance-2.5": "image",
    "bytedance/seedance-2.0": "image",
    "bytedance/seedance-1-pro": "image",
    "google/veo-3.1": "image",
    "google/veo-3.1-fast": "image",
    "kwaivgi/kling-v2.6": "start_image",
    "wan-video/wan-2.5-i2v": "image",
}
_LAST_FRAME_INPUT_KEY: dict[str, str] = {
    "bytedance/seedance-2.5": "last_frame_image",
    "bytedance/seedance-2.0": "last_frame_image",
    "bytedance/seedance-1-pro": "last_frame_image",
    "google/veo-3.1": "last_frame",
    "google/veo-3.1-fast": "last_frame",
}
# Models with a dedicated reference-image slot that is distinct from the
# source/init image slot. Reference images must not fall through to the
# generic ``image`` key or the provider silently drops them.
_REFERENCE_IMAGE_INPUT_KEY: dict[str, str] = {
    "minimax/video-01": "subject_reference",
}
# Models that accept an ordered list of reference images (characters, props,
# environments) instead of a single subject reference. Seedance and Veo reject
# requests that combine this slot with first/last frames.
_REFERENCE_IMAGE_LIST_INPUT_KEY: dict[str, str] = {
    "bytedance/seedance-2.5": "reference_images",
    "bytedance/seedance-2.0": "reference_images",
    "google/veo-3.1": "reference_images",
    "google/veo-3.1-fast": "reference_images",
}


def _guess_kind_from_url(url: str) -> AssetKind:
    """Infer asset kind from a URL's extension."""
    lower = url.lower().split("?")[0]
    if lower.endswith((".mp4", ".webm", ".mov", ".avi")):
        kind = AssetKind.VIDEO
    else:
        kind = AssetKind.IMAGE
    logger.debug(
        "_guess_kind_from_url url=%s kind=%s",
        url,
        kind.value,
    )
    return kind


class ReplicateProvider:
    """Generation provider adapter for Replicate's predictions API."""

    id: str = "replicate"

    def __init__(
        self,
        api_token: str,
        webhook_secret: str | None = None,
        base_url: str = "https://api.replicate.com",
        request_timeout: float = 30.0,
    ) -> None:
        self.api_token = api_token
        self.webhook_secret = webhook_secret
        self.base_url = base_url.rstrip("/")
        logger.info(
            "ReplicateProvider initialized base_url=%s request_timeout=%s "
            "webhook_secret_configured=%s",
            self.base_url,
            request_timeout,
            webhook_secret is not None,
        )
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            timeout=request_timeout,
        )
        logger.debug(
            "ReplicateProvider httpx client created base_url=%s timeout=%s",
            self.base_url,
            request_timeout,
        )

    async def submit(self, req: ProviderRequest) -> ProviderJobRef:
        """Submit a prediction to Replicate."""
        logger.info(
            "Replicate submit START model=%s webhook_url=%s num_inputs=%d num_params=%d",
            req.model,
            req.webhook_url,
            len(req.inputs) if req.inputs else 0,
            len(req.params) if req.params else 0,
        )
        logger.debug(
            "Replicate submit request details model=%s prompt=%s negative_prompt=%s "
            "inputs=%s params=%s",
            req.model,
            req.prompt,
            req.negative_prompt,
            [{"role": inp.role, "url": inp.url} for inp in (req.inputs or [])],
            list((req.params or {}).keys()),
        )

        input_payload: dict[str, Any] = {}

        # Map prompt
        if req.prompt:
            input_payload["prompt"] = req.prompt
            logger.debug("Replicate submit mapped prompt key='prompt' model=%s", req.model)
        if req.negative_prompt:
            input_payload["negative_prompt"] = req.negative_prompt
            logger.debug(
                "Replicate submit mapped negative_prompt key='negative_prompt' model=%s",
                req.model,
            )

        # Map input assets by role. A few Replicate models expect image
        # inputs under a different key, so keep those quirks in one place.
        reference_list_key = _REFERENCE_IMAGE_LIST_INPUT_KEY.get(req.model)
        reference_key = _REFERENCE_IMAGE_INPUT_KEY.get(req.model)
        # Video models expose a dedicated first-frame slot. For those models a
        # reference image must never fall through to ``image``: doing so would
        # silently use the reference as the first frame and drop the rest.
        is_video_model = req.model in _FIRST_FRAME_INPUT_KEY or req.model in _LAST_FRAME_INPUT_KEY

        logger.debug(
            "Replicate submit slot resolution model=%s is_video_model=%s "
            "reference_list_key=%s reference_key=%s",
            req.model,
            is_video_model,
            reference_list_key,
            reference_key,
        )

        image_urls: list[str] = []
        reference_urls: list[str] = []
        for inp in req.inputs:
            logger.debug(
                "Replicate submit processing input role=%s url=%s model=%s is_video_model=%s",
                inp.role,
                inp.url,
                req.model,
                is_video_model,
            )
            if inp.role == "init_image":
                image_urls.append(inp.url)
                logger.debug(
                    "Replicate submit routed init_image -> image_urls (count now %d) model=%s",
                    len(image_urls),
                    req.model,
                )
            elif inp.role == "reference_image":
                if reference_list_key:
                    reference_urls.append(inp.url)
                    logger.debug(
                        "Replicate submit routed reference_image -> reference_list_key=%s "
                        "(count now %d) model=%s",
                        reference_list_key,
                        len(reference_urls),
                        req.model,
                    )
                elif reference_key:
                    input_payload[reference_key] = inp.url
                    logger.debug(
                        "Replicate submit routed reference_image -> reference_key=%s model=%s",
                        reference_key,
                        req.model,
                    )
                elif is_video_model:
                    logger.warning(
                        "Replicate submit model=%s is a video model and does not accept "
                        "reference images; raising PermanentProviderError",
                        req.model,
                    )
                    raise PermanentProviderError(
                        f"Replicate model '{req.model}' does not accept reference images"
                    )
                else:
                    image_urls.append(inp.url)
                    logger.debug(
                        "Replicate submit routed reference_image -> image_urls "
                        "(fallback, count now %d) model=%s",
                        len(image_urls),
                        req.model,
                    )
            elif inp.role == "first_frame":
                first_frame_key = _FIRST_FRAME_INPUT_KEY.get(req.model, "first_frame")
                input_payload[first_frame_key] = inp.url
                logger.debug(
                    "Replicate submit routed first_frame -> key=%s model=%s",
                    first_frame_key,
                    req.model,
                )
            elif inp.role == "last_frame":
                last_frame_key = _LAST_FRAME_INPUT_KEY.get(req.model, "last_frame")
                input_payload[last_frame_key] = inp.url
                logger.debug(
                    "Replicate submit routed last_frame -> key=%s model=%s",
                    last_frame_key,
                    req.model,
                )
            elif inp.role == "mask":
                input_payload["mask"] = inp.url
                logger.debug(
                    "Replicate submit routed mask -> key='mask' model=%s",
                    req.model,
                )
            else:
                logger.warning(
                    "Replicate submit unknown input role=%s url=%s model=%s; ignoring",
                    inp.role,
                    inp.url,
                    req.model,
                )

        if reference_urls:
            assert reference_list_key is not None
            input_payload[reference_list_key] = reference_urls
            logger.info(
                "Replicate submit set reference_list_key=%s with %d reference image(s) model=%s",
                reference_list_key,
                len(reference_urls),
                req.model,
            )

        if image_urls:
            list_key = _IMAGE_LIST_INPUT_KEY.get(req.model)
            if list_key:
                input_payload[list_key] = image_urls
                logger.info(
                    "Replicate submit set IMAGE_LIST_INPUT_KEY key=%s with %d image(s) model=%s",
                    list_key,
                    len(image_urls),
                    req.model,
                )
            else:
                single_key = _IMAGE_INPUT_KEY.get(req.model, "image")
                input_payload[single_key] = image_urls[0]
                logger.info(
                    "Replicate submit set single image key=%s url_count=%d model=%s "
                    "(only first image sent)",
                    single_key,
                    len(image_urls),
                    req.model,
                )
                if len(image_urls) > 1:
                    logger.warning(
                        "Replicate submit model=%s uses single-image slot '%s' but %d "
                        "init images were provided; only the first will be sent",
                        req.model,
                        single_key,
                        len(image_urls),
                    )

        # Merge model-specific params
        before_param_count = len(input_payload)
        input_payload.update(req.params or {})
        logger.debug(
            "Replicate submit merged %d model-specific params into input_payload "
            "(keys before merge=%d, after=%d) model=%s",
            len(req.params or {}),
            before_param_count,
            len(input_payload),
            req.model,
        )
        logger.debug(
            "Replicate submit final input_payload keys=%s model=%s",
            sorted(input_payload),
            req.model,
        )

        # Input keys are safe to log (URLs are not). This makes it obvious when
        # a reference image was routed to the wrong provider slot.
        logger.debug(
            "Replicate input model=%s roles=%s keys=%s",
            req.model,
            [inp.role for inp in req.inputs],
            sorted(input_payload),
        )

        body: dict[str, Any] = {
            "version": req.model,
            "input": input_payload,
        }

        if req.webhook_url:
            body["webhook"] = req.webhook_url
            body["webhook_events_filter"] = ["completed"]
            logger.debug(
                "Replicate submit attached webhook_url=%s events_filter=['completed'] model=%s",
                req.webhook_url,
                req.model,
            )

        url = "/v1/predictions"
        logger.info(
            "Replicate submit POST %s model=%s webhook_attached=%s",
            url,
            req.model,
            bool(req.webhook_url),
        )
        logger.debug(
            "Replicate submit request body model=%s body_keys=%s input_keys=%s",
            req.model,
            sorted(body),
            sorted(input_payload),
        )

        resp = await self._client.post(url, json=body)
        logger.info(
            "Replicate submit POST %s response status=%s model=%s",
            url,
            resp.status_code,
            req.model,
        )
        logger.debug(
            "Replicate submit response headers=%s body_length=%d model=%s",
            dict(resp.headers),
            len(resp.text),
            req.model,
        )

        self._check_response(resp)

        data = resp.json()
        job_id = data.get("id", "")
        raw_status = data.get("status")
        logger.info(
            "Replicate submit SUCCESS model=%s provider_job_id=%s raw_status=%s",
            req.model,
            job_id,
            raw_status,
        )
        logger.debug(
            "Replicate submit response data keys=%s model=%s provider_job_id=%s",
            sorted(data),
            req.model,
            job_id,
        )

        return ProviderJobRef(
            provider_id=self.id,
            provider_job_id=job_id,
        )

    async def get_status(self, ref: ProviderJobRef) -> ProviderStatus:
        """Fetch current prediction status from Replicate."""
        url = f"/v1/predictions/{ref.provider_job_id}"
        logger.info(
            "Replicate get_status START provider_job_id=%s url=%s",
            ref.provider_job_id,
            url,
        )
        logger.debug(
            "Replicate get_status GET %s provider_job_id=%s",
            url,
            ref.provider_job_id,
        )

        resp = await self._client.get(url)
        logger.info(
            "Replicate get_status GET %s response status=%s provider_job_id=%s",
            url,
            resp.status_code,
            ref.provider_job_id,
        )
        logger.debug(
            "Replicate get_status response headers=%s body_length=%d provider_job_id=%s",
            dict(resp.headers),
            len(resp.text),
            ref.provider_job_id,
        )

        self._check_response(resp)

        data = resp.json()
        raw_status = data.get("status", "failed")
        state = _STATUS_MAP.get(raw_status, ProviderJobState.FAILED)

        logger.debug(
            "Replicate get_status provider_job_id=%s raw_status=%s mapped_state=%s error=%s",
            ref.provider_job_id,
            raw_status,
            state.value,
            data.get("error"),
        )

        outputs: list[ProviderOutput] = []
        if state == ProviderJobState.SUCCEEDED:
            logger.debug(
                "Replicate get_status normalizing output for SUCCEEDED job provider_job_id=%s",
                ref.provider_job_id,
            )
            outputs = self.normalize_output(data)
            logger.info(
                "Replicate get_status provider_job_id=%s state=%s num_outputs=%d",
                ref.provider_job_id,
                state.value,
                len(outputs),
            )
        else:
            logger.debug(
                "Replicate get_status provider_job_id=%s state=%s skipping output normalization",
                ref.provider_job_id,
                state.value,
            )

        error_message = data.get("error")
        if error_message:
            logger.warning(
                "Replicate get_status provider_job_id=%s state=%s error_message=%s",
                ref.provider_job_id,
                state.value,
                error_message,
            )

        logger.info(
            "Replicate get_status RETURN provider_job_id=%s state=%s num_outputs=%d error_code=%s",
            ref.provider_job_id,
            state.value,
            len(outputs),
            "PROVIDER_FAILURE" if error_message else None,
        )
        return ProviderStatus(
            state=state,
            outputs=outputs,
            error_code="PROVIDER_FAILURE" if error_message else None,
            error_message=error_message,
        )

    async def cancel(self, ref: ProviderJobRef) -> None:
        """Cancel a running prediction. Swallow 'already finished' errors."""
        url = f"/v1/predictions/{ref.provider_job_id}/cancel"
        logger.info(
            "Replicate cancel START provider_job_id=%s url=%s",
            ref.provider_job_id,
            url,
        )
        try:
            resp = await self._client.post(url)
            logger.debug(
                "Replicate cancel POST %s response status=%s provider_job_id=%s",
                url,
                resp.status_code,
                ref.provider_job_id,
            )
            # 404 or 409 means already done — swallow
            if resp.status_code not in (200, 201, 404, 409):
                logger.warning(
                    "Replicate cancel POST %s unexpected status=%s before "
                    "_check_response provider_job_id=%s",
                    url,
                    resp.status_code,
                    ref.provider_job_id,
                )
                self._check_response(resp)
            logger.info(
                "Replicate cancel RETURN provider_job_id=%s status=%s swallowed=%s",
                ref.provider_job_id,
                resp.status_code,
                resp.status_code in (404, 409),
            )
        except (httpx.HTTPError, ProviderError) as exc:
            logger.warning(
                "Replicate cancel swallowed exception provider_job_id=%s url=%s exception=%s",
                ref.provider_job_id,
                url,
                exc,
            )
            pass  # Best-effort cancel

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        """Verify Replicate webhook using Svix/Standard Webhooks HMAC-SHA256 scheme."""
        logger.debug(
            "Replicate verify_webhook START num_headers=%d body_length=%d",
            len(headers),
            len(body),
        )

        # Normalize header access (case-insensitive)
        h = {k.lower(): v for k, v in headers.items()}
        logger.debug(
            "Replicate verify_webhook normalized headers keys=%s",
            sorted(h),
        )

        msg_id = h.get("webhook-id") or h.get("svix-id")
        timestamp = h.get("webhook-timestamp") or h.get("svix-timestamp")
        signature_header = h.get("webhook-signature") or h.get("svix-signature")

        logger.debug(
            "Replicate verify_webhook extracted headers msg_id=%s timestamp=%s "
            "signature_header_present=%s",
            msg_id,
            timestamp,
            bool(signature_header),
        )

        if not msg_id or not timestamp or not signature_header:
            logger.warning(
                "Replicate verify_webhook FAILED missing headers msg_id=%s "
                "timestamp=%s signature_header_present=%s",
                bool(msg_id),
                bool(timestamp),
                bool(signature_header),
            )
            raise PermanentProviderError("Missing required webhook signature headers")

        if not self.webhook_secret:
            logger.warning(
                "Replicate verify_webhook FAILED webhook_secret not configured",
            )
            raise PermanentProviderError("Webhook secret not configured for Replicate provider")

        # Replay protection
        try:
            ts_int = int(timestamp)
        except ValueError:
            logger.warning(
                "Replicate verify_webhook FAILED invalid timestamp timestamp=%r",
                timestamp,
            )
            raise PermanentProviderError("Invalid webhook timestamp") from None

        time_diff = abs(time.time() - ts_int)
        logger.debug(
            "Replicate verify_webhook timestamp=%s ts_int=%s time_diff=%.1fs tolerance=%ds",
            timestamp,
            ts_int,
            time_diff,
            _WEBHOOK_TOLERANCE_SECONDS,
        )

        if time_diff > _WEBHOOK_TOLERANCE_SECONDS:
            logger.warning(
                "Replicate verify_webhook FAILED timestamp outside tolerance "
                "time_diff=%.1fs tolerance=%ds",
                time_diff,
                _WEBHOOK_TOLERANCE_SECONDS,
            )
            raise PermanentProviderError("Webhook timestamp outside tolerance window")

        # Compute expected signature
        signed_content = f"{msg_id}.{timestamp}.{body.decode('utf-8')}"
        logger.debug(
            "Replicate verify_webhook signed_content=%r (body redacted)",
            f"{msg_id}.{timestamp}.<body_redacted>",
        )

        # Secret: strip "whsec_" prefix and base64-decode
        secret_str = self.webhook_secret
        had_whsec_prefix = secret_str.startswith("whsec_")
        if secret_str.startswith("whsec_"):
            secret_str = secret_str[6:]
        logger.debug(
            "Replicate verify_webhook secret had_whsec_prefix=%s secret_length_after_strip=%d",
            had_whsec_prefix,
            len(secret_str),
        )
        secret_bytes = base64.b64decode(secret_str)

        expected = base64.b64encode(
            hmac.new(secret_bytes, signed_content.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")
        logger.debug(
            "Replicate verify_webhook computed expected_signature=%s",
            expected,
        )

        # Compare against any of the provided signatures (space-separated "v1,<sig>")
        signatures = signature_header.split(" ")
        matched = any(
            sig.startswith("v1,") and hmac.compare_digest(sig[3:], expected) for sig in signatures
        )
        logger.debug(
            "Replicate verify_webhook num_signatures=%d matched=%s",
            len(signatures),
            matched,
        )
        if not matched:
            logger.warning(
                "Replicate verify_webhook FAILED invalid signature num_signatures=%d",
                len(signatures),
            )
            raise PermanentProviderError("Invalid Replicate webhook signature")

        # Parse prediction payload
        payload = json.loads(body.decode("utf-8"))
        raw_status = payload.get("status", "failed")
        state = _STATUS_MAP.get(raw_status, ProviderJobState.FAILED)
        outputs = self.normalize_output(payload) if state == ProviderJobState.SUCCEEDED else []

        logger.info(
            "Replicate verify_webhook SUCCESS provider_job_id=%s raw_status=%s "
            "state=%s num_outputs=%d",
            payload.get("id", ""),
            raw_status,
            state.value,
            len(outputs),
        )
        logger.debug(
            "Replicate verify_webhook payload keys=%s provider_job_id=%s",
            sorted(payload),
            payload.get("id", ""),
        )

        return WebhookEvent(
            provider_id=self.id,
            provider_job_id=payload.get("id", ""),
            state=state,
            outputs=outputs,
            raw_payload=payload,
        )

    def normalize_output(self, raw: dict[str, Any]) -> list[ProviderOutput]:
        """Normalize Replicate output (string, list of strings, or list of dicts)."""
        logger.debug(
            "Replicate normalize_output START raw_keys=%s",
            sorted(raw),
        )
        outputs: list[ProviderOutput] = []
        raw_output = raw.get("output")

        logger.debug(
            "Replicate normalize_output raw_output type=%s is_none=%s",
            type(raw_output).__name__,
            raw_output is None,
        )

        if raw_output is None:
            logger.debug("Replicate normalize_output raw_output is None; returning empty outputs")
            return outputs

        # Single string URL
        if isinstance(raw_output, str):
            kind = _guess_kind_from_url(raw_output)
            outputs.append(ProviderOutput(url=raw_output, kind=kind))
            logger.info(
                "Replicate normalize_output single string url=%s kind=%s",
                raw_output,
                kind.value,
            )
            return outputs

        # List of items
        if isinstance(raw_output, list):
            logger.debug(
                "Replicate normalize_output list with %d items",
                len(raw_output),
            )
            for index, item in enumerate(raw_output):
                if isinstance(item, str):
                    kind = _guess_kind_from_url(item)
                    outputs.append(ProviderOutput(url=item, kind=kind))
                    logger.debug(
                        "Replicate normalize_output item[%d] string url=%s kind=%s",
                        index,
                        item,
                        kind.value,
                    )
                elif isinstance(item, dict):
                    url = item.get("url", "")
                    mime = item.get("mime_type") or item.get("content_type")
                    is_video = bool(mime and "video" in mime)
                    kind = AssetKind.VIDEO if is_video else _guess_kind_from_url(url)
                    outputs.append(ProviderOutput(url=url, mime_type=mime, kind=kind))
                    logger.debug(
                        "Replicate normalize_output item[%d] dict url=%s mime_type=%s "
                        "is_video=%s kind=%s",
                        index,
                        url,
                        mime,
                        is_video,
                        kind.value,
                    )
                else:
                    logger.warning(
                        "Replicate normalize_output item[%d] unexpected type=%s; skipping",
                        index,
                        type(item).__name__,
                    )

        logger.info(
            "Replicate normalize_output RETURN num_outputs=%d",
            len(outputs),
        )
        for index, out in enumerate(outputs):
            logger.debug(
                "Replicate normalize_output output[%d] url=%s kind=%s mime_type=%s",
                index,
                out.url,
                out.kind.value,
                out.mime_type,
            )
        return outputs

    def _check_response(self, resp: httpx.Response) -> None:
        """Map HTTP errors to typed provider exceptions."""
        if resp.is_success:
            logger.debug(
                "Replicate _check_response SUCCESS status=%s url=%s",
                resp.status_code,
                str(resp.url),
            )
            return

        body_text = resp.text
        status = resp.status_code
        url_str = str(resp.url)

        logger.warning(
            "Replicate _check_response NON-SUCCESS status=%s url=%s body_length=%d",
            status,
            url_str,
            len(body_text),
        )
        logger.debug(
            "Replicate _check_response error body status=%s body=%r",
            status,
            body_text,
        )

        if status == 429:
            retry_after = float(resp.headers.get("retry-after", "5"))
            logger.warning(
                "Replicate _check_response RATE LIMITED status=429 url=%s retry_after=%s",
                url_str,
                retry_after,
            )
            raise RateLimitedError(f"Replicate rate limited: {body_text}", retry_after=retry_after)

        if status in (400, 401, 403, 404, 409, 422):
            logger.error(
                "Replicate _check_response PERMANENT error status=%s url=%s",
                status,
                url_str,
            )
            raise PermanentProviderError(f"Replicate error {status}: {body_text}")

        if status >= 500:
            logger.error(
                "Replicate _check_response TRANSIENT server error status=%s url=%s",
                status,
                url_str,
            )
            raise TransientProviderError(f"Replicate server error {status}: {body_text}")

        logger.error(
            "Replicate _check_response TRANSIENT unexpected status=%s url=%s",
            status,
            url_str,
        )
        raise TransientProviderError(f"Replicate unexpected status {status}: {body_text}")
