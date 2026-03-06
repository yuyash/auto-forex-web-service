/**
 * E2E: Dashboard page.
 * Tests widget rendering and chart controls.
 */

import { test, expect } from './fixtures';
import { NavigationHelper } from './helpers';

test.describe('Dashboard', () => {
  test('loads dashboard after login', async ({ authenticatedPage }) => {
    await expect(authenticatedPage).toHaveURL(/\/dashboard/);
  });

  test('displays task widgets', async ({ authenticatedPage }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToDashboard();

    // Dashboard should have widget sections
    await expect(
      authenticatedPage.locator('text=Market Chart').first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('has chart control buttons', async ({ authenticatedPage }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToDashboard();

    // Instrument selector
    await expect(
      authenticatedPage.locator('[aria-label="Select instrument"]')
    ).toBeVisible({ timeout: 10000 });

    // Granularity selector
    await expect(
      authenticatedPage.locator('[aria-label="Select granularity"]')
    ).toBeVisible();

    // Auto-refresh toggle
    await expect(
      authenticatedPage.locator(
        'input[aria-label="Auto-refresh"], [role="switch"]'
      )
    ).toBeVisible();
  });

  test('instrument selector opens popover', async ({ authenticatedPage }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToDashboard();

    await authenticatedPage.locator('[aria-label="Select instrument"]').click();

    // Popover with instrument options should appear
    await expect(
      authenticatedPage.locator('[role="menuitem"]').first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('granularity selector opens popover', async ({ authenticatedPage }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToDashboard();

    await authenticatedPage
      .locator('[aria-label="Select granularity"]')
      .click();

    await expect(
      authenticatedPage.locator('[role="menuitem"]').first()
    ).toBeVisible({ timeout: 5000 });
  });
});
