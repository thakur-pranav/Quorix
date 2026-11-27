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

test("Overview: headline numbers, both charts and their table views", async ({ page }) => {
  await page.goto("/overview");
  await expect(page.getByRole("heading", { name: "Overview", level: 1 })).toBeVisible();
  for (const label of ["Questions this month", "Conversations", "Weak doc match", "Mean confidence"]) {
    await expect(page.getByText(label, { exact: true })).toBeVisible();
  }

  // Both charts are labelled images, each with a table view behind "Show as table".
  const charts = page.getByRole("img", { name: /Exact values in the table below/ });
  await expect(charts).toHaveCount(2);
  const toggles = page.getByText("Show as table");
  await toggles.first().click();
  const months = page.locator("details[open] tbody tr");
  expect(await months.count()).toBeGreaterThanOrEqual(1);
  await expect(months.first()).toContainText(/\d{4}-\d{2}/);

  // The histogram's decision lines come from the backend's live threshold.
  await expect(page.getByText(/^Refused below 0\.\d\d$/)).toBeVisible();
  await expect(page.getByText(/^Strong 0\.\d\d\+$/)).toBeVisible();

  // Keyboard users get the same tooltip as mouse users.
  const firstMonth = page.locator('[tabindex="0"][aria-label*="questions, mean confidence"]').first();
  await firstMonth.focus();
  await expect(firstMonth.getByRole("tooltip")).toBeVisible();
});

test("Insights: ranked topics, and a topic's history across months", async ({ page }) => {
  await page.goto("/insights");
  const topics = page.locator('a[href^="/insights/ins_"]');
  await expect(topics.first()).toBeVisible();
  await expect(topics.first().locator(":scope > span").first()).toHaveText("1"); // ranked from 1

  await topics.first().click();
  // Generous: in dev mode a route compiles on its first visit, which can take several seconds.
  await expect(page).toHaveURL(/\/insights\/ins_[0-9a-f]{12}$/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "History" })).toBeVisible();
  await expect(page.getByText("Pages to improve")).toBeVisible();
  await expect(page.getByText("What customers asked")).toBeVisible();
});

test("Report: summary and categorised recommendations", async ({ page }) => {
  await page.goto("/report");
  await expect(page.getByRole("heading", { name: /^Report: \d{4}-\d{2}$/, level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recommendations" })).toBeVisible();
  await expect(page.getByText(/Product fix|Docs gap|FAQ|Customer follow-up/).first()).toBeVisible();
  await expect(page.getByText(/questions behind this/).first()).toBeVisible();
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
  await expect(page.getByText(/judgements? failed and left out of the averages/)).toBeVisible();

  const firstFailure = page.locator("ol > li").first();
  if (await firstFailure.isVisible()) {
    await expect(firstFailure.getByText(/^Judge:/)).toBeVisible();
    await firstFailure.getByText(/The answer it judged/).click();
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
  await expect(stranger.getByRole("heading", { name: "History" })).toHaveCount(0);
  await stranger.close();
});
