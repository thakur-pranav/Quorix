"use client";

import { LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { pingBackendAction } from "@/actions/intelligence";

const POLL_MS = 5_000;
const GIVE_UP_MS = 3 * 60_000;

/**
 * Shown instead of an error while the backend wakes up (a free host stops it when idle). Checks
 * every 5 s through a server action and reloads the page's data as soon as it answers. After 3
 * minutes it stops polling and offers a manual retry, instead of polling forever.
 */
export function WakingUp() {
  const router = useRouter();
  const [gaveUp, setGaveUp] = useState(false);
  const [attempt, setAttempt] = useState(0); // bumped by "Try again" to restart the polling

  useEffect(() => {
    const started = Date.now();
    let stopped = false;
    const timer = setInterval(async () => {
      if (await pingBackendAction().catch(() => false)) {
        clearInterval(timer);
        if (!stopped) router.refresh(); // re-run the server components: real data replaces this
      } else if (Date.now() - started > GIVE_UP_MS) {
        clearInterval(timer);
        if (!stopped) setGaveUp(true);
      }
    }, POLL_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [router, attempt]);

  if (gaveUp) {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3 text-sm text-amber-800 dark:border-amber-950 dark:bg-amber-950/30 dark:text-amber-200">
        <span>The analysis service still isn&apos;t answering.</span>
        <button
          type="button"
          onClick={() => {
            setGaveUp(false);
            setAttempt((n) => n + 1);
          }}
          className="inline-flex items-center rounded-full border border-amber-300 bg-white px-3.5 py-1.5 text-xs font-medium text-amber-800 shadow-xs transition hover:bg-amber-50 active:scale-95"
        >
          Try again
        </button>
      </div>
    );
  }
  return (
    <div role="status" className="flex items-center gap-3 rounded-3xl border border-slate-200/70 bg-[#F3EDF7]/40 px-5 py-4 text-sm text-slate-700 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-slate-300">
      <LoaderCircle aria-hidden className="size-4 shrink-0 animate-spin text-[#6750A4]" />
      <span>
        Waking up the backend (about 30 s). It sleeps when nobody has used it for a while; this page will load
        by itself.
      </span>
    </div>
  );
}
