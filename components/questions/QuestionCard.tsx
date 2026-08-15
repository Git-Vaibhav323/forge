"use client";

import { useState } from "react";
import { HelpCircle } from "lucide-react";
import type { Question } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { cn } from "@/lib/utils";

const priorityTone: Record<Question["priority"], string> = {
  critical: "text-conflict",
  high: "text-review",
  medium: "text-accent",
  low: "text-muted",
};

export function QuestionCard({
  question,
  onAnswer,
  submitting,
}: {
  question: Question;
  onAnswer: (answer: string) => void;
  submitting: boolean;
}) {
  const [selected, setSelected] = useState<string>("");
  const [text, setText] = useState("");

  const answer = question.inputType === "text" || question.inputType === "number" ? text : selected;

  return (
    <div className="border border-line bg-panel p-5">
      <div className="mb-3 flex items-center gap-2">
        <HelpCircle size={16} className="text-review" />
        <span
          className={cn(
            "font-mono text-[11px] uppercase tracking-[0.06em]",
            priorityTone[question.priority]
          )}
        >
          {question.priority} priority
        </span>
        <span className="font-mono text-[11px] text-faint">
          · field: {question.field}
        </span>
      </div>

      <p className="mb-1 text-[15px] font-medium">{question.text}</p>
      <p className="mb-4 text-[12px] text-muted">{question.whyAsked}</p>

      {(question.inputType === "select" || question.inputType === "multi_select") &&
        question.options && (
          <div className="mb-4 grid gap-2">
            {question.options.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setSelected(opt)}
                className={cn(
                  "rounded border px-3 py-2 text-left text-[13px] transition-colors",
                  selected === opt
                    ? "border-ink bg-ink text-paper"
                    : "border-line hover:border-line-strong"
                )}
              >
                {opt}
              </button>
            ))}
          </div>
        )}

      {(question.inputType === "text" || question.inputType === "number") && (
        <div className="mb-4">
          <Input
            type={question.inputType === "number" ? "number" : "text"}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type your answer"
          />
        </div>
      )}

      <div className="flex items-center justify-between">
          <button
            type="button"
            disabled={submitting}
            onClick={() => onAnswer("Not applicable")}
            className="text-[12px] text-muted underline decoration-dotted hover:text-ink disabled:text-faint"
          >
            Not applicable
          </button>
          <div className="flex gap-2">
          <button
            type="button"
            disabled={submitting}
            onClick={() => onAnswer("I don't know")}
            className="text-[12px] text-muted underline decoration-dotted hover:text-ink disabled:text-faint"
          >
            I don&rsquo;t know
          </button>
          <Button
            variant="primary"
            size="sm"
            disabled={!answer || submitting}
            onClick={() => onAnswer(answer)}
          >
            {submitting ? "Saving…" : "Submit answer"}
          </Button>
        </div>
      </div>
    </div>
  );
}
