import { expect, test, type Page } from "@playwright/test";

async function signIn(page: Page, user: "a" | "b") {
  await page.goto("/");
  await page.getByRole("link", { name: "Sign in", exact: true }).click();
  await page.getByLabel("Username or email").fill(`demo-${user}`);
  await page
    .getByLabel("Password", { exact: true })
    .fill(`local-demo-${user}-only`);
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

test("two real OIDC users have separate task workspaces", async ({
  page,
  browser,
}) => {
  const uniqueTitle = `Browser isolation ${Date.now()}`;
  await signIn(page, "a");
  await page.getByLabel("Task name", { exact: true }).fill(uniqueTitle);
  await page.getByLabel("Remaining minutes", { exact: true }).fill("90");
  await page.getByRole("button", { name: "Add task", exact: true }).click();
  await expect(page.locator('.task-list > ul').getByText(uniqueTitle, { exact: true })).toBeVisible();
  const other = await browser.newContext();
  try {
    const second = await other.newPage();
    await signIn(second, "b");
    await expect(
      second.getByRole("heading", { name: "Your tasks" }),
    ).toBeVisible();
    await expect(second.getByText(uniqueTitle, { exact: true })).toHaveCount(0);
    await second.screenshot({
      path: "docs/evidence/raw/second-user-workspace.png",
      fullPage: true,
    });
  } finally {
    await other.close();
  }
  await page.screenshot({
    path: "docs/evidence/raw/task-workspace.png",
    fullPage: true,
  });
});
