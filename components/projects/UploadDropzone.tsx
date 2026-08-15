"use client";

import { useRef, useState } from "react";
import { UploadCloud, FileText, X } from "lucide-react";
import { cn } from "@/lib/utils";

export function UploadDropzone({
  files,
  onFilesChange,
}: {
  files: File[];
  onFilesChange: (files: File[]) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(list: FileList | null) {
    if (!list) return;
    onFilesChange([...files, ...Array.from(list)]);
  }

  function removeFile(idx: number) {
    onFilesChange(files.filter((_, i) => i !== idx));
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          addFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer items-start gap-3 border border-dashed px-4 py-4",
          dragging ? "border-accent bg-accent-soft" : "border-line-strong hover:bg-line/20"
        )}
      >
        <UploadCloud size={16} strokeWidth={1.75} className="mt-0.5 text-muted" />
        <div>
          <p className="text-[13px] text-ink">
            Drop PDFs, nameplate photos, or a CSV here
          </p>
          <p className="text-[12px] text-faint">or click to browse this machine</p>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          accept=".pdf,.png,.jpg,.jpeg,.webp,.csv,.xlsx,.xls,.json,.xml"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {files.length > 0 && (
        <ul className="mt-3 divide-y divide-line border border-line">
          {files.map((file, idx) => (
            <li
              key={`${file.name}-${idx}`}
              className="flex items-center gap-2 px-3 py-2 text-[13px]"
            >
              <FileText size={14} className="shrink-0 text-faint" />
              <span className="min-w-0 flex-1 truncate">{file.name}</span>
              <span className="font-mono text-[11px] text-faint">
                {(file.size / 1024).toFixed(0)} KB
              </span>
              <button
                type="button"
                onClick={() => removeFile(idx)}
                className="text-faint hover:text-conflict"
                aria-label={`Remove ${file.name}`}
              >
                <X size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
