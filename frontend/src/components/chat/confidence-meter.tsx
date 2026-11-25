import { cn, formatPercent } from "@/lib/utils";

/**
 * Retrieval confidence: how well the docs matched the question, measured BEFORE the answer was
 * written. Labelled by what it means for the user, not just a colour.
 */
export function ConfidenceMeter({ confidence, lowConfidence }: { confidence: number; lowConfidence: boolean }) {
  const level = lowConfidence ? "low" : confidence >= 0.7 ? "high" : "medium";
  const styles = {
    high: { bar: "bg-success", label: "Strong match in your docs" },
    medium: { bar: "bg-warning", label: "Partial match: check the sources" },
    low: { bar: "bg-danger", label: "Not found in your docs" },
  }[level];

  return (
    <div className="flex items-center gap-3 text-xs text-ink-muted">
      <div
        className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-3"
        role="meter"
        aria-label="Retrieval confidence"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(confidence * 100)}
      >
        <div className={cn("h-full rounded-full", styles.bar)} style={{ width: formatPercent(confidence) }} />
      </div>
      <span>
        <span className="font-medium text-ink">{formatPercent(confidence)}</span> · {styles.label}
      </span>
    </div>
  );
}
