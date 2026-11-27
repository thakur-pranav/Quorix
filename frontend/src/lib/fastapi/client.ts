import "server-only";

import { requireUser } from "@/lib/auth";
import { getEnv } from "@/lib/env";
import { signServiceToken } from "@/lib/fastapi/token";

/**
 * The ONLY way the app talks to FastAPI, and it only runs on the server ("server-only" makes
 * importing it from a Client Component a build error). The browser never sees the backend URL
 * or the service secret.
 */

const TIMEOUT_MS = 60_000; // chat can include LLM retries (1 + 2 + 4 s backoff)

export class BackendError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "BackendError";
  }
}

type RequestOptions = { method?: "GET" | "POST" | "DELETE"; json?: unknown; formData?: FormData };

/** Turn FastAPI's `detail` (a string, or a 422 list of {loc, msg}) into one readable sentence. */
export function readableError(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((issue: { loc?: unknown[]; msg?: string }) => {
        const field = issue.loc?.at(-1);
        return field && field !== "body" ? `${String(field)}: ${issue.msg}` : String(issue.msg);
      })
      .join("; ");
  }
  if (status === 401) return "Your session with the analysis service expired. Please sign in again.";
  if (status === 404) return "Not found.";
  if (status >= 500) return "The analysis service had a problem. Please try again.";
  return `Request failed (${status}).`;
}

/**
 * The backend is asleep or starting: a free host stops it after a while idle, and the proxy in
 * front answers 502/503/504 (or the connection fails) until it's up again (~30 s).
 */
export const WAKING_UP_STATUSES = new Set([502, 503, 504]);
const WAKING_UP_MESSAGE = "The analysis service is waking up (about 30 seconds). Please try again in a moment.";

export function isWakingUp(error: unknown): boolean {
  return error instanceof BackendError && WAKING_UP_STATUSES.has(error.status);
}

export async function fastapi<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const user = await requireUser(); // defence in depth: no user, no backend call
  const headers: Record<string, string> = {
    Authorization: `Bearer ${await signServiceToken(user)}`,
  };
  let body: BodyInit | undefined;
  if (options.formData) {
    body = options.formData; // fetch sets the multipart boundary itself
  } else if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }

  let response: Response;
  try {
    response = await fetch(`${getEnv().FASTAPI_BASE_URL}/api${path}`, {
      method: options.method ?? "GET",
      headers,
      body,
      cache: "no-store", // per-user, per-org data: never cache
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    throw new BackendError(503, WAKING_UP_MESSAGE); // unreachable: asleep, starting or restarting
  }

  if (response.status === 204) return undefined as T;
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    // A proxy's 502-504 page isn't FastAPI JSON: say what it almost always means.
    const message = WAKING_UP_STATUSES.has(response.status) && payload === null ? WAKING_UP_MESSAGE : readableError(response.status, payload);
    throw new BackendError(response.status, message);
  }
  return payload as T;
}
