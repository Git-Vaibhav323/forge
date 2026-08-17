"use client";

import { cn } from "@/lib/utils";
import type { ProjectGoal } from "@/lib/types";
import { PROJECT_GOAL_LABELS } from "@/lib/types";

const descriptions: Record<ProjectGoal, string> = {
  product_configuration:
    "A complete spec — every detail sourced, nothing invented.",
  bom_generation: "A structured list of everything that belongs together.",
  technical_quotation: "A quote where every line cites a source.",
  product_datasheet: "A one-page summary with only verified facts.",
  installation_package: "Setup and deployment steps from what you know.",
  replacement_recommendation: "A plan to upgrade or replace what exists today.",
  rfq_response: "A response mapped to what was asked for.",
};

const goals: ProjectGoal[] = [
  "product_configuration",
  "bom_generation",
  "technical_quotation",
  "product_datasheet",
  "installation_package",
  "replacement_recommendation",
  "rfq_response",
];

export function GoalSelector({
  value,
  onChange,
}: {
  value: ProjectGoal | null;
  onChange: (goal: ProjectGoal) => void;
}) {
  return (
    <div className="divide-y divide-line border border-line">
      {goals.map((goal) => {
        const active = value === goal;
        return (
          <button
            key={goal}
            type="button"
            onClick={() => onChange(goal)}
            className={cn(
              "flex w-full items-start gap-3 px-3 py-2.5 text-left",
              active ? "bg-ink text-paper" : "bg-panel hover:bg-paper"
            )}
          >
            <span
              className={cn(
                "mt-0.5 flex h-3.5 w-3.5 shrink-0 items-center justify-center border",
                active ? "border-paper" : "border-line-strong"
              )}
            >
              {active && <span className="h-1.5 w-1.5 bg-paper" />}
            </span>
            <span>
              <span className="block text-[13px] font-medium">
                {PROJECT_GOAL_LABELS[goal]}
              </span>
              <span
                className={cn(
                  "mt-0.5 block text-[12px] leading-snug",
                  active ? "text-paper/70" : "text-muted"
                )}
              >
                {descriptions[goal]}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
