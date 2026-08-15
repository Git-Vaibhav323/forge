import { cn, formatConfidence } from "@/lib/utils";

export function ConfidenceMeter({ value }: { value: number }) {
  const tone =
    value >= 0.85 ? "bg-verified" : value >= 0.6 ? "bg-review" : "bg-conflict";
  return (
    <div className="flex items-center gap-1.5">
      <div className="flex h-2.5 w-10 gap-[2px]">
        {Array.from({ length: 5 }).map((_, i) => (
          <span
            key={i}
            className={cn(
              "h-full flex-1 rounded-[1px]",
              i < Math.round(value * 5) ? tone : "bg-line"
            )}
          />
        ))}
      </div>
      <span className="num font-mono text-[11px] text-muted">
        {formatConfidence(value)}
      </span>
    </div>
  );
}

export function CompletenessGauge({
  value,
  size = "md",
}: {
  value: number;
  size?: "sm" | "md";
}) {
  const tone =
    value >= 90 ? "text-verified" : value >= 60 ? "text-review" : "text-conflict";
  const dim = size === "sm" ? 36 : 52;
  const stroke = size === "sm" ? 4 : 5;
  const radius = (dim - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="relative shrink-0" style={{ width: dim, height: dim }}>
      <svg width={dim} height={dim} className="-rotate-90">
        <circle
          cx={dim / 2}
          cy={dim / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="stroke-line"
        />
        <circle
          cx={dim / 2}
          cy={dim / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="butt"
          className={cn("transition-all", tone)}
          stroke="currentColor"
        />
      </svg>
      <span
        className={cn(
          "num absolute inset-0 flex items-center justify-center font-mono font-semibold",
          size === "sm" ? "text-[10px]" : "text-xs"
        )}
      >
        {value}%
      </span>
    </div>
  );
}
