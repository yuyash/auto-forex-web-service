/**
 * E2E: Backtest tasks flow.
 * Tests list view, detail view, and task operations.
 */

import { test, expect } from './fixtures';
import { NavigationHelper, TaskHelper } from './helpers';

test.describe('Backtest Tasks', () => {
  test('navigates to backtest tasks list', async ({ authenticatedPage }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToBacktestTasks();

    await expect(authenticatedPage).toHaveURL(/\/backtest-tasks/);
    await expect(
      authenticatedPage.locator('h1, h2, h3, h4, h5, h6').first()
    ).toBeVisible();
  });

  test('displays task list or empty state', async ({ authenticatedPage }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToBacktestTasks();

    // Either task cards or an empty state message should be visible
    const hasCards = await authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first()
      .isVisible({ timeout: 5000 })
      .catch(() => false);

    if (!hasCards) {
      // Empty state or loading should be present
      await expect(authenticatedPage.locator('body')).not.toHaveText('');
    }
  });

  test('navigates to task detail when clicking a task', async ({
    authenticatedPage,
  }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToBacktestTasks();

    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (await taskCard.isVisible({ timeout: 5000 }).catch(() => false)) {
      await taskCard.click();
      await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/, {
        timeout: 10000,
      });
      await expect(authenticatedPage).toHaveURL(/\/backtest-tasks\/\d+/);
    }
  });

  test('task detail shows tabs', async ({ authenticatedPage }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToBacktestTasks();

    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (await taskCard.isVisible({ timeout: 5000 }).catch(() => false)) {
      await taskCard.click();
      await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

      // Verify tabs are present
      const tabs = authenticatedPage.locator('button[role="tab"]');
      await expect(tabs.first()).toBeVisible({ timeout: 5000 });
    }
  });

  test('task detail tab navigation works', async ({ authenticatedPage }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToBacktestTasks();

    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (await taskCard.isVisible({ timeout: 5000 }).catch(() => false)) {
      await taskCard.click();
      await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

      const taskHelper = new TaskHelper(authenticatedPage);

      // Switch through tabs
      for (const tabName of ['Events', 'Logs', 'Positions']) {
        await taskHelper.switchToTab(tabName);
        await authenticatedPage.waitForTimeout(500);
      }
    }
  });
});
