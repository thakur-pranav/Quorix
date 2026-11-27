import { formatConfidence } from "@/lib/formatters";

/**
 * Retrieval confidence: how well the docs matched the question, measured BEFORE the answer was
 * written. Below the backend threshold the backend refuses (`lowConfidence`). Between it and
 * 0.62 covered and off-topic questions overlap (docs/EXPERIMENTS.md), so those answers are
 * flagged for the reader to check. The words carry the meaning, not just the colour.
 */
export const STRONG_MATCH = 0.62;

interface ConfidenceMeterProps {
  confidence: number;
  lowConfidence: boolean;
}

export function ConfidenceMeter({ confidence, lowConfidence }: ConfidenceMeterProps) {
  const level = lowConfidence ? "low" : confidence >= STRONG_MATCH ? "high" : "medium";
  const style = {
    high: { bar: "bg-emerald-500", label: "Strong match in your docs" },
    medium: { bar: "bg-amber-500", label: "Weak match: check the sources" },
    low: { bar: "bg-rose-500", label: "Not found in your docs" },
  }[level];
  const pct = Math.min(100, Math.max(0, Math.round(confidence * 100)));

  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
      <span className="font-medium text-slate-600 dark:text-slate-300">Retrieval confidence:</span>
      <div
        role="meter"
        aria-label="Retrieval confidence"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200 dark:bg-zinc-700"
      >
        <div style={{ width: `${pct}%` }} className={`h-full rounded-full transition-all duration-300 ${style.bar}`} />
      </div>
      <span className="font-semibold text-slate-700 dark:text-slate-200">{formatConfidence(confidence)}</span>
      <span>· {style.label}</span>
    </div>
  );
}
