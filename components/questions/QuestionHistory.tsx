import { CheckCircle2, HelpCircle, SkipForward } from "lucide-react";
import type { Question } from "@/lib/types";

export function QuestionHistory({ questions }: { questions: Question[] }) {
  if (questions.length === 0) {
    return (
      <p className="py-6 text-center text-[13px] text-muted">
        No questions asked yet.
      </p>
    );
  }

  return (
    <ul className="space-y-0">
      {questions.map((q) => (
        <li
          key={q.id}
          className="flex items-start gap-2.5 border-b border-line py-3 last:border-0"
        >
          {q.status === "answered" ? (
            <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-verified" />
          ) : q.status === "skipped" ? (
            <SkipForward size={14} className="mt-0.5 shrink-0 text-faint" />
          ) : (
            <HelpCircle size={14} className="mt-0.5 shrink-0 text-review" />
          )}
          <div className="min-w-0 flex-1">
            <p className="text-[13px] text-ink">{q.text}</p>
            {q.answer && (
              <p className="mt-0.5 font-mono text-[12px] text-muted">
                → {q.answer}
              </p>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
