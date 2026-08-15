"use client";

import { useEffect, useState } from "react";
import { useAttributes } from "@/hooks/useProjectData";
import { AttributeTable } from "@/components/evidence/AttributeTable";
import { EvidencePanel } from "@/components/evidence/EvidencePanel";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";

export default function EvidencePage({
  params,
}: {
  params: { projectId: string };
}) {
  const { data: attributes, loading } = useAttributes(params.projectId);
  const [selectedId, setSelectedId] = useState<string>();

  useEffect(() => {
    if (attributes && attributes.length > 0 && !selectedId) {
      setSelectedId(attributes[0]!.id);
    }
  }, [attributes, selectedId]);

  const selected = attributes?.find((a) => a.id === selectedId);

  return (
    <div className="grid grid-cols-3 gap-4">
      <Card className="col-span-2 overflow-hidden">
        <CardHeader>
          <p className="text-[13px] font-medium">Fields on the record</p>
          <p className="mt-0.5 text-[12px] text-muted">
            A value without a source is not shown as fact. Click a row.
          </p>
        </CardHeader>
        {loading && (
          <p className="px-4 py-6 font-mono text-[11px] text-faint">
            Reading fields…
          </p>
        )}
        {attributes && (
          <AttributeTable
            attributes={attributes}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        )}
      </Card>

      <Card className="h-fit">
        <CardBody>
          <EvidencePanel attribute={selected} />
        </CardBody>
      </Card>
    </div>
  );
}
