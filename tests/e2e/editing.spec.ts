import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test("edit inputs, inspect rounding, review timezone changes and remove commitments", async ({
  page,
}) => {
  test.setTimeout(90000);
  await signIn(page, "b");
  const suffix = Date.now();
  const title = `Editable task ${suffix}`;
  const renamed = `Revised task ${suffix}`;
  const day = new Date(Date.now() + 2 * 86400000).toISOString().slice(0, 10);
  await page.getByLabel("Task name", { exact: true }).fill(title);
  await page.getByLabel("Remaining minutes", { exact: true }).fill("30");
  await page.getByLabel("Deadline (UTC)", { exact: true }).fill(day);
  await page.getByRole("button", { name: "Add task", exact: true }).click();
  await page
    .getByRole("button", { name: `Edit task ${title}`, exact: true })
    .click();
  const editor = page.getByRole("form", { name: `Edit ${title}`, exact: true });
  await editor.getByLabel("Task title", { exact: true }).fill(renamed);
  await editor.getByRole("button", { name: "Save task changes" }).click();
  await expect(
    page.getByRole("button", { name: `Edit task ${renamed}`, exact: true }),
  ).toBeVisible();
  const windowsBefore = (
    await (await page.request.get("/api/v1/availability")).json()
  ).windows.length;
  await page
    .getByLabel("Available from (UTC)", { exact: true })
    .fill(`${day}T09:07`);
  await page
    .getByLabel("Available until (UTC)", { exact: true })
    .fill(`${day}T17:00`);
  await page.getByRole("button", { name: "Add available time" }).click();
  await expect(
    page.getByText("Available time saved", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Generate plan", exact: true })
    .click();
  await expect(
    page.getByText("Original times and planning adjustments", { exact: true }),
  ).toBeVisible({ timeout: 30000 });
  await page
    .getByText("Original times and planning adjustments", { exact: true })
    .click();
  await expect(
    page.getByRole("table", { name: "Adjustments for this planning snapshot" }),
  ).toContainText("8 minutes");
  await page.getByText("Timezone settings", { exact: true }).click();
  await page
    .getByLabel("Planning timezone", { exact: true })
    .fill("America/New_York");
  await page.getByRole("button", { name: "Preview timezone change" }).click();
  await expect(page.locator(".timezone-preview")).toContainText(renamed);
  await expect(
    page.getByRole("button", { name: "Apply timezone change" }),
  ).toBeDisabled();
  await page.getByLabel("I reviewed these timezone changes").check();
  await page.getByRole("button", { name: "Apply timezone change" }).click();
  await expect(
    page.getByLabel("Available from (America/New_York)", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Planning timezone", { exact: true }).fill("UTC");
  await page.getByRole("button", { name: "Preview timezone change" }).click();
  await page.getByLabel("I reviewed these timezone changes").check();
  await page.getByRole("button", { name: "Apply timezone change" }).click();
  await expect(
    page.getByLabel("Available from (UTC)", { exact: true }),
  ).toBeVisible();
  await page
    .getByText("Fixed commitments and task dependencies", { exact: true })
    .click();
  await page.getByLabel("Commitment name").fill(`Class ${suffix}`);
  await page
    .getByLabel("Busy from (UTC)", { exact: true })
    .fill(`${day}T12:00`);
  await page
    .getByLabel("Busy until (UTC)", { exact: true })
    .fill(`${day}T13:00`);
  await page
    .getByRole("button", { name: "Add commitment", exact: true })
    .click();
  await expect(
    page.getByText("Commitment added", { exact: true }),
  ).toBeVisible();
  await page.getByText("Review existing commitments", { exact: true }).click();
  await page.getByText(`Edit Class ${suffix}`, { exact: true }).click();
  await page
    .getByLabel("Commitment title", { exact: true })
    .fill(`Updated class ${suffix}`);
  await page.getByRole("button", { name: "Save commitment changes" }).click();
  const remove = page.getByRole("button", {
    name: `Remove commitment Updated class ${suffix}`,
    exact: true,
  });
  await expect(remove).toBeVisible();
  await remove.click();
  await expect(remove).toHaveCount(0);
  await page
    .getByRole("button", {
      name: `Remove available window ${windowsBefore + 1}`,
      exact: true,
    })
    .click();
  await expect
    .poll(
      async () =>
        (await (await page.request.get("/api/v1/availability")).json()).windows
          .length,
    )
    .toBe(windowsBefore);
  await page
    .getByRole("button", { name: `Edit task ${renamed}`, exact: true })
    .click();
  const cancelEditor = page.getByRole("form", {
    name: `Edit ${renamed}`,
    exact: true,
  });
  await cancelEditor.getByLabel("I want to cancel this task").check();
  await cancelEditor
    .getByRole("button", { name: "Cancel task", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: `Edit task ${renamed}`, exact: true }),
  ).toHaveCount(0);
  await page.getByRole("link", { name: "Evidence & limits" }).click();
  await expect(
    page.getByRole("heading", { name: "What has been verified" }),
  ).toBeVisible();
  await page.screenshot({
    path: "docs/evidence/raw/editing-evidence.png",
    fullPage: true,
  });
});
