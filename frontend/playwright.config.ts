import { existsSync } from "node:fs";

import { defineConfig, devices } from "@playwright/test";

// Tests that need the seeded demo login read DEMO_EMAIL / DEMO_PASSWORD from .env.local (Node's
// built-in loader, no package). Without them, those tests skip themselves (e.g. in CI).
if (existsSync(".env.local")) process.loadEnvFile(".env.local");

/**
 * End-to-end tests drive a real browser against the real stack:
 * MongoDB + FastAPI on :8000 must already be running; the Next.js dev server is started here
 * if it isn't (reused if it is). In CI they run against the docker compose stack instead.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  // On CI also write an HTML report (with traces of failures), uploaded as an artifact.
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "corepack pnpm dev",
    url: "http://localhost:3000/login",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
