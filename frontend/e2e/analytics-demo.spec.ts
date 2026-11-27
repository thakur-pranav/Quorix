import { expect, test } from "@playwright/test";

import { hasDemoLogin, signInAsDemo, signUpFreshUser } from "./helpers";

/**
 * The analytics pages with real data: the seeded demo organization (backend
 * scripts/seed_conversations.py + run_analysis, login from `pnpm demo:user`). Checks structure
 * and invariants, not exact numbers, so a re-seed doesn't break it. Skips without DEMO_EMAIL /
 * DEMO_PASSWORD (CI has no seeded data).
 */
test.skip(!hasDemoLogin, "needs the seeded demo login: DEMO_EMAIL and DEMO_PASSWORD in .env.local");

test.beforeEach(async ({ page }) => {
  await signInAsDemo(page);
});

test("Overview: headline numbers, the three charts and the live threshold", async ({ page }) => {
  await page.goto("/overview");
  await expect(page.getByRole("heading", { name: "This period", level: 1 })).toBeVisible();
  for (const label of ["Conversations", "Questions", "Active Topics", "Unanswered Rate", "Mean Confidence", "Emerging Topics"]) {
    await expect(page.getByText(label, { exact: true })).toBeVisible();
  }
  for (const chart of ["Query Volume Over Time", "Retrieval Confidence Trend", /^How Well The Docs Matched/]) {
    await expect(page.getByRole("heading", { name: chart })).toBeVisible();
  }
  // The histogram's decision lines come from the backend's live threshold (SVG labels).
  await expect(page.getByText(/^Refused below 0\.\d\d$/)).toBeVisible();
  await expect(page.getByText(/^Strong 0\.\d\d\+$/)).toBeVisible();
  await expect(page.locator(".recharts-bar-rectangle").first()).toBeVisible(); // bars drawn
});

test("Insights: ranked topics, and a topic's history across months", async ({ page }) => {
  await page.goto("/insights");
  const topics = page.locator('a[href^="/insights/ins_"]');
  await expect(topics.first()).toBeVisible();
  await expect(topics.first().getByText("#1", { exact: true })).toBeVisible(); // ranked from 1

  await topics.first().click();
  // Generous: in dev mode a route compiles on its first visit, which can take several seconds.
  await expect(page).toHaveURL(/\/insights\/ins_[0-9a-f]{12}$/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Topic Volume History" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Customer Questions \(\d+\)$/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Weakest Knowledge Matches" })).toBeVisible();
  await expect(page.getByText("Why this severity:")).toBeVisible();
});

test("Report: summary and categorised recommendations", async ({ page }) => {
  await page.goto("/report");
  await expect(page.getByRole("heading", { name: /^Report: \d{4}-\d{2}$/, level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Recommendations \(\d+\)$/ })).toBeVisible();
  await expect(page.getByText(/Product fix|Docs gap|FAQ|Customer follow-up/).first()).toBeVisible();
  await expect(page.getByText("Customer Inquiry Evidence").first()).toBeVisible();
});

test("Evaluation: three meters with valid values, and the judge's reasons", async ({ page }) => {
  await page.goto("/evaluation");
  const meters = page.getByRole("meter");
  await expect(meters).toHaveCount(3);
  for (const meter of await meters.all()) {
    const now = await meter.getAttribute("aria-valuenow");
    if (now !== null) expect(Number(now)).toBeGreaterThanOrEqual(0); // null = no usable judgements
    if (now !== null) expect(Number(now)).toBeLessThanOrEqual(1);
  }
  await expect(page.getByText(/judgements? failed and left out of\s+the averages/)).toBeVisible();

  const firstFailure = page.locator("ol > li").first();
  if (await firstFailure.isVisible()) {
    await expect(firstFailure.getByText("Reason:")).toBeVisible();
    await firstFailure.getByText("The answer it judged").click();
    await expect(firstFailure.locator("details[open] p")).not.toBeEmpty();
  }
});

test("another organization can't open a demo topic, even with its real id", async ({ page, browser }) => {
  await page.goto("/insights");
  const href = await page.locator('a[href^="/insights/ins_"]').first().getAttribute("href");
  expect(href).toMatch(/^\/insights\/ins_/);

  const stranger = await browser.newPage(); // a separate browser context: no demo session
  await signUpFreshUser(stranger, "Curious Competitor");
  await stranger.goto(href!);
  // The API scopes by the token's org, so for them the topic doesn't exist: not-found, no data.
  await expect(stranger.getByText("This page could not be found.")).toBeVisible();
  await expect(stranger.getByRole("heading", { name: "Topic Volume History" })).toHaveCount(0);
  await stranger.close();
});

test("the demo is read-only: a banner, and no controls that change data", async ({ page }) => {
  // The demo org must be listed in READ_ONLY_ORGS (as in production); the API refuses the writes
  // on its own (backend tests/test_read_only.py), this checks the UI doesn't offer them.
  await page.goto("/insights");
  await expect(page.getByText("read-only demo")).toBeVisible();
  await expect(page.getByRole("button", { name: /Run analytics/ })).toHaveCount(0);

  for (const path of ["/overview", "/report"]) {
    await page.goto(path);
    await expect(page.getByRole("button", { name: /Run analytics/ })).toHaveCount(0);
  }

  await page.goto("/sources");
  await expect(page.getByRole("heading", { name: /^Connected Knowledge \(\d+\)$/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Add Website|Upload/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Delete source" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Reindex" })).toHaveCount(0);
});
