import { expect, type Page } from "@playwright/test";

/** Register a brand-new user, which also creates a brand-new, empty organization. */
export async function signUpFreshUser(page: Page, company = "Empty Org Ltd"): Promise<string> {
  const email = `e2e-${Date.now()}-${Math.random().toString(16).slice(2, 8)}@example.com`;
  const password = "correct horse battery";
  await page.goto("/register");
  await page.getByLabel("Your name").fill("E2E Tester");
  await page.getByLabel("Company").fill(company);
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/sources$/);
  return email;
}

/** Sign in with the seeded demo login (scripts/create-demo-user.ts). */
export async function signInAsDemo(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(process.env.DEMO_EMAIL ?? "");
  await page.getByLabel("Password").fill(process.env.DEMO_PASSWORD ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

export const hasDemoLogin = Boolean(process.env.DEMO_EMAIL && process.env.DEMO_PASSWORD);
