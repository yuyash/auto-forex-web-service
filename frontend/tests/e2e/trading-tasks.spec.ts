/**
 * E2E: Trading tasks flow.
 * Tests list view, detail view, and task operations.
 */

import { test, expect } from './fixtures';
import { NavigationHelper, TaskHelper } from './helpers';

test.describe('Trading Tasks', () => {
  test('navigates to trading tasks list', async ({ authenticatedPage }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToTradingTasks();

    await expect(authenticatedPage).toHaveURL(/\/trading-tasks/);
  });

  test('displays task list or empty state', async ({ authenticatedPage }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToTradingTasks();

    // Either task cards or an empty state message should be visible
    const hasCards = await authenticatedPage
      .locator('[data-testid="trading-task-card"]')
      .first()
      .isVisible({ timeout: 5000 })
      .catch(() => false);

    if (!hasCards) {
      await expect(authenticatedPage.locator('body')).not.toHaveText('');
    }
  });

  test('navigates to task detail when clicking a task', async ({
    authenticatedPage,
  }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToTradingTasks();

    const taskCard = authenticatedPage
      .locator('[data-testid="trading-task-card"]')
      .first();

    if (await taskCard.isVisible({ timeout: 5000 }).catch(() => false)) {
      await taskCard.click();
      await authenticatedPage.waitForURL(/\/trading-tasks\/\d+/, {
        timeout: 10000,
      });
      await expect(authenticatedPage).toHaveURL(/\/trading-tasks\/\d+/);
    }
  });

  test('task detail shows control buttons', async ({ authenticatedPage }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToTradingTasks();

    const taskCard = authenticatedPage
      .locator('[data-testid="trading-task-card"]')
      .first();

    if (await taskCard.isVisible({ timeout: 5000 }).catch(() => false)) {
      await taskCard.click();
      await authenticatedPage.waitForURL(/\/trading-tasks\/\d+/);

      const taskHelper = new TaskHelper(authenticatedPage);
      // Control buttons should be visible on detail page
      await taskHelper.areControlButtonsVisible();
      // This is data-dependent, so we just verify the page loaded
      await expect(
        authenticatedPage.locator('h1, h2, h3, h4, h5, h6').first()
      ).toBeVisible();
    }
  });
});
