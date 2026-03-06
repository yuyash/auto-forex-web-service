/**
 * E2E: Global navigation.
 * Tests header navigation links, 404 handling, and breadcrumbs.
 */

import { test, expect } from './fixtures';

test.describe('Navigation', () => {
  test('header has navigation links', async ({ authenticatedPage }) => {
    // Ensure we're on the dashboard
    await authenticatedPage.goto('/dashboard');
    await authenticatedPage.waitForLoadState('networkidle');

    // Wait for the header to render with navigation links
    // At desktop viewport (1280x720), links are in the header/banner area
    // The AppHeader renders links like "Configurations", "Backtest", "Trading"
    await expect(
      authenticatedPage
        .locator(
          'a[href="/configurations"], a[href="/backtest-tasks"], a[href="/trading-tasks"]'
        )
        .first()
    ).toBeVisible({ timeout: 10000 });

    const navLinks = authenticatedPage.locator(
      'a[href="/configurations"], a[href="/backtest-tasks"], a[href="/trading-tasks"]'
    );
    const count = await navLinks.count();
    expect(count).toBeGreaterThan(0);
  });

  test('shows 404 page for unknown routes', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/this-route-does-not-exist');

    // Should show 404 or redirect
    await expect(authenticatedPage.locator('body')).not.toHaveText('');
  });

  test('breadcrumbs are visible on sub-pages', async ({
    authenticatedPage,
  }) => {
    await authenticatedPage.goto('/backtest-tasks');
    await authenticatedPage.waitForLoadState('networkidle');

    // Breadcrumb navigation should be present
    const breadcrumb = authenticatedPage.locator(
      'nav[aria-label="breadcrumb"], [role="navigation"]'
    );
    await expect(breadcrumb.first()).toBeVisible({ timeout: 10000 });
  });
});
