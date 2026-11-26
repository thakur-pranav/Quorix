import type { Column } from "@/components/charts/column-chart";
import type { OverviewOut } from "@/lib/fastapi/types";

type Delta = { text: string; direction: "up" | "down" | "flat" };

/** Change vs the previous month, as a relative % for counts. null when there is no previous month. */
export function countDelta(current: number, previous: number | undefined): Delta | null {
  if (previous === undefined) return null;
  if (previous === 0) return { text: "new vs last month", direction: current > 0 ? "up" : "flat" };
  const pct = Math.round(((current - previous) / previous) * 100);
  return { text: `${pct > 0 ? "+" : ""}${pct}% vs last month`, direction: pct > 0 ? "up" : pct < 0 ? "down" : "flat" };
}

/** Change of a 0..1 rate vs the previous month, in percentage points (not % of a %). */
export function pointsDelta(current: number, previous: number | undefined): Delta | null {
  if (previous === undefined) return null;
  const pts = Math.round((current - previous) * 100);
  return { text: `${pts > 0 ? "+" : ""}${pts} pts vs last month`, direction: pts > 0 ? "up" : pts < 0 ? "down" : "flat" };
}

/** Histogram bins → chart columns, labelled "0.45–0.50" and with a tooltip in words. */
export function histogramColumns(bins: OverviewOut["confidenceHistogram"]): Column[] {
  const width = bins.length > 0 ? 1 / bins.length : 0;
  return bins.map((b) => {
    const range = `${b.start.toFixed(2)}–${(b.start + width).toFixed(2)}`;
    return { key: range, label: range, value: b.count, tooltip: `${b.count} question${b.count === 1 ? "" : "s"} at confidence ${range}` };
  });
}
