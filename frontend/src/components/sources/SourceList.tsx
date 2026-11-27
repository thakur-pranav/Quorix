"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Database } from "lucide-react";

import { EmptyState } from "@/components/shared/EmptyState";
import type { SourceOut } from "@/lib/fastapi/types";

import { SourceCard } from "./SourceCard";

const POLL_MS = 2000;
const IN_PROGRESS = new Set(["queued", "crawling", "indexing"]);

interface SourceListProps {
  sources: SourceOut[];
  readOnly?: boolean; // the public demo: no reindex/delete (the server refuses them anyway)
}

export function SourceList({ sources, readOnly = false }: SourceListProps) {
  const router = useRouter();
  const busy = sources.some((s) => IN_PROGRESS.has(s.status));

  // Re-render from the server every 2 s while something is indexing; stop once all are done.
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => router.refresh(), POLL_MS);
    return () => clearInterval(timer);
  }, [busy, router]);

  if (sources.length === 0) {
    return (
      <EmptyState
        icon={Database}
        title="No knowledge sources connected"
        description="Add a website or upload document files to ground Quorix in your organisation's knowledge."
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {sources.map((source) => (
        <SourceCard key={source.id} source={source} readOnly={readOnly} onRefresh={() => router.refresh()} />
      ))}
    </div>
  );
}
