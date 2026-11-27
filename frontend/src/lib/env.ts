import "server-only";

import { z } from "zod";

/**
 * Server environment, validated once. Called from instrumentation.ts at server startup, so a
 * missing or short secret stops the app before it serves a single request (CLAUDE.md rule:
 * no fallback secrets, at least 32 characters).
 */
const secret = (name: string) =>
  z.string({ error: `${name} is required` }).min(32, `${name} must be at least 32 characters`);

const schema = z
  .object({
    NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
    MONGODB_URI: z.string({ error: "MONGODB_URI is required" }).min(1),
    AUTH_SECRET: secret("AUTH_SECRET"),
    BACKEND_JWT_SECRET: secret("BACKEND_JWT_SECRET"),
    FASTAPI_BASE_URL: z.url().optional(),
    // Organizations that may read and chat but not change anything (the public demo). Same
    // comma-separated list as the backend's READ_ONLY_ORGS, which is the real enforcement.
    READ_ONLY_ORGS: z.string().default(""),
  })
  .refine((env) => env.AUTH_SECRET !== env.BACKEND_JWT_SECRET, {
    message: "AUTH_SECRET and BACKEND_JWT_SECRET must be different",
  })
  .refine((env) => env.NODE_ENV !== "production" || env.FASTAPI_BASE_URL, {
    message: "FASTAPI_BASE_URL is required in production",
  });

export type Env = z.infer<typeof schema> & { FASTAPI_BASE_URL: string };

let cached: Env | undefined;

export function getEnv(): Env {
  if (cached) return cached;
  const parsed = schema.safeParse(process.env);
  if (!parsed.success) {
    // Messages name the variable and the rule, never the value.
    throw new Error(`Invalid environment:\n${z.prettifyError(parsed.error)}`);
  }
  cached = {
    ...parsed.data,
    FASTAPI_BASE_URL: parsed.data.FASTAPI_BASE_URL ?? "http://127.0.0.1:8000",
  };
  return cached;
}

export const isProduction = () => process.env.NODE_ENV === "production";
