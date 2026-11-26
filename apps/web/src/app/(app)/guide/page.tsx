"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowUpRight,
  BookOpen,
  Cpu,
  Lightbulb,
  Loader2,
  Sparkles,
} from "lucide-react";
import { useModels, type TaskType } from "@/hooks/use-models";
import {
  GUIDE_TASK_ORDER,
  TASK_GUIDE_META,
  recommendedModelFor,
  resolveGuideGoals,
} from "@/lib/model-guide";
import { GuideGoalCard } from "@/components/guide/guide-goal-card";
import { GuideTaskSection } from "@/components/guide/guide-task-section";
import { providerAccent, providerLabel } from "@/lib/providers";

const CHOOSING_TIPS = [
  {
    title: "Draft cheap, finish premium",
    body: "Explore prompts on FLUX Schnell or H3 Max Turbo, then re-run the winner on a premium model. You only pay full price once.",
  },
  {
    title: "Edit instead of regenerating",
    body: "If you only need one change, use an image-to-image model such as Kontext or Nano Banana Edit. It preserves the parts that already work.",
  },
  {
    title: "Lock the aspect ratio early",
    body: "Set the output ratio before you generate. Switching ratios later means a fresh generation, not a free crop.",
  },
  {
    title: "Test video prompts on a budget",
    body: "A 5-second clip ranges from about 10 to 320 credits. Validate motion and framing on a cheap model before paying for Veo or Seedance.",
  },
  {
    title: "Match the model to the content",
    body: "Ideogram for readable text, GPT Image 2 for strict prompts, Kontext for surgical edits, Veo for cinematic motion.",
  },
  {
    title: "Keep the prompt, change the model",
    body: "When comparing quality, reuse the same prompt and seed. That isolates the model as the only variable.",
  },
];

