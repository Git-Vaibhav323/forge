"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";

export interface TabItem {
  href: string;
  label: string;
  count?: number;
  tone?: "conflict" | "review";
}

export function Tabs({
  items,
  activeHref,
}: {
  items: TabItem[];
  activeHref: string;
}) {
  return (
    <nav className="flex gap-5 border-b border-line">
      {items.map((item) => {
        const active = activeHref === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "relative flex items-center gap-1.5 py-2.5 text-sm transition-colors",
              active ? "text-ink" : "text-muted hover:text-ink"
            )}
          >
            {item.label}
            {typeof item.count === "number" && item.count > 0 && (
              <span
                className={cn(
                  "rounded-sm px-1 font-mono text-[10px]",
                  item.tone === "conflict" && "bg-conflict-soft text-conflict",
                  item.tone === "review" && "bg-review-soft text-review",
                  !item.tone && "bg-line text-muted"
                )}
              >
                {item.count}
              </span>
            )}
            {active && (
              <span className="absolute -bottom-px left-0 right-0 h-[2px] bg-ink" />
            )}
          </Link>
        );
      })}
    </nav>
  );
}
