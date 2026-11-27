import { CircleDot, Minus, Repeat, Sparkles, TrendingDown } from "lucide-react";

import type { Trend } from "@/lib/fastapi/types";

interface InsightTrendBadgeProps {
  trend: Trend;
  className?: string;
}

/** Reference UI badge, extended to our five trend states (it had no baseline or recurring). */
const BADGES: Record<Trend, { label: string; icon: typeof Sparkles; className: string; hint: string }> = {
  emerging: {
    label: "Emerging",
    icon: Sparkles,
    className: "bg-purple-100 font-semibold text-[#6750A4] dark:bg-purple-950/60 dark:text-purple-300",
    hint: "New or growing fast from a small base",
  },
  recurring: {
    label: "Recurring",
    icon: Repeat,
    className: "bg-amber-50 font-semibold text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
    hint: "Holding at 70%+ of last month",
  },
  stable: {
    label: "Stable",
    icon: Minus,
    className: "bg-slate-100 font-medium text-slate-700 dark:bg-zinc-800 dark:text-slate-300",
    hint: "Between 50% and 70% of last month",
  },
  declining: {
    label: "Declining",
    icon: TrendingDown,
    className: "bg-slate-100 font-medium text-slate-600 dark:bg-zinc-800 dark:text-slate-400",
    hint: "Under half of last month",
  },
  baseline: {
    label: "Baseline",
    icon: CircleDot,
    className: "bg-slate-100 font-medium text-slate-600 dark:bg-zinc-800 dark:text-slate-400",
    hint: "First analysed month: nothing to compare with yet",
  },
};

export function InsightTrendBadge({ trend, className = "" }: InsightTrendBadgeProps) {
  const badge = BADGES[trend] ?? BADGES.stable;
  const Icon = badge.icon;
  return (
    <span title={badge.hint} className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs ${badge.className} ${className}`}>
      <Icon className="h-3 w-3" />
      {badge.label}
    </span>
  );
}
