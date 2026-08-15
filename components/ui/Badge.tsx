import { cn } from "@/lib/utils";

type Tone = "verified" | "review" | "conflict" | "missing" | "accent" | "neutral";

const tones: Record<Tone, string> = {
  verified: "bg-verified-soft text-verified",
  review: "bg-review-soft text-review",
  conflict: "bg-conflict-soft text-conflict",
  missing: "bg-missing-soft text-muted",
  accent: "bg-accent-soft text-accent",
  neutral: "bg-line/50 text-ink",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 font-mono text-[11px] font-medium uppercase tracking-[0.04em]",
        tones[tone],
        className
      )}
    >
      {children}
    </span>
  );
}
