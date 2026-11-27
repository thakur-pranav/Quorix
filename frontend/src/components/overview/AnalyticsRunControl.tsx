"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Play, RefreshCw } from "lucide-react";
import { runAnalyticsAction } from "@/actions/intelligence";

const REFRESH_MS = 10_000;
const WATCH_MS = 3 * 60_000; // the batch runs in the background on FastAPI: refresh while it does

/** Queues the analysis for the whole window (it has no per-period option), then refreshes. */
export function AnalyticsRunControl() {
  const router = useRouter();
  const [isRunning, setIsRunning] = useState(false);
  const [watching, setWatching] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!watching) return;
    const timer = setInterval(() => router.refresh(), REFRESH_MS);
    const stop = setTimeout(() => setWatching(false), WATCH_MS);
    return () => {
      clearInterval(timer);
      clearTimeout(stop);
    };
  }, [watching, router]);

  async function handleRunAnalytics() {
    setIsRunning(true);
    setStatusMessage("Starting analytics batch…");

    try {
      const result = await runAnalyticsAction();
      if (result.success) {
        setStatusMessage(
          result.data.periods.length === 0
            ? "No questions to analyse yet."
            : "Analytics started. Results will appear once processing completes."
        );
        setWatching(result.data.periods.length > 0);
      } else {
        setStatusMessage(result.error || "Unable to start analytics.");
      }
    } catch {
      setStatusMessage("Failed to trigger analytics.");
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1.5 sm:flex-row sm:items-center">
      {statusMessage && (
        <span className="text-xs text-slate-600 dark:text-slate-400">
          {statusMessage}
        </span>
      )}

      <button
        type="button"
        onClick={handleRunAnalytics}
        disabled={isRunning}
        className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3.5 py-1.5 text-xs font-medium text-slate-700 shadow-xs transition hover:bg-slate-50 hover:text-slate-900 disabled:opacity-50 active:scale-95 dark:border-zinc-700 dark:bg-zinc-800 dark:text-slate-200 dark:hover:bg-zinc-750"
      >
        {isRunning ? (
          <RefreshCw className="h-3.5 w-3.5 animate-spin text-[#6750A4]" />
        ) : (
          <Play className="h-3.5 w-3.5 text-[#6750A4]" />
        )}
        <span>{isRunning ? "Starting batch…" : "Run analytics"}</span>
      </button>
    </div>
  );
}
