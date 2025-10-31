import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('/');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Vite \+ React \+ TS/);
});

test('get started link', async ({ page }) => {
  await page.goto('/');

  // Click the get started link.
  await page
    .getByRole('link', {
      name: 'Click on the Vite and React logos to learn more',
    })
    .click();

  // Expects page to have a heading with the name of Installation.
  await expect(page.locator('body')).toContainText('Vite');
});
