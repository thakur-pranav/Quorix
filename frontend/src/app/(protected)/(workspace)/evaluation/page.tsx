import type { Metadata } from "next";
import { Calendar, CheckCircle2 } from "lucide-react";

import { EvaluationFailuresList } from "@/components/evaluation/EvaluationFailuresList";
import { EvaluationMetricCard } from "@/components/evaluation/EvaluationMetricCard";
import { BackendProblem } from "@/components/layout/backend-problem";
import { EmptyState } from "@/components/shared/EmptyState";
import { PageHeader } from "@/components/shared/PageHeader";
import { LocalTime } from "@/components/ui/local-time";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { EvaluationOut } from "@/lib/fastapi/types";
import { formatNumber } from "@/lib/formatters";

export const metadata: Metadata = { title: "Evaluation" };

export default async function EvaluationPage() {
  let evaluation: EvaluationOut | null = null;
  let error: BackendError | null = null;
  try {
    evaluation = await fastapi<EvaluationOut>("/evaluation/latest");
  } catch (e) {
    if (!(e instanceof BackendError)) throw e;
    if (e.status !== 404) error = e; // 404 = no run yet: the empty state below
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Evaluation" description="How good the answers are, scored by an independent AI judge." />

      {error && <BackendProblem error={error} />}

      {!error && !evaluation && (
        <EmptyState
          icon={CheckCircle2}
          title="No evaluation yet."
          description="Answer quality is scored offline by an independent AI judge: faithfulness to the docs, relevance to the question, and relevance of the retrieved passages. Results appear here after the next evaluation run."
        />
      )}

      {evaluation && (
        <>
          {/* Metadata Banner */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200/60 bg-[#F3EDF7]/30 px-5 py-3 text-xs dark:border-zinc-800 dark:bg-zinc-900/30">
            <span className="font-semibold text-slate-800 dark:text-slate-200">Evaluation Batch #{evaluation.id}</span>
            <div className="flex flex-wrap items-center gap-4 text-slate-500">
              <span>{formatNumber(evaluation.questionCount)} evaluated questions</span>
              <span>•</span>
              <span>
                {evaluation.failedJudgements} judgement{evaluation.failedJudgements === 1 ? "" : "s"} failed and left out of
                the averages (not counted as zero)
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5" />
                Ran <LocalTime iso={evaluation.ranAt} />
              </span>
            </div>
          </div>

          {/* Primary Quality Metrics */}
          <section aria-labelledby="eval-metrics-heading" className="space-y-3">
            <h2 id="eval-metrics-heading" className="text-base font-semibold text-slate-900 dark:text-white">
              Core Grounding Benchmarks
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <EvaluationMetricCard
                label="Faithfulness"
                score={evaluation.faithfulness}
                description="Are the answer's claims backed by the retrieved passages? Low means invented facts."
              />
              <EvaluationMetricCard
                label="Answer Relevance"
                score={evaluation.answerRelevance}
                description="Does the answer address the question asked? Low means evasive or off-topic."
              />
              <EvaluationMetricCard
                label="Context Relevance"
                score={evaluation.contextRelevance}
                description="Are the retrieved passages useful for the question? Low means noisy retrieval."
              />
            </div>
          </section>

          {/* Failure Cases */}
          <section aria-labelledby="eval-failures-heading" className="space-y-3">
            <div className="border-b border-slate-200/60 pb-2.5 dark:border-zinc-800">
              <h3 id="eval-failures-heading" className="text-base font-semibold text-slate-900 dark:text-white">
                Benchmark Failure Cases ({evaluation.failures.length})
              </h3>
              <p className="text-xs text-slate-500">The lowest scores below 0.50, worst first, with the judge&apos;s reason</p>
            </div>
            <EvaluationFailuresList failures={evaluation.failures} />
          </section>
        </>
      )}
    </div>
  );
}
