import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test("export ICS, explicitly connect simulator, retry publication and retain events on disconnect", async ({ page }) => {
  test.setTimeout(60000);
  await signIn(page, "b");
  const active = await (await page.request.get("/api/v1/active-plan")).json();
  if (!active) {
    const day = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
    const form = page.getByRole("form", { name: "Add task", exact: true });
    const title = `Calendar example ${Date.now()}`;
    await form.getByLabel("Task name", { exact: true }).fill(title);
    await form.getByRole("button", { name: "Add task", exact: true }).click();
    await expect(page.locator(".task-list > ul").getByText(title, { exact: true })).toBeVisible();
    await page.getByLabel("Available from (UTC)", { exact: true }).fill(`${day}T09:00`);
    await page.getByLabel("Available until (UTC)", { exact: true }).fill(`${day}T17:00`);
    await page.getByRole("button", { name: "Add available time" }).click();
    await expect(page.getByText("Available time saved")).toBeVisible();
    await page.getByRole("button", { name: "Generate plan", exact: true }).click();
    await page.getByRole("button", { name: "Activate this plan", exact: true }).click({ timeout: 20000 });
    await expect(page.getByText("Plan activated", { exact: true })).toBeVisible();
  }
  await page.getByText("Calendar export and connection", { exact: true }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download active plan as ICS" }).click();
  expect((await download).suggestedFilename()).toBe("adaptive-planner.ics");
  const exported = await page.request.get("/api/v1/exports/calendar.ics");
  expect(await exported.text()).toContain("BEGIN:VCALENDAR");
  await page.getByLabel("This is a dedicated calendar for synthetic tasks").check();
  await page.getByRole("button", { name: "Connect calendar", exact: true }).click();
  await expect(page.getByText("Connection: connected · Local simulator", { exact: true })).toBeVisible();
  await page.route("**/api/v1/calendar/publish", (route) => route.fulfill({ status: 503,
    json: { error: { code: "DEPENDENCY_UNAVAILABLE", message: "Calendar request temporarily unavailable." } } }));
  const publish = page.getByRole("button", { name: "Publish active plan", exact: true });
  await expect(publish).toBeEnabled({ timeout: 15000 });
  await publish.click();
  await expect(page.getByText("Calendar request temporarily unavailable.", { exact: true })).toBeVisible();
  await page.unroute("**/api/v1/calendar/publish");
  await publish.click();
  await expect(page.getByText("Calendar publication queued", { exact: true })).toBeVisible();
  await expect.poll(async () => {
    const status = await (await page.request.get("/api/v1/calendar/status")).json();
    return status.published_count > 0 && status.pending_count === 0 && !status.publish_pending;
  }, { timeout: 15000 }).toBe(true);
  await page.screenshot({ path: "docs/evidence/raw/calendar-simulator.png", fullPage: true });
  await page.getByText("Disconnect calendar", { exact: true }).click();
  await expect(page.getByLabel("Keep remote events after disconnecting")).toBeChecked();
  await page.getByRole("button", { name: "Confirm disconnect", exact: true }).click();
  await expect(page.getByText("Connection: disconnected · Local simulator", { exact: true })).toBeVisible({ timeout: 15000 });
});
