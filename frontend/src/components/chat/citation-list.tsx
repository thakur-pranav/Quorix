import type { Citation } from "@/lib/fastapi/types";
import { formatPercent } from "@/lib/utils";

/** Numbered like the [n] markers in the answer, so each claim can be traced to its passage. */
export function CitationList({ citations }: { citations: Citation[] }) {
  return (
    <details className="group rounded-field bg-surface px-4 py-2.5 text-sm">
      <summary className="cursor-pointer select-none font-medium text-ink-muted marker:text-outline">
        {citations.length} {citations.length === 1 ? "source" : "sources"}
      </summary>
      <ol className="mt-3 flex flex-col gap-3">
        {citations.map((citation, index) => (
          <li key={citation.chunkId} className="flex gap-3">
            <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded bg-secondary-soft text-[11px] font-medium text-on-secondary-soft">
              {index + 1}
            </span>
            <div className="min-w-0">
              <p className="text-ink">
                <span className="font-medium">{citation.sourceLabel}</span>
                <span className="text-ink-muted"> · {citation.headingPath}</span>
                <span className="ml-2 text-xs text-ink-muted">{formatPercent(citation.similarity)} match</span>
              </p>
              <p className="mt-1 line-clamp-3 text-ink-muted">{citation.excerpt}</p>
            </div>
          </li>
        ))}
      </ol>
    </details>
  );
}
