"use client";

import { useEffect, useState } from "react";

/**
 * A timestamp in the viewer's own timezone. The server (UTC on Vercel) and the browser (e.g. IST)
 * would format the same instant differently, a hydration mismatch. So the first render shows a
 * stable UTC string, and the local one replaces it after mount.
 */
export function LocalTime({ iso, fallback = "never" }: { iso: string | null; fallback?: string }) {
  const [local, setLocal] = useState<string | null>(null);

  useEffect(() => {
    if (!iso) return;
    const formatted = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
    setLocal(formatted); // eslint-disable-line react-hooks/set-state-in-effect -- runs once per value, after mount
  }, [iso]);

  if (!iso) return <>{fallback}</>;
  return <time dateTime={iso}>{local ?? `${iso.slice(0, 16).replace("T", " ")} UTC`}</time>;
}
