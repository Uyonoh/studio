# Pull Request

<!--
Thanks for contributing! Fill in the sections below.
Keep the PR title in Conventional Commits form, e.g. `fix(worker): handle empty asset counts`.
-->

## Summary

<!-- What changed and why? One or two sentences a reviewer can scan first. -->

## Related issues

<!-- e.g. Closes #11, Relates to #12 -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / chore
- [ ] Documentation
- [ ] CI / tooling / tests
- [ ] Breaking change (describe impact below)

## What changed

<!--
Bullet the notable changes. Call out anything a reviewer must not miss:
- DB migrations (name + ordering)
- API/schema changes (and regenerated `docs/openapi.json` / `api-client` schema)
- New or changed environment variables (update `.env.example` and docs)
- Provider/model behavior changes
-->

## How was this tested

<!-- Paste the commands you ran and their result. Include a regression test note for bug fixes. -->

```bash
# example
uv run pytest -q
pnpm -r --if-present test
```

## Screenshots / recordings

<!-- UI changes only. Before/after is ideal. Remove this section if not applicable. -->

---

## Author checklist (Definition of Done)

### Python

- [ ] `uv run ruff check .`
- [ ] `uv run ruff format --check .`
- [ ] `uv run mypy -p api -p worker -p studio_core -p studio_providers -p studio_media`
- [ ] `uv run mypy apps/api/tests apps/worker/tests packages/studio_core/tests packages/studio_providers/tests packages/studio_media/tests tests/e2e_backend tests/infra`
- [ ] `uv run pytest -q`

### Web / TypeScript

- [ ] `pnpm -r --if-present lint`
- [ ] `pnpm --filter "./packages/**" build`
- [ ] `pnpm -r --if-present typecheck`
- [ ] `pnpm -r --if-present test`

### Browser E2E (required when UI, auth, or user flows change)

- [ ] `pnpm --filter @studio/api-client build`
- [ ] `pnpm --filter @studio/web build`
- [ ] `pnpm --filter @studio/web exec playwright install chromium`
- [ ] `pnpm --filter @studio/web e2e`

### General

- [ ] Tests added or updated for new logic and endpoints
- [ ] Bug fix includes a regression test that fails before the fix
- [ ] Test doubles/mocks updated when queries or payload shapes change
- [ ] No secrets, stray `TODO`s without a ticket, or commented-out code
- [ ] Public functions/classes documented; non-obvious decisions explained
- [ ] Docs/README/`.env.example` updated for setup, config, or env changes
- [ ] Migrations are ordered, documented, and safe to re-run where practical
- [ ] `.\scripts\ci-local.ps1 -Check` (or `make ci`) passes locally

---

## Maintainer review checklist

### Correctness

- [ ] Behavior matches the linked issue and acceptance criteria
- [ ] Edge cases covered: empty/`None`, concurrency, retries, idempotency
- [ ] Error paths return the right status/error code and do not leak internals
- [ ] No unintended API/DB/schema changes; if intended, migration + docs + codegen included
- [ ] State transitions are guarded (expected-status checks) and refunds/cancellations are safe

### Tests

- [ ] New behavior is covered; the fix is proven by a test that would have caught it
- [ ] Mocks/fakes mirror real query and payload shapes (a common source of false greens)
- [ ] No tests skipped, weakened, or deleted without justification
- [ ] Deterministic: no reliance on wall-clock timing, network, or local `.env`

### Security & data

- [ ] Authorization scoping enforced (workspace/project ownership)
- [ ] Input validated; upload size/type and rate limits respected
- [ ] No secrets in code, logs, fixtures, or error messages
- [ ] No PII or tokens written to logs

### Frontend (if applicable)

- [ ] Loading, empty, and error states handled
- [ ] Accessible: labels, focus management, keyboard paths, color contrast
- [ ] Responsive at 375px with no horizontal overflow
- [ ] No new console errors or hydration warnings

### Operations

- [ ] Env/config changes documented in `.env.example` and deployment docs
- [ ] Logging is meaningful and not noisy or sensitive
- [ ] Rollback path exists for migrations or risky feature flags

## Notes for reviewers

<!-- Risky areas, follow-ups, out-of-scope items, or specific files to focus on. -->
