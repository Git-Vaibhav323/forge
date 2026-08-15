import { LucideIcon } from "lucide-react";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex gap-3 px-4 py-6">
      <Icon size={16} strokeWidth={1.75} className="mt-0.5 shrink-0 text-faint" />
      <div>
        <p className="text-[13px] font-medium text-ink">{title}</p>
        <p className="mt-1 max-w-md text-[12px] leading-relaxed text-muted">
          {description}
        </p>
        {action && <div className="mt-3">{action}</div>}
      </div>
    </div>
  );
}
