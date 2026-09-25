import { expect, test } from '@playwright/test';

test('browser connects through the dev proxy to the migrated backend', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('Workspace connected');
  await expect(page.getByRole('heading', {name: 'Your agenda'})).toBeVisible();
  await page.screenshot({ path: 'docs/evidence/raw/bootstrap-desktop.png', fullPage: true });
  await page.setViewportSize({width: 390, height: 844});
  await expect(page.getByRole('heading', {name: 'Your agenda'})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: 'docs/evidence/raw/bootstrap-mobile.png', fullPage: true });
});

test('an unavailable backend gives a keyboard accessible recovery action', async ({page}) => {
  await page.route('**/health/ready', route => route.fulfill({status: 503, json: {status: 'not_ready'}}));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Workspace is unavailable');
  await page.unroute('**/health/ready');
  await page.getByRole('button', {name: 'Try again'}).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('status')).toHaveText('Workspace connected');
});
