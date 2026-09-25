import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test("local extraction needs review and provider failure preserves manual entry", async ({ page }) => {
  await signIn(page, "b");
  await page.getByText("Describe tasks in your own words", { exact: true }).click();
  const title = `Review synthetic notes ${Date.now()}`;
  const source = `${title} for 60 minutes due next Thursday`;
  await page.getByLabel("Describe your tasks").fill(source);
  await page.getByRole("button", { name: "Extract draft", exact: true }).click();
  const review = page.getByRole("form", { name: "Review extracted tasks" });
  await expect(review).toBeVisible({ timeout: 10000 });
  await expect(page.locator(".task-list > ul").getByText(title, { exact: true })).toHaveCount(0);
  await expect(review.getByRole("button", { name: "Add reviewed tasks" })).toBeDisabled();
  await review.getByLabel("Use no deadline").check();
  await review.getByLabel("Confirm Priority").check();
  await review.getByRole("button", { name: "Add reviewed tasks" }).click();
  await expect(page.getByText("Reviewed tasks added", { exact: true })).toBeVisible();
  await expect(page.locator(".task-list > ul").getByText(title, { exact: true })).toBeVisible();
  await page.route("**/api/v1/interpretations", (route) => route.fulfill({
    status: 503, json: { error: { code: "PROVIDER_TIMEOUT", message: "Extraction timed out." } },
  }));
  await page.getByRole("button", { name: "Extract draft", exact: true }).click();
  await expect(page.getByText("Extraction timed out.", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Describe your tasks")).toHaveValue(source);
  await page.getByRole("link", { name: "Use the task form" }).click();
  await expect(page.getByRole("form", { name: "Add task", exact: true })).toBeVisible();
  await page.screenshot({ path: "docs/evidence/raw/interpretation-fallback.png", fullPage: true });
});
