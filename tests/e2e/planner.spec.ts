import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test("create two tasks, set work hours, generate, inspect and activate a plan", async ({
  page,
}) => {
  test.setTimeout(60000);
  await signIn(page, "a");
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + 1);
  const day = date.toISOString().slice(0, 10);
  const suffix = Date.now();
  for (const title of [`Review lecture ${suffix}`, `Write report ${suffix}`]) {
    await page.getByLabel("Task name", { exact: true }).fill(title);
    await page.getByLabel("Remaining minutes", { exact: true }).fill("60");
    await page.getByLabel("Deadline (UTC)", { exact: true }).fill(day);
    await page.getByRole("button", { name: "Add task", exact: true }).click();
    await expect(
      page.locator(".task-list > ul").getByText(title, { exact: true }),
    ).toBeVisible();
  }
  await page.getByLabel("Available from (UTC)").fill(`${day}T09:00`);
  await page.getByLabel("Available until (UTC)").fill(`${day}T17:00`);
  await page.getByRole("button", { name: "Add available time" }).click();
  await expect(page.getByText("Available time saved")).toBeVisible();
  await page
    .getByRole("button", { name: "Generate plan", exact: true })
    .click();
  const activate = page.getByRole("button", { name: "Activate this plan" });
  await expect(activate).toBeVisible({ timeout: 20000 });
  await expect(page.locator(".schedule-blocks")).toContainText(
    `Write report ${suffix}`,
  );
  await expect(page.getByText("Active plan", { exact: true })).toHaveCount(0);
  await page.screenshot({
    path: "docs/evidence/raw/planner-proposal.png",
    fullPage: true,
  });
  await activate.click();
  await expect(page.getByText("Plan activated", { exact: true })).toBeVisible();
  await expect(page.getByText("Active plan", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "docs/evidence/raw/planner-active.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "docs/evidence/raw/planner-mobile.png",
    fullPage: true,
  });
});
