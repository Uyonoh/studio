"use client";

import { useMemo, useState } from "react";
import { Lightbulb } from "lucide-react";
import type { StudioModel, TaskType } from "@/hooks/use-models";
import {
  GUIDE_FILTERS,
  QUALITY_LABELS,
  SPEED_LABELS,
  TASK_GUIDE_META,
  guideEntryFor,
  sortModelsForFilter,
  type GuideFilter,
} from "@/lib/model-guide";
import { formatCredits } from "@/components/settings/format";
import { providerAccent, providerLabel } from "@/lib/providers";

interface GuideTaskSectionProps {
  taskType: TaskType;
  models: StudioModel[];
  recommended: StudioModel | null;
}

function RecommendationBadge() {
  return (
    <span className="rounded-full border border-[#7C5CFF]/40 bg-[#6C4CE8]/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#C4B5FD]">
      Recommended
    </span>
  );
}

function SpeedPill({ speed }: { speed: keyof typeof SPEED_LABELS }) {
  const tone =
    speed === "fast"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
      : speed === "slow"
        ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
        : "border-[#262A35] bg-[#1B1E26] text-[#C7CBD6]";

  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`}>
      {SPEED_LABELS[speed]}
    </span>
  );
}

export function GuideTaskSection({
  taskType,
  models,
  recommended,
}: GuideTaskSectionProps) {
  const [filter, setFilter] = useState<GuideFilter>("all");
  const meta = TASK_GUIDE_META[taskType];
  const sorted = useMemo(
    () => sortModelsForFilter(models, filter),
    [models, filter]
  );

  return (
    <section
      id={`guide-task-${taskType}`}
      aria-labelledby={`guide-task-${taskType}-heading`}
      className="scroll-mt-24 space-y-4"
    >
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2
              id={`guide-task-${taskType}-heading`}
              className="text-lg font-semibold text-[#E8EAF0]"
            >
              {meta.label}
            </h2>
            <span className="rounded-full border border-[#262A35] bg-[#1B1E26] px-2.5 py-0.5 font-mono text-[11px] text-[#9AA1B2]">
              {models.length} model{models.length === 1 ? "" : "s"}
            </span>
          </div>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-[#9AA1B2]">
            {meta.description}
          </p>
        </div>

        <div
          role="group"
          aria-label={`${meta.label} sorting`}
          className="flex shrink-0 flex-wrap items-center gap-1.5"
        >
          {GUIDE_FILTERS.map((option) => {
            const isActive = option.id === filter;
            return (
              <button
                key={option.id}
                type="button"
                aria-pressed={isActive}
                onClick={() => setFilter(option.id)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] ${
                  isActive
                    ? "border-[#7C5CFF]/50 bg-[#6C4CE8]/20 text-[#E8EAF0]"
                    : "border-[#262A35] bg-[#14161C] text-[#9AA1B2] hover:border-[#3A3F4D] hover:text-[#E8EAF0]"
                }`}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Desktop comparison table */}
      <div className="hidden overflow-hidden rounded-2xl border border-[#262A35] bg-[#14161C] md:block">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">
            {meta.label} models with provider, best use cases, speed, quality
            tier, and credit cost.
          </caption>
          <thead>
            <tr className="border-b border-[#262A35] text-[10px] uppercase tracking-[0.14em] text-[#9AA1B2]">
              <th scope="col" className="px-5 py-3 font-semibold">
                Model
              </th>
              <th scope="col" className="px-4 py-3 font-semibold">
                Provider
              </th>
              <th scope="col" className="px-4 py-3 font-semibold">
                Best for
              </th>
              <th scope="col" className="px-4 py-3 font-semibold">
                Speed
              </th>
              <th scope="col" className="px-4 py-3 font-semibold">
                Quality
              </th>
              <th scope="col" className="px-5 py-3 text-right font-semibold">
                Credits
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#262A35]">
            {sorted.map((model) => {
              const entry = guideEntryFor(model.slug);
              const isRecommended = model.slug === recommended?.slug;

              return (
                <tr
                  key={model.id}
                  className={
                    isRecommended
                      ? "bg-[#6C4CE8]/5"
                      : "transition-colors hover:bg-[#1B1E26]/40"
                  }
                >
                  <th scope="row" className="px-5 py-4 align-top font-normal">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-[#E8EAF0]">
                        {model.display_name}
                      </span>
                      {isRecommended && <RecommendationBadge />}
                    </div>
                    <span className="mt-0.5 block font-mono text-[10px] text-[#9AA1B2]">
                      {model.slug}
                    </span>
                  </th>
                  <td className="px-4 py-4 align-top">
                    <span className="flex items-center gap-2 text-xs text-[#C7CBD6]">
                      <span
                        aria-hidden="true"
                        className={`h-1.5 w-1.5 rounded-full bg-current ${providerAccent(
                          model.provider_id
                        )}`}
                      />
                      {providerLabel(model.provider_id)}
                    </span>
                  </td>
                  <td className="max-w-sm px-4 py-4 align-top">
                    <p className="text-xs leading-relaxed text-[#C7CBD6]">
                      {entry.summary}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {entry.bestFor.map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full border border-[#262A35] bg-[#0B0C10] px-2 py-0.5 text-[10px] text-[#9AA1B2]"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                    {entry.tip && (
                      <p className="mt-2 flex items-start gap-1.5 text-[11px] leading-relaxed text-[#8B93A7]">
                        <Lightbulb
                          className="mt-0.5 h-3 w-3 shrink-0 text-[#F5C451]"
                          aria-hidden="true"
                        />
                        <span>{entry.tip}</span>
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-4 align-top">
                    <SpeedPill speed={entry.speed} />
                  </td>
                  <td className="px-4 py-4 align-top">
                    <span className="text-xs text-[#C7CBD6]">
                      {QUALITY_LABELS[entry.qualityTier]}
                    </span>
                  </td>
                  <td className="px-5 py-4 align-top text-right">
                    <span className="font-mono text-sm text-[#E8EAF0]">
                      {formatCredits(model.cost_credits)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <ul className="space-y-3 md:hidden">
        {sorted.map((model) => {
          const entry = guideEntryFor(model.slug);
          const isRecommended = model.slug === recommended?.slug;

          return (
            <li
              key={model.id}
              className={`rounded-2xl border bg-[#14161C] p-4 ${
                isRecommended ? "border-[#7C5CFF]/40" : "border-[#262A35]"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-medium text-[#E8EAF0]">
                      {model.display_name}
                    </h3>
                    {isRecommended && <RecommendationBadge />}
                  </div>
                  <p className="mt-0.5 font-mono text-[10px] text-[#9AA1B2]">
                    {model.slug}
                  </p>
                </div>
                <span className="shrink-0 rounded-full border border-[#262A35] bg-[#0B0C10] px-2 py-0.5 font-mono text-[11px] text-[#E8EAF0]">
                  {formatCredits(model.cost_credits)} cr
                </span>
              </div>

              <p className="mt-3 text-xs leading-relaxed text-[#C7CBD6]">
                {entry.summary}
              </p>

              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <span className={`text-[11px] font-medium ${providerAccent(model.provider_id)}`}>
                  {providerLabel(model.provider_id)}
                </span>
                <span aria-hidden="true" className="text-[#3A3F4D]">
                  ·
                </span>
                <SpeedPill speed={entry.speed} />
                <span className="rounded-full border border-[#262A35] bg-[#1B1E26] px-2 py-0.5 text-[11px] text-[#C7CBD6]">
                  {QUALITY_LABELS[entry.qualityTier]}
                </span>
              </div>

              <div className="mt-2 flex flex-wrap gap-1">
                {entry.bestFor.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-[#262A35] bg-[#0B0C10] px-2 py-0.5 text-[10px] text-[#9AA1B2]"
                  >
                    {tag}
                  </span>
                ))}
              </div>

              {entry.tip && (
                <p className="mt-2 flex items-start gap-1.5 text-[11px] leading-relaxed text-[#8B93A7]">
                  <Lightbulb
                    className="mt-0.5 h-3 w-3 shrink-0 text-[#F5C451]"
                    aria-hidden="true"
                  />
                  <span>{entry.tip}</span>
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
