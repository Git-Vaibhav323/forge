"use client";

import { cn } from "@/lib/utils";
import { WORK_CATEGORIES } from "@/lib/categories";

export function CategorySelector({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (categoryId: string) => void;
}) {
  return (
    <div className="max-h-72 divide-y divide-line overflow-y-auto border border-line">
      {WORK_CATEGORIES.map((category) => {
        const active = value === category.id;
        return (
          <button
            key={category.id}
            type="button"
            onClick={() => onChange(category.id)}
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
              <span className="block text-[13px] font-medium">{category.label}</span>
              <span
                className={cn(
                  "mt-0.5 block text-[12px] leading-snug",
                  active ? "text-paper/70" : "text-muted"
                )}
              >
                {category.description}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
