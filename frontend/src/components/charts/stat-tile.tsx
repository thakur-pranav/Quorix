import { ArrowDown, ArrowRight, ArrowUp } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Stat tile: label (sentence case) · value · optional delta vs a named period. The delta's
 * colour means "better or worse", which depends on the metric: more questions is neither,
 * a lower weak-match rate is better. It always carries an arrow and words, never colour alone.
 */
export function StatTile({
  label,
  value,
  delta,
  note,
}: {
  label: string;
  value: string;
  delta?: { text: string; direction: "up" | "down" | "flat"; good: "up" | "down" | "neither" };
  note?: string; // a plain caption, for context that isn't a change over time
}) {
  const tone =
    !delta || delta.direction === "flat" || delta.good === "neither"
      ? "text-ink-muted"
      : delta.direction === delta.good
        ? "text-success"
        : "text-danger";
  // SVG icons in currentColor: arrow characters fall back to colour emoji on some systems (Windows).
  const Arrow = delta ? { up: ArrowUp, down: ArrowDown, flat: ArrowRight }[delta.direction] : null;
  return (
    <div className="rounded-card bg-surface-2 p-4">
      <dt className="text-sm text-ink-muted">{label}</dt>
      <dd className="mt-1 text-2xl font-medium">{value}</dd>
      {delta && (
        <dd className={cn("mt-1 text-xs", tone)}>
          {Arrow && <Arrow aria-hidden className="mr-0.5 inline size-3 align-[-1px]" />}
          {delta.text}
        </dd>
      )}
      {note && <dd className="mt-1 text-xs text-ink-muted">{note}</dd>}
    </div>
  );
}
