import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test("weekday-only extraction needs confirmation and persists in manual preferences", async ({
  page,
}) => {
  await signIn(page, "b");
  await page
    .getByText("Describe tasks in your own words", { exact: true })
    .click();
  await page.getByLabel("Describe your tasks").fill("I dislike Sundays");
  await page
    .getByRole("button", { name: "Extract draft", exact: true })
    .click();
  const review = page.getByRole("form", { name: "Review extracted tasks" });
  await expect(review).toBeVisible({ timeout: 10000 });
  const accept = review.getByRole("button", { name: "Add reviewed inputs" });
  await expect(accept).toBeDisabled();
  await review
    .getByLabel("Confirm Prefer to avoid work on Sunday", { exact: true })
    .check();
  await accept.click();
  await expect(
    page.getByText("Reviewed inputs added", { exact: true }),
  ).toBeVisible();
  await page.getByText("Weekly preferences", { exact: true }).click();
  await expect(
    page.getByText("Sunday: Prefer to keep free", { exact: false }),
  ).toBeVisible();
  await page.reload();
  await page.getByText("Weekly preferences", { exact: true }).click();
  await expect(
    page.getByText("Sunday: Prefer to keep free", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Remove Sunday rule", exact: true })
    .click();
  await expect(
    page.getByText("Weekly rule removed", { exact: true }),
  ).toBeVisible();
});
