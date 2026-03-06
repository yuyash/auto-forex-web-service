/**
 * E2E: Settings and Profile pages.
 * Tests navigation and basic rendering.
 * Requires authentication.
 */

import { test, expect } from './fixtures';

test.describe('Settings', () => {
  test('loads settings page', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/settings');
    await authenticatedPage.waitForLoadState('networkidle');

    // Settings page should render
    await expect(authenticatedPage.locator('h4, h5, h6').first()).toBeVisible({
      timeout: 10000,
    });
  });

  test('loads profile page', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/profile');
    await authenticatedPage.waitForLoadState('networkidle');

    // Profile page should render
    await expect(authenticatedPage.locator('h4, h5, h6').first()).toBeVisible({
      timeout: 10000,
    });
  });
});
