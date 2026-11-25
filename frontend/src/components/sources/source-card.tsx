"use client";

import { FileText, Globe, LoaderCircle } from "lucide-react";
import { useState, useTransition } from "react";

import { deleteSourceAction, reindexSourceAction } from "@/actions/intelligence";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/card";
import type { SourceOut, SourceStatus } from "@/lib/fastapi/types";
import { cn, formatDateTime } from "@/lib/utils";

const STATUS: Record<SourceStatus, { label: string; className: string; busy?: boolean }> = {
  queued: { label: "Queued", className: "bg-surface-3 text-ink-muted", busy: true },
  crawling: { label: "Crawling", className: "bg-primary-soft text-on-primary-soft", busy: true },
  indexing: { label: "Indexing", className: "bg-primary-soft text-on-primary-soft", busy: true },
  ready: { label: "Ready", className: "bg-success-soft text-success" },
  failed: { label: "Failed", className: "bg-danger-soft text-danger" },
};

export function SourceCard({ source, onChanged }: { source: SourceOut; onChanged: () => Promise<void> }) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const status = STATUS[source.status];
  const Icon = source.kind === "website" ? Globe : FileText;

  function act(action: () => Promise<{ success: boolean; error?: string }>) {
    setError(null);
    startTransition(async () => {
      const result = await action();
      if (!result.success) setError(result.error ?? "Something went wrong.");
      setConfirming(false);
      await onChanged();
    });
  }

  return (
    <article className="rounded-card bg-surface-2 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <span className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-field bg-secondary-soft text-primary">
            <Icon className="size-5" aria-hidden />
          </span>
          <div className="min-w-0">
            <h3 className="truncate font-medium">{source.label}</h3>
            <p className="truncate text-sm text-ink-muted">{source.location}</p>
          </div>
        </div>
        <span className={cn("inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium", status.className)}>
          {status.busy && <LoaderCircle className="size-3.5 animate-spin" aria-hidden />}
          {status.label}
        </span>
      </div>

      <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-sm text-ink-muted">
        <div className="flex gap-1.5">
          <dt>Pages</dt>
          <dd className="font-medium text-ink">{source.pageCount}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt>Chunks</dt>
          <dd className="font-medium text-ink">{source.chunkCount}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt>Last indexed</dt>
          <dd className="text-ink">{formatDateTime(source.lastIndexedAt)}</dd>
        </div>
      </dl>

      {source.status === "failed" && source.error && <Alert className="mt-4">{source.error}</Alert>}
      {error && <Alert className="mt-4">{error}</Alert>}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" variant="outlined" disabled={pending || status.busy} onClick={() => act(() => reindexSourceAction(source.id))}>
          Re-index
        </Button>
        {confirming ? (
          <>
            <Button size="sm" variant="danger" disabled={pending} onClick={() => act(() => deleteSourceAction(source.id))}>
              Delete source and its chunks
            </Button>
            <Button size="sm" variant="text" disabled={pending} onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </>
        ) : (
          <Button size="sm" variant="danger" disabled={pending} onClick={() => setConfirming(true)}>
            Delete
          </Button>
        )}
      </div>
    </article>
  );
}
