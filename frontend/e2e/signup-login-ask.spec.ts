import { expect, test } from "@playwright/test";

/**
 * The ROADMAP Day 4 journey: sign up → (sign out) → log in → ask a question.
 * A brand-new workspace has no sources, so the honest answer is "nothing indexed yet",
 * which proves the full chain: browser → server action → signed service token → FastAPI.
 */
test("sign up, sign out, log in and ask a question", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  const password = "correct horse battery";

  await page.goto("/register");
  await page.getByLabel("Full name").fill("E2E Tester");
  await page.getByLabel("Organization name").fill("E2E Corp");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page).toHaveURL(/\/sources$/);
  await expect(page.getByRole("heading", { name: "Sources", exact: true })).toBeVisible();
  await expect(page.getByText("E2E Tester")).toBeVisible(); // the navbar shows who's signed in

  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);

  // Protected pages bounce to login without a session.
  await page.goto("/ask");
  await expect(page).toHaveURL(/\/login$/);

  // A wrong password shows the generic message.
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("wrong password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Invalid email or password.")).toBeVisible();

  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/overview$/);

  await page.getByRole("navigation", { name: "Workspace secondary navigation" }).getByRole("link", { name: "Ask" }).click();
  await page.getByLabel("Your question").fill("How do refunds work?");
  await page.getByRole("button", { name: "Send message" }).click();

  await expect(page.getByText("How do refunds work?")).toBeVisible();
  await expect(page.getByText(/Nothing has been indexed yet/)).toBeVisible({ timeout: 30_000 });
});
