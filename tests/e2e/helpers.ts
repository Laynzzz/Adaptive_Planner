import { expect, type Page } from "@playwright/test";
export async function signIn(page: Page, user: "a" | "b") {
  await page.goto("/");
  await page.getByRole("link", { name: "Sign in", exact: true }).click();
  await page.getByLabel("Username or email").fill(`demo-${user}`);
  await page
    .getByLabel("Password", { exact: true })
    .fill(`local-demo-${user}-only`);
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}
