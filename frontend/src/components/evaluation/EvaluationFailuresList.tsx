import { AlertTriangle, CheckCircle } from "lucide-react";

import type { EvaluationMetric, EvaluationOut } from "@/lib/fastapi/types";
import { formatPercent } from "@/lib/formatters";

interface EvaluationFailuresListProps {
  failures: EvaluationOut["failures"];
}

const METRIC_NAME: Record<EvaluationMetric, string> = {
  faithfulness: "Faithfulness",
  answer_relevance: "Answer relevance",
  context_relevance: "Context relevance",
};

/** The worst judgements (score below 0.5), lowest first, with the judge's reason and the answer judged. */
export function EvaluationFailuresList({ failures }: EvaluationFailuresListProps) {
  if (failures.length === 0) {
    return (
      <div className="flex items-center gap-2.5 rounded-3xl border border-emerald-200 bg-emerald-50/60 p-5 text-xs text-emerald-800 dark:border-emerald-950/60 dark:bg-emerald-950/20 dark:text-emerald-300">
        <CheckCircle className="h-5 w-5 shrink-0 text-emerald-600" />
        <span>No evaluation failures detected. All test queries met benchmark quality thresholds.</span>
      </div>
    );
  }

  return (
    <ol className="space-y-3">
      {failures.map((item) => (
        <li
          key={`${item.question}-${item.metric}`}
          className="rounded-2xl border border-rose-200/80 bg-rose-50/40 p-4 text-xs dark:border-rose-950/60 dark:bg-rose-950/20"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
              <div>
                <p className="font-semibold text-rose-900 dark:text-rose-200">{item.question}</p>
                <p className="mt-1 text-slate-600 dark:text-slate-300">
                  <strong className="text-slate-700 dark:text-slate-200">Reason:</strong> {item.reason || "no reason given"}
                </p>
              </div>
            </div>

            <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 text-[11px]">
              <span className="rounded-md bg-white/80 px-2 py-0.5 font-semibold text-rose-700 dark:bg-zinc-800">
                {METRIC_NAME[item.metric]}: {formatPercent(item.score)}
              </span>
              <span className="rounded-md bg-white/80 px-2 py-0.5 text-slate-600 dark:bg-zinc-800">
                Retrieval: {formatPercent(item.confidence)}
              </span>
            </div>
          </div>

          <details className="mt-2.5 pl-6">
            <summary className="cursor-pointer text-slate-500 hover:text-slate-800 dark:hover:text-slate-200">The answer it judged</summary>
            <p className="mt-2 whitespace-pre-line rounded-xl bg-white/70 p-3 leading-relaxed text-slate-700 dark:bg-zinc-900/60 dark:text-slate-300">
              {item.answer}
            </p>
          </details>
        </li>
      ))}
    </ol>
  );
}
