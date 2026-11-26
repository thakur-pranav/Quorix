import type { Metadata } from "next";

import { Alert, Card } from "@/components/ui/card";
import { LocalTime } from "@/components/ui/local-time";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { EvaluationMetric, EvaluationOut } from "@/lib/fastapi/types";
import { cn, formatPercent } from "@/lib/utils";

export const metadata: Metadata = { title: "Evaluation" };

const METRICS: { key: EvaluationMetric; field: "faithfulness" | "answerRelevance" | "contextRelevance"; name: string; tests: string }[] = [
  { key: "faithfulness", field: "faithfulness", name: "Faithfulness", tests: "Are the answer's claims backed by the retrieved passages? Low means invented facts." },
  { key: "answer_relevance", field: "answerRelevance", name: "Answer relevance", tests: "Does the answer address the question asked? Low means evasive or off-topic." },
  { key: "context_relevance", field: "contextRelevance", name: "Context relevance", tests: "Are the retrieved passages useful for the question? Low means noisy retrieval." },
];
const METRIC_NAME = Object.fromEntries(METRICS.map((m) => [m.key, m.name])) as Record<EvaluationMetric, string>;

/** The meter's fill carries the verdict, and the word says it too: never colour alone. */
function verdict(score: number) {
  if (score >= 0.8) return { word: "good", fill: "bg-primary", track: "bg-primary-soft" };
  if (score >= 0.5) return { word: "needs work", fill: "bg-warning", track: "bg-warning-soft" };
  return { word: "poor", fill: "bg-danger", track: "bg-danger-soft" };
}

export default async function EvaluationPage() {
  let run: EvaluationOut | null = null;
  let error: string | null = null;
  try {
    run = await fastapi<EvaluationOut>("/evaluation/latest");
  } catch (e) {
    if (!(e instanceof BackendError)) throw e;
    if (e.status !== 404) error = e.message; // 404 = no run yet: the empty state below
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[28px] font-medium tracking-tight">Evaluation</h1>
        <p className="mt-1 text-ink-muted">How good the answers are, scored by an independent AI judge.</p>
      </div>

      {error && <Alert>{error}</Alert>}
      {!error && !run && (
        <p className="rounded-card border border-dashed border-outline-soft px-5 py-10 text-center text-ink-muted">
          No evaluation yet. Run <code className="text-sm">python -m scripts.run_evaluation</code> on the backend.
        </p>
      )}

      {run && (
        <>
          <Card className="flex flex-col gap-5">
            <dl className="flex flex-col gap-5">
              {METRICS.map((m) => {
                const score = run[m.field];
                const v = score === null ? null : verdict(score);
                return (
                  <div key={m.key} className="grid gap-x-6 gap-y-1.5 sm:grid-cols-[12rem_1fr_9rem] sm:items-center">
                    <div>
                      <dt className="font-medium">{m.name}</dt>
                      <dd className="text-xs text-ink-muted">{m.tests}</dd>
                    </div>
                    <dd
                      className={cn("h-2 overflow-hidden rounded-full", v?.track ?? "bg-surface-3")}
                      role="meter"
                      aria-label={m.name}
                      aria-valuemin={0}
                      aria-valuemax={1}
                      aria-valuenow={score ?? undefined}
                    >
                      {v && score !== null && <div className={cn("h-full rounded-full", v.fill)} style={{ width: `${score * 100}%` }} />}
                    </dd>
                    <dd className="text-sm sm:text-right">
                      {score === null ? (
                        <span className="text-ink-muted">no usable judgements</span>
                      ) : (
                        <>
                          <span className="text-lg font-medium">{score.toFixed(2)}</span>
                          <span className="ml-1.5 whitespace-nowrap text-ink-muted">{v?.word}</span>
                        </>
                      )}
                    </dd>
                  </div>
                );
              })}
            </dl>
            <p className="border-t border-outline-soft/60 pt-4 text-sm text-ink-muted">
              {run.questionCount} questions · {run.failedJudgements} judgement{run.failedJudgements === 1 ? "" : "s"} failed
              and left out of the averages (not counted as zero) · run <LocalTime iso={run.ranAt} />
            </p>
          </Card>

          <section className="flex flex-col gap-3">
            <div>
              <h2 className="text-lg font-medium">Worst answers</h2>
              <p className="text-sm text-ink-muted">
                The lowest scores below 0.50 (up to {run.failures.length}), worst first, with the judge&apos;s reason.
              </p>
            </div>
            {run.failures.length === 0 && <p className="text-ink-muted">No score fell below 0.50.</p>}
            <ol className="flex flex-col gap-2">
              {run.failures.map((f, i) => (
                <li key={`${f.question}-${f.metric}`} className="rounded-card bg-surface-2 p-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <p className="font-medium">
                      <span className="mr-2 text-ink-muted">{i + 1}.</span>
                      {f.question}
                    </p>
                    <p className="text-sm">
                      {METRIC_NAME[f.metric]} <span className="font-medium">{f.score.toFixed(2)}</span>
                    </p>
                  </div>
                  <p className="mt-2 text-sm">
                    <span className="text-ink-muted">Judge: </span>
                    {f.reason || "no reason given"}
                  </p>
                  <details className="mt-2 text-sm">
                    <summary className="cursor-pointer text-ink-muted hover:text-ink">
                      The answer it judged · retrieval confidence {formatPercent(f.confidence)}
                    </summary>
                    <p className="mt-2 whitespace-pre-line rounded-field bg-surface px-3 py-2 leading-relaxed">{f.answer}</p>
                  </details>
                </li>
              ))}
            </ol>
          </section>
        </>
      )}
    </div>
  );
}
