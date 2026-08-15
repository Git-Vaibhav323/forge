"use client";

import { cn } from "@/lib/utils";
import type { Attribute } from "@/lib/types";
import { FieldStatusBadge } from "@/components/shared/StatusBadge";
import { ConfidenceMeter } from "@/components/shared/Meters";

export function AttributeTable({
  attributes,
  selectedId,
  onSelect,
}: {
  attributes: Attribute[];
  selectedId: string | undefined;
  onSelect: (id: string) => void;
}) {
  return (
    <table className="w-full border-collapse text-[13px]">
      <thead>
        <tr className="border-b border-line text-left">
          <th className="label-caps px-3 py-2 font-normal">Attribute</th>
          <th className="label-caps px-3 py-2 font-normal">Value</th>
          <th className="label-caps px-3 py-2 font-normal">Confidence</th>
          <th className="label-caps px-3 py-2 font-normal">Status</th>
        </tr>
      </thead>
      <tbody>
        {attributes.map((attr) => (
          <tr
            key={attr.id}
            onClick={() => onSelect(attr.id)}
            className={cn(
              "cursor-pointer border-b border-line last:border-0",
              selectedId === attr.id ? "bg-accent-soft" : "hover:bg-line/20"
            )}
          >
            <td className="px-3 py-2.5 font-medium capitalize">
              {attr.name.replace(/_/g, " ")}
            </td>
            <td className="num px-3 py-2.5 font-mono">
              {attr.rawValue || <span className="text-faint">—</span>}
              {attr.unit && attr.status !== "missing" ? (
                <span className="text-faint"> {attr.unit}</span>
              ) : null}
            </td>
            <td className="px-3 py-2.5">
              {attr.status !== "missing" ? (
                <ConfidenceMeter value={attr.confidence} />
              ) : (
                <span className="text-faint">—</span>
              )}
            </td>
            <td className="px-3 py-2.5">
              <FieldStatusBadge status={attr.status} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
