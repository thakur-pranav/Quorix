import { expect, test } from "@playwright/test";

/**
 * The Day 4 "Done when", in a real browser: sign up → add a docs site → watch it reach
 * "Ready" → get a cited answer. Crawls a real website (~3 minutes), so it's opt-in:
 *   E2E_FULL_CRAWL=1 DOCS_URL=https://docs.github.com/en/billing corepack pnpm test:e2e full-crawl
 * Set SCREENSHOT_DIR to save screenshots of each step.
 */
const docsUrl = process.env.DOCS_URL ?? "https://docs.github.com/en/billing";
const question = process.env.QUESTION ?? "My credit card was declined. What should I do?";
const shots = process.env.SCREENSHOT_DIR;

test.skip(!process.env.E2E_FULL_CRAWL, "opt-in: set E2E_FULL_CRAWL=1");
test.setTimeout(8 * 60_000);

test("crawl a real docs site and get a cited answer", async ({ page }) => {
  const shot = async (name: string) => {
    if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
  };
  const email = `crawl-${Date.now()}@example.com`;

  await page.goto("/register");
  await shot("01-register");
  await page.getByLabel("Full name").fill("Demo Owner");
  await page.getByLabel("Organization name").fill("Demo Support Team");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("correct horse battery");
  await page.getByLabel("Confirm password").fill("correct horse battery");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/sources$/);

  await page.getByRole("button", { name: "Add Website" }).click();
  await page.getByLabel("Website or Documentation URL *").fill(docsUrl);
  await page.getByLabel("Display Label (optional)").fill("Help Center");
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByText(/Queued|Crawling/)).toBeVisible({ timeout: 15_000 });
  await shot("02-crawling");

  await expect(page.getByText("Ready", { exact: true })).toBeVisible({ timeout: 7 * 60_000 });
  await shot("03-ready");

  await page.getByRole("navigation", { name: "Workspace secondary navigation" }).getByRole("link", { name: "Ask" }).click();
  await page.getByLabel("Your question").fill(question);
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText(/Grounded Sources?$/).first()).toBeVisible({ timeout: 60_000 }); // "N Grounded Sources"
  await page.getByText(/Grounded Sources?$/).first().click(); // open the citations
  await shot("04-answer");

  await expect(page.getByRole("meter", { name: "Retrieval confidence" })).toBeVisible();
});
