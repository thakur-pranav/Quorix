"use client";

import { useCallback, useEffect, useState } from "react";

import { listSourcesAction } from "@/actions/intelligence";
import type { SourceOut } from "@/lib/fastapi/types";

import { AddSourceForms } from "./add-source-forms";
import { SourceCard } from "./source-card";

const POLL_MS = 2000;
const IN_PROGRESS = new Set(["queued", "crawling", "indexing"]);

export function SourcesView({ initialSources }: { initialSources: SourceOut[] }) {
  const [sources, setSources] = useState(initialSources);
  const busy = sources.some((s) => IN_PROGRESS.has(s.status));

  const refresh = useCallback(async () => {
    const result = await listSourcesAction();
    if (result.success) setSources(result.data);
  }, []);

  // Poll only while something is indexing; stop as soon as everything is ready or failed.
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [busy, refresh]);

  return (
    <>
      <AddSourceForms onAdded={refresh} />
      <section aria-labelledby="your-sources" className="flex flex-col gap-3">
        <h2 id="your-sources" className="text-lg font-medium">
          Your sources <span className="text-ink-muted">({sources.length})</span>
        </h2>
        {sources.length === 0 ? (
          <p className="rounded-card border border-dashed border-outline-soft px-5 py-10 text-center text-ink-muted">
            Nothing indexed yet. Add your help center URL above to get started.
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {sources.map((source) => (
              <li key={source.id}>
                <SourceCard source={source} onChanged={refresh} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
