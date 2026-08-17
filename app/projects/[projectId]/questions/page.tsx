"use client";

import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import * as api from "@/lib/api";
import { useQuestions } from "@/hooks/useProjectData";
import { QuestionCard } from "@/components/questions/QuestionCard";
import { QuestionHistory } from "@/components/questions/QuestionHistory";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/shared/EmptyState";

export default function QuestionsPage({
  params,
}: {
  params: { projectId: string };
}) {
  const { projectId } = params;
  const { data: questions, loading, refresh } = useQuestions(projectId);
  const [submitting, setSubmitting] = useState(false);

  const openQuestion = questions?.find((q) => q.status === "open");
  const history = questions?.filter((q) => q.status !== "open") ?? [];

  async function handleAnswer(answer: string) {
    if (!openQuestion) return;
    setSubmitting(true);
    try {
      await api.answerQuestion(projectId, openQuestion.id, answer);
      refresh();
    } catch {
      // Answer may have persisted despite a gateway timeout; sync UI from server.
      refresh();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="col-span-2">
        <p className="label-caps mb-2">Current question</p>
        {loading && (
          <p className="font-mono text-[11px] text-faint">Loading questions…</p>
        )}

        {!loading && openQuestion && (
          <QuestionCard
            question={openQuestion}
            onAnswer={handleAnswer}
            submitting={submitting}
          />
        )}

        {!loading && !openQuestion && (
          <Card>
            <EmptyState
              icon={CheckCircle2}
              title="Nothing left to ask"
              description="Every required field is asked one at a time. Your last answer determines what comes next."
            />
          </Card>
        )}
      </div>

      <Card className="h-fit">
        <CardHeader>
          <p className="text-sm font-medium">History</p>
        </CardHeader>
        <CardBody className="p-0 px-4">
          <QuestionHistory questions={history} />
        </CardBody>
      </Card>
    </div>
  );
}
