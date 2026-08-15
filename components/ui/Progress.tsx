import { cn } from "@/lib/utils";

export function Progress({
  value,
  className,
  toneClassName = "bg-ink",
}: {
  value: number;
  className?: string;
  toneClassName?: string;
}) {
  return (
    <div
      className={cn("h-1.5 w-full overflow-hidden rounded-sm bg-line", className)}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cn("h-full transition-all", toneClassName)}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}
