import { expect, test } from "@playwright/test";

import { signUpFreshUser } from "./helpers";

/**
 * A brand-new organization has no questions, topics, reports or evaluation runs. Every analytics
 * page must show its empty state, never an error, and never another organization's data
 * (tenant isolation, checked in a real browser). Needs no seeded data, so it also runs in CI.
 */
test("a new organization sees empty states, not errors or other tenants' data", async ({ page }) => {
  await signUpFreshUser(page);
  // A normal org gets the write controls (the demo spec checks they're absent for the demo org).
  await expect(page.getByRole("button", { name: "Add website" })).toBeVisible();
  await expect(page.getByText("read-only demo")).toHaveCount(0);
  const nav = page.getByRole("navigation", { name: "Workspace" });

  await nav.getByRole("link", { name: "Overview" }).click();
  await expect(page.getByRole("heading", { name: "Overview", level: 1 })).toBeVisible();
  await expect(page.getByText("No questions yet.")).toBeVisible();

  await nav.getByRole("link", { name: "Insights" }).click();
  await expect(page.getByRole("heading", { name: "Insights", level: 1 })).toBeVisible();
  await expect(page.getByText(/No topics yet/)).toBeVisible();
  await expect(page.locator('a[href^="/insights/ins_"]')).toHaveCount(0); // no one else's topics

  await nav.getByRole("link", { name: "Report" }).click();
  await expect(page.getByText(/No report yet/)).toBeVisible();

  await nav.getByRole("link", { name: "Evaluation" }).click();
  await expect(page.getByText(/No evaluation yet/)).toBeVisible();
  await expect(page.getByRole("meter")).toHaveCount(0);

  // No backend error on any of them. Scoped to <main>: Next.js adds its own (empty) role="alert"
  // route announcer for screen readers outside it.
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
});

test("a topic id this organization doesn't own shows not-found", async ({ page }) => {
  await signUpFreshUser(page);
  await page.goto("/insights/ins_000000000000");
  // The API answered 404, so the page renders Next's not-found UI. The HTTP status is still 200:
  // loading.tsx makes the page stream, and the 200 header is sent before notFound() runs.
  await expect(page.getByText("This page could not be found.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "History" })).toHaveCount(0);
});
