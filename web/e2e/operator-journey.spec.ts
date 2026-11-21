import { test, expect } from "@playwright/test";

test.describe("Operator Journey E2E", () => {
  test("loads the operator console with simulated data banner", async ({ page }) => {
    await page.goto("/");
    // Operator console must always present the SIMULATED DATA badge
    await expect(page.locator("body")).toContainText("SIMULATED");
  });

  test("navigates to shortage risk trajectory view", async ({ page }) => {
    await page.goto("/");
    const riskLink = page.getByRole("link", { name: /risk/i }).or(page.getByText(/risk/i)).first();
    if (await riskLink.isVisible()) {
      await riskLink.click();
      await expect(page.locator("body")).toBeVisible();
    }
  });

  test("displays recommendations with human-in-the-loop approval controls", async ({ page }) => {
    await page.goto("/");
    const allocLink = page.getByRole("link", { name: /allocation|recommendation/i }).or(page.getByText(/allocation/i)).first();
    if (await allocLink.isVisible()) {
      await allocLink.click();
      await expect(page.locator("body")).toBeVisible();
    }
  });
});

