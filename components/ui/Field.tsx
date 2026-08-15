import { cn } from "@/lib/utils";
import { InputHTMLAttributes, SelectHTMLAttributes } from "react";

export function Label({ children }: { children: React.ReactNode }) {
  return <label className="label-caps mb-1.5 block">{children}</label>;
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cn(
        "h-9 w-full rounded border border-line bg-panel px-3 text-sm text-ink placeholder:text-faint",
        "focus:border-accent focus:outline-none",
        props.className
      )}
    />
  );
}

export function Select({
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={cn(
        "h-9 w-full rounded border border-line bg-panel px-3 text-sm text-ink",
        "focus:border-accent focus:outline-none",
        className
      )}
    >
      {children}
    </select>
  );
}
