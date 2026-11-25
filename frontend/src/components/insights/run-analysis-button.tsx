"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { runAnalyticsAction } from "@/actions/intelligence";
import { Button } from "@/components/ui/button";

const REFRESH_EVERY_MS = 5000;
const REFRESH_FOR_MS = 3 * 60_000;

/** Queues the batch, then refreshes the page for a few minutes so new results appear. */
export function RunAnalysisButton({ label = "Run analysis" }: { label?: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState<string | null>(null);
  const [watching, setWatching] = useState(false);

  useEffect(() => {
    if (!watching) return;
    const timer = setInterval(() => router.refresh(), REFRESH_EVERY_MS);
    const stop = setTimeout(() => setWatching(false), REFRESH_FOR_MS);
    return () => {
      clearInterval(timer);
      clearTimeout(stop);
    };
  }, [watching, router]);

  function run() {
    startTransition(async () => {
      const result = await runAnalyticsAction();
      if (!result.success) return setMessage(result.error);
      const periods = result.data.periods;
      setMessage(
        periods.length === 0
          ? "No questions logged yet, so there's nothing to analyse."
          : `Analysing ${periods.join(", ")}. Results appear here in a minute or two.`,
      );
      setWatching(periods.length > 0);
    });
  }

  return (
    <div className="flex flex-col items-start gap-2 sm:items-end">
      <Button variant="tonal" onClick={run} disabled={pending || watching}>
        {pending ? "Starting…" : watching ? "Analysing…" : label}
      </Button>
      {message && <p className="max-w-xs text-[13px] text-ink-muted sm:text-right">{message}</p>}
    </div>
  );
}
