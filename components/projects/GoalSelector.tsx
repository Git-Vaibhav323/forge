"use client";

import { cn } from "@/lib/utils";
import type { ProjectGoal } from "@/lib/types";
import { PROJECT_GOAL_LABELS } from "@/lib/types";

const descriptions: Record<ProjectGoal, string> = {
  product_configuration:
    "One SKU, fully specified, with parts that actually fit together.",
  bom_generation: "A parts list for the application as described.",
  technical_quotation: "A quote an engineer can stand behind.",
  product_datasheet: "A datasheet that only prints cited fields.",
  installation_package: "Mounting, wiring, commissioning — from the record.",
  replacement_recommendation: "A substitute for a part that no longer ships.",
  rfq_response: "Map the customer’s list onto the catalog, field by field.",
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
