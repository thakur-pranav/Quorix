import type { Trend } from "@/lib/fastapi/types";
import { cn } from "@/lib/utils";

const TRENDS: Record<Trend, { label: string; className: string; hint: string }> = {
  emerging: { label: "Emerging", className: "bg-warning-soft text-warning", hint: "New or growing fast from a small base" },
  recurring: { label: "Recurring", className: "bg-secondary-soft text-on-secondary-soft", hint: "Holding at 70%+ of last month" },
  stable: { label: "Stable", className: "bg-surface-3 text-ink-muted", hint: "Between 50% and 70% of last month" },
  declining: { label: "Declining", className: "bg-success-soft text-success", hint: "Under half of last month" },
  baseline: { label: "Baseline", className: "bg-surface-3 text-ink-muted", hint: "First analysed month: nothing to compare with yet" },
};

export function TrendBadge({ trend, className }: { trend: Trend; className?: string }) {
  const t = TRENDS[trend];
  return (
    <span title={t.hint} className={cn("inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium", t.className, className)}>
      {t.label}
    </span>
  );
}

export function formatGrowth(growth: number, previous: number): string {
  if (previous === 0) return "new";
  const pct = Math.round(growth * 100);
  return `${pct > 0 ? "+" : ""}${pct}%`;
}
