import { AlertTriangle, BookOpen } from "lucide-react";
import type { TopicDetailOut } from "@/lib/fastapi/types";
import { formatPercent } from "@/lib/formatters";

interface InsightEvidenceProps {
  weakestChunks: TopicDetailOut["weakestChunks"];
}

export function InsightEvidence({ weakestChunks }: InsightEvidenceProps) {
  if (!weakestChunks || weakestChunks.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-200/70 bg-white/40 p-4 text-xs text-slate-500">
        No weak knowledge chunks flagged for this topic.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {weakestChunks.map((chunk, idx) => (
        <div
          key={`${chunk.chunkId}-${idx}`}
          className="rounded-2xl border border-amber-200/80 bg-amber-50/40 p-4 text-xs dark:border-amber-950/60 dark:bg-amber-950/20"
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 font-medium text-slate-900 dark:text-white">
              <BookOpen className="h-4 w-4 text-[#7D5260]" />
              <span>{chunk.sourceLabel}</span>
              {chunk.headingPath &&
                (chunk.url ? (
                  <a href={chunk.url} target="_blank" rel="noreferrer" className="text-slate-500 underline-offset-2 hover:text-[#6750A4] hover:underline">
                    / {chunk.headingPath}
                  </a>
                ) : (
                  <span className="text-slate-500">/ {chunk.headingPath}</span>
                ))}
              <span className="text-[11px] font-normal text-slate-400">retrieved {chunk.timesRetrieved}×</span>
            </div>

            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800 dark:bg-amber-900/60 dark:text-amber-200">
              <AlertTriangle className="h-3 w-3" />
              Avg match: {formatPercent(chunk.meanSimilarity)}
            </span>
          </div>

          <blockquote className="mt-2.5 rounded-xl bg-white/70 p-3 italic text-slate-700 dark:bg-zinc-900/60 dark:text-slate-300">
            &ldquo;{chunk.excerpt}&rdquo;
          </blockquote>
        </div>
      ))}
    </div>
  );
}
