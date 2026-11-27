import { AlertCircle, CheckCircle2, Clock, Loader2 } from "lucide-react";

import type { SourceStatus } from "@/lib/fastapi/types";

interface SourceStatusBadgeProps {
  status: SourceStatus;
  className?: string;
}

/** Reference UI badge, mapped to our ingestion states (queued -> crawling -> indexing -> ready | failed). */
const BADGES: Record<SourceStatus, { label: string; className: string; icon: typeof Clock; spin?: boolean }> = {
  queued: { label: "Queued", icon: Clock, className: "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300" },
  crawling: { label: "Crawling", icon: Loader2, spin: true, className: "bg-purple-50 text-[#6750A4] dark:bg-purple-950/50 dark:text-purple-300" },
  indexing: { label: "Indexing", icon: Loader2, spin: true, className: "bg-purple-50 text-[#6750A4] dark:bg-purple-950/50 dark:text-purple-300" },
  ready: { label: "Ready", icon: CheckCircle2, className: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300" },
  failed: { label: "Failed", icon: AlertCircle, className: "bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300" },
};

export function SourceStatusBadge({ status, className = "" }: SourceStatusBadgeProps) {
  const badge = BADGES[status];
  const Icon = badge.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.className} ${className}`}>
      <Icon className={`h-3 w-3 ${badge.spin ? "animate-spin" : ""}`} />
      {badge.label}
    </span>
  );
}