export default function ModelGuidePage() {
  const { data: models, isLoading, isError, error, refetch } = useModels();

  const goals = useMemo(() => resolveGuideGoals(models ?? []), [models]);

  const groupedTasks = useMemo(
    () =>
      GUIDE_TASK_ORDER.map((taskType) => ({
        taskType,
        models: (models ?? []).filter((model) => model.task_type === taskType),
      })).filter((group) => group.models.length > 0),
    [models]
  );

  const providers = useMemo(
    () => Array.from(new Set((models ?? []).map((model) => model.provider_id))),
    [models]
  );

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl space-y-8">
        <div className="space-y-3">
          <div className="h-8 w-56 animate-pulse rounded-lg bg-[#14161C]" />
          <div className="h-4 w-full max-w-xl animate-pulse rounded bg-[#14161C]" />
        </div>
        <div className="h-12 w-full animate-pulse rounded-2xl border border-[#262A35] bg-[#14161C]" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              key={index}
              className="h-56 animate-pulse rounded-2xl border border-[#262A35] bg-[#14161C]"
            />
          ))}
        </div>
        <div className="flex items-center justify-center gap-2 py-8 text-sm text-[#9AA1B2]">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading the model guide…
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-3 rounded-2xl border border-[#262A35] bg-[#14161C] px-6 py-16 text-center">
        <AlertCircle className="h-7 w-7 text-[#F87171]" />
        <h1 className="text-lg font-semibold text-[#E8EAF0]">
          Could not load models
        </h1>
        <p className="text-sm text-[#9AA1B2]">
          {error instanceof Error
            ? error.message
            : "The model registry is unavailable right now."}
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          className="rounded-lg border border-[#262A35] bg-[#1B1E26] px-3 py-1.5 text-xs font-medium text-[#A995FF] transition-colors hover:text-[#E8EAF0]"
        >
          Try again
        </button>
      </div>
    );
  }

  if (!models || models.length === 0) {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-3 rounded-2xl border border-[#262A35] bg-[#14161C] px-6 py-16 text-center">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-[#262A35] bg-[#1B1E26]">
          <Cpu className="h-5 w-5 text-[#A995FF]" />
        </div>
        <h1 className="text-lg font-semibold text-[#E8EAF0]">
          No models are enabled
        </h1>
        <p className="text-sm text-[#9AA1B2]">
          Enable at least one provider model in the registry to see guidance
          here.
        </p>
        <Link
          href="/settings?tab=models"
          className="underline text-xs font-medium text-[#A995FF] hover:underline"
        >
          Open AI Models &amp; Providers
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-10">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div className="flex items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#262A35] bg-[#1B1E26] text-[#A995FF]">
            <BookOpen className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-[#E8EAF0]">
                Model Guide
              </h1>
              <span className="flex items-center gap-1.5 rounded-full border border-[#262A35] bg-[#1B1E26] px-2.5 py-0.5 text-xs font-mono text-[#A995FF]">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
                Live catalog
              </span>
            </div>
            <p className="mt-1 max-w-2xl text-sm text-[#9AA1B2]">
              Not sure which model to use? Start with a goal, compare the
              trade-offs, then pick with confidence. Prices update live from the
              model registry.
            </p>
          </div>
        </div>

        <Link
          href="/settings?tab=models"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-[#262A35] bg-[#14161C] px-3 py-2 text-xs font-medium text-[#C7CBD6] transition-colors hover:border-[#3A3F4D] hover:text-[#E8EAF0]"
        >
          Browse full catalog
          <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </div>

      {/* Provider legend */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-2xl border border-[#262A35] bg-[#14161C] px-4 py-3">
        <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#9AA1B2]">
          Providers
        </span>
        {providers.map((providerId) => (
          <span
            key={providerId}
            className="flex items-center gap-1.5 text-xs text-[#C7CBD6]"
          >
            <span
              aria-hidden="true"
              className={`h-1.5 w-1.5 rounded-full bg-current ${providerAccent(
                providerId
              )}`}
            />
            {providerLabel(providerId)}
          </span>
        ))}
        <span className="ml-auto font-mono text-[11px] text-[#9AA1B2]">
          {models.length} models enabled
        </span>
      </div>

      {/* Quick picks */}
      <section aria-labelledby="guide-goals-heading" className="space-y-4">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-[#A995FF]" aria-hidden="true" />
            <h2
              id="guide-goals-heading"
              className="text-lg font-semibold text-[#E8EAF0]"
            >
              Start with your goal
            </h2>
          </div>
          <p className="mt-1 text-xs text-[#9AA1B2]">
            Each card shows our top pick and the live credit cost. Select a card
            to jump to the full comparison.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {goals.map((goal) => (
            <GuideGoalCard key={goal.id} goal={goal} />
          ))}
        </div>
      </section>

      {/* Comparison */}
      <section aria-labelledby="guide-compare-heading" className="space-y-8">
        <div>
          <h2
            id="guide-compare-heading"
            className="text-lg font-semibold text-[#E8EAF0]"
          >
            Compare every model
          </h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-[#9AA1B2]">
            Grouped by flow. Sort by speed, value, or quality — or leave it on
            <span className="text-[#C7CBD6]"> All </span>
            for our recommended order. A{" "}
            <span className="text-[#C4B5FD]">Recommended</span> badge marks the
            best starting point for each flow.
          </p>
        </div>

        {groupedTasks.map(({ taskType, models: taskModels }) => (
          <GuideTaskSection
            key={taskType}
            taskType={taskType as TaskType}
            models={taskModels}
            recommended={recommendedModelFor(taskModels, taskType as TaskType)}
          />
        ))}
      </section>

      {/* Tips */}
      <section
        aria-labelledby="guide-tips-heading"
        className="rounded-2xl border border-[#262A35] bg-[#14161C] p-6"
      >
        <div className="flex items-center gap-2">
          <Lightbulb className="h-4 w-4 text-[#F5C451]" aria-hidden="true" />
          <h2
            id="guide-tips-heading"
            className="text-base font-semibold text-[#E8EAF0]"
          >
            How to choose well
          </h2>
        </div>
        <ul className="mt-5 grid gap-5 sm:grid-cols-2">
          {CHOOSING_TIPS.map((tip, index) => (
            <li key={tip.title} className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-[#262A35] bg-[#1B1E26] font-mono text-[11px] text-[#A995FF]">
                {index + 1}
              </span>
              <div>
                <h3 className="text-sm font-medium text-[#E8EAF0]">
                  {tip.title}
                </h3>
                <p className="mt-0.5 text-xs leading-relaxed text-[#9AA1B2]">
                  {tip.body}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <p className="text-center text-xs text-[#9AA1B2]">
        Looking for slugs, input schemas, and provider metadata?{" "}
        <Link
          href="/settings?tab=models"
          className="underline text-[#A995FF] hover:underline"
        >
          Open AI Models &amp; Providers
        </Link>
        .
      </p>
    </div>
  );
}
