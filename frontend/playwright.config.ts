import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests drive a real browser against the real stack:
 * MongoDB + FastAPI on :8000 must already be running; the Next.js dev server is started here
 * if it isn't (reused if it is).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
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
