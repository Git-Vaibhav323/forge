"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { apiMode } from "@/lib/api";

const navItems = [
  { href: "/", label: "Jobs" },
  { href: "/projects/new", label: "Open a job" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-[13.5rem] shrink-0 flex-col border-r border-line bg-panel">
      <div className="border-b border-line px-4 py-5">
        <p className="font-mono text-[11px] font-semibold tracking-[0.18em] text-ink">
          FORGEDATA
        </p>
        <p className="mt-1 text-[12px] leading-snug text-muted">
          Product records, cited before they leave the desk.
        </p>
      </div>

      <nav className="flex-1 px-2 py-3">
        {navItems.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "block border-l-2 px-3 py-1.5 text-[13px]",
                active
                  ? "border-ink font-medium text-ink"
                  : "border-transparent text-muted hover:border-line-strong hover:text-ink"
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-line px-4 py-3 text-[12px] text-muted">
        <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-faint">
          Store
        </p>
        <p className="mt-1">
          {apiMode === "mock" ? "Mock drawer (no plant DB)" : "Live API"}
        </p>
        <Link
          href="/settings"
          className="mt-2 inline-block text-[12px] text-ink underline decoration-line underline-offset-2 hover:decoration-ink"
        >
          Connection
        </Link>
      </div>
    </aside>
  );
}
