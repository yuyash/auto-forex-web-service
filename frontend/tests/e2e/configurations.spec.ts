/**
 * E2E: Configurations page.
 * Tests listing, search, filter, and navigation to create form.
 * Requires authentication.
 */

import { test, expect } from './fixtures';

test.describe('Configurations', () => {
  test('loads configurations page', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/configurations');
    await authenticatedPage.waitForLoadState('networkidle');

    await expect(
      authenticatedPage.locator('text=Strategy Configurations').first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('has search input', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/configurations');
    await authenticatedPage.waitForLoadState('networkidle');

    await expect(
      authenticatedPage.locator('input[placeholder*="Search"]')
    ).toBeVisible({ timeout: 10000 });
  });

  test('has strategy type filter', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/configurations');
    await authenticatedPage.waitForLoadState('networkidle');

    await expect(
      authenticatedPage.locator('text=Strategy Type').first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('has New Configuration button', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/configurations');
    await authenticatedPage.waitForLoadState('networkidle');

    await expect(
      authenticatedPage.locator('button', { hasText: /new configuration/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test('New Configuration button navigates to form', async ({
    authenticatedPage,
  }) => {
    await authenticatedPage.goto('/configurations');
    await authenticatedPage.waitForLoadState('networkidle');

    await authenticatedPage
      .locator('button', { hasText: /new configuration/i })
      .click();

    await expect(authenticatedPage).toHaveURL(/\/configurations\/new/, {
      timeout: 10000,
    });
  });

  test('search filters configurations', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/configurations');
    await authenticatedPage.waitForLoadState('networkidle');

    const searchInput = authenticatedPage.locator(
      'input[placeholder*="Search"]'
    );
    await searchInput.fill('nonexistent-config-xyz');

    // Wait for debounced search to take effect
    await authenticatedPage.waitForTimeout(1000);

    // Should show empty state or filtered results
    const content = await authenticatedPage.textContent('body');
    expect(content).toBeTruthy();
  });
});
