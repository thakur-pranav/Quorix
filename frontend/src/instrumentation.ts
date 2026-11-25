/**
 * Runs once when the Next.js server starts. Validating the environment here makes a bad
 * secret a startup crash instead of a 500 on some later request.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { getEnv } = await import("@/lib/env");
    getEnv();
  }
}
