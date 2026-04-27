import type { Page } from '@playwright/test';
import { expect, test } from './fixtures';
import { NavigationHelper, TaskHelper } from './helpers';

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
  }));

  expect(
    Math.max(overflow.documentWidth, overflow.bodyWidth),
    JSON.stringify(overflow)
  ).toBeLessThanOrEqual(overflow.viewportWidth + 1);
}

test.describe('task detail mobile layout @mobile-only', () => {
  test('filter and metrics controls stay within the mobile viewport', async ({
    authenticatedPage,
  }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToBacktestTasks();

    const taskHelper = new TaskHelper(authenticatedPage);
    const taskCard = taskHelper.getFirstTaskCard();
    if (!(await taskCard.isVisible({ timeout: 5000 }).catch(() => false))) {
      return;
    }

    await taskHelper.clickTaskCard(taskCard);
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/, {
      timeout: 10000,
    });

    for (const tabName of ['Positions', 'Trades', 'Orders', 'Logs']) {
      const tab = authenticatedPage.locator('button[role="tab"]', {
        hasText: new RegExp(tabName, 'i'),
      });
      if (!(await tab.isVisible().catch(() => false))) {
        continue;
      }
      await taskHelper.switchToTab(tabName);
      await expectNoHorizontalOverflow(authenticatedPage);

      const filterBar = authenticatedPage
        .locator('[data-testid="table-filter-bar"]')
        .first();
      if (await filterBar.isVisible().catch(() => false)) {
        const box = await filterBar.boundingBox();
        expect(box?.width ?? 0).toBeLessThanOrEqual(390);
      }
    }

    const metricsTab = authenticatedPage.locator('button[role="tab"]', {
      hasText: /metrics/i,
    });
    if (await metricsTab.isVisible().catch(() => false)) {
      await taskHelper.switchToTab('Metrics');
      await expectNoHorizontalOverflow(authenticatedPage);
      const granularityControl = authenticatedPage.getByLabel('Granularity');
      if (await granularityControl.isVisible().catch(() => false)) {
        await expect(granularityControl).toBeVisible();
        await expect(
          authenticatedPage.getByLabel('Refresh all charts')
        ).toBeVisible();
      }
    }
  });
});
