/// <reference lib="dom" />

import type { Locator, Page } from '@playwright/test';
import { expect, test } from './fixtures';

const VIEWPORTS = [
  { name: 'desktop', width: 1366, height: 768 },
  { name: 'mobile', width: 390, height: 844 },
] as const;

const AUTHENTICATED_ROUTES = [
  '/dashboard',
  '/configurations',
  '/configurations/new',
  '/backtest-tasks',
  '/backtest-tasks/new',
  '/trading-tasks',
  '/trading-tasks/new',
  '/oanda-accounts',
  '/settings',
  '/profile',
  '/this-route-does-not-exist',
] as const;

const PUBLIC_ROUTES = ['/login', '/register'] as const;

async function expectNoDocumentHorizontalOverflow(page: Page) {
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

async function expectPageStructure(page: Page) {
  await expect(page.locator('body')).not.toHaveText('');
  await expect(page.locator('body')).not.toContainText('Maximum call stack');
  await expect(
    page.locator('h1, h2, h3, h4, h5, h6, main, [role="main"]').first()
  ).toBeVisible({ timeout: 10_000 });
  await expectNoDocumentHorizontalOverflow(page);
}

async function openFirstCardDetail(
  page: Page,
  listPath: string,
  cardTestId: string,
  detailPattern: RegExp
): Promise<boolean> {
  await page.goto(listPath);
  await page.waitForLoadState('networkidle');

  const card = page.locator(`[data-testid="${cardTestId}"]`).first();
  if (!(await card.isVisible({ timeout: 5_000 }).catch(() => false))) {
    return false;
  }

  await card.click();
  await page.waitForURL(detailPattern, { timeout: 10_000 });
  await page.waitForLoadState('networkidle');
  await expectPageStructure(page);
  return true;
}

async function visibleTabs(page: Page) {
  const tabs = page.locator('button[role="tab"]');
  const count = await tabs.count();
  const visible: Locator[] = [];
  for (let index = 0; index < count; index += 1) {
    const tab = tabs.nth(index);
    if (await tab.isVisible().catch(() => false)) {
      visible.push(tab);
    }
  }
  return visible;
}

async function expectTabsRender(page: Page) {
  await expect(page.locator('[role="tablist"]').first()).toBeVisible({
    timeout: 10_000,
  });

  const tabs = await visibleTabs(page);
  expect(tabs.length).toBeGreaterThan(0);

  for (const tab of tabs) {
    await tab.click();
    await page.waitForTimeout(250);
    await expectPageStructure(page);
  }
}

async function switchToTab(page: Page, label: RegExp): Promise<boolean> {
  const tab = page.locator('button[role="tab"]', { hasText: label }).first();
  if (!(await tab.isVisible({ timeout: 3_000 }).catch(() => false))) {
    return false;
  }
  await tab.click();
  await page.waitForTimeout(500);
  return true;
}

async function expectFirstDataTableCanScrollHorizontally(page: Page) {
  const region = page
    .locator('[role="region"][aria-label="Data table"]')
    .first();
  await expect(region).toBeVisible({ timeout: 10_000 });

  const scrollState = await region.evaluate((node) => {
    const tableContainer = node.querySelector('.MuiTableContainer-root');
    const table = node.querySelector('table');
    if (!tableContainer || !table) {
      return {
        hasTable: false,
        canScroll: false,
        tableWidth: 0,
        clientWidth: 0,
      };
    }

    const before = tableContainer.scrollLeft;
    tableContainer.scrollLeft = 48;
    const after = tableContainer.scrollLeft;
    tableContainer.scrollLeft = before;

    return {
      hasTable: true,
      canScroll: after > before,
      tableWidth: table.getBoundingClientRect().width,
      clientWidth: tableContainer.clientWidth,
    };
  });

  expect(scrollState.hasTable, JSON.stringify(scrollState)).toBe(true);
  expect(scrollState.tableWidth, JSON.stringify(scrollState)).toBeGreaterThan(
    scrollState.clientWidth
  );
  expect(scrollState.canScroll, JSON.stringify(scrollState)).toBe(true);
}

async function expectVisibleMetricChartsFillPanels(page: Page) {
  const chartGeometry = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('.MuiCharts-root'))
      .map((node) => {
        const chart = node.getBoundingClientRect();
        const paper = node.closest('.MuiPaper-root')?.getBoundingClientRect();
        if (!paper || chart.width === 0 || chart.height === 0) {
          return null;
        }

        return {
          chartWidth: chart.width,
          chartHeight: chart.height,
          paperWidth: paper.width,
          paperHeight: paper.height,
          insideHorizontally:
            chart.left >= paper.left - 1 && chart.right <= paper.right + 1,
          insideVertically:
            chart.top >= paper.top - 1 && chart.bottom <= paper.bottom + 1,
          fillsWidth: chart.width >= paper.width * 0.75,
          fillsHeight: chart.height >= paper.height * 0.6,
        };
      })
      .filter(Boolean);
  });

  if (chartGeometry.length === 0) {
    return;
  }

  for (const geometry of chartGeometry) {
    expect(geometry?.insideHorizontally, JSON.stringify(geometry)).toBe(true);
    expect(geometry?.insideVertically, JSON.stringify(geometry)).toBe(true);
    expect(geometry?.fillsWidth, JSON.stringify(geometry)).toBe(true);
    expect(geometry?.fillsHeight, JSON.stringify(geometry)).toBe(true);
  }
}

test.describe('screen structure coverage', () => {
  for (const viewport of VIEWPORTS) {
    test(`public screen structure renders on ${viewport.name}`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);

      for (const route of PUBLIC_ROUTES) {
        await page.goto(route);
        await page.waitForLoadState('networkidle');
        await expectPageStructure(page);
      }
    });

    test(`authenticated screen structure renders on ${viewport.name}`, async ({
      authenticatedPage,
    }) => {
      await authenticatedPage.setViewportSize(viewport);

      for (const route of AUTHENTICATED_ROUTES) {
        await authenticatedPage.goto(route);
        await authenticatedPage.waitForLoadState('networkidle');
        await expectPageStructure(authenticatedPage);
      }
    });
  }

  test('settings tabs render without layout overflow', async ({
    authenticatedPage,
  }) => {
    await authenticatedPage.goto('/settings');
    await authenticatedPage.waitForLoadState('networkidle');

    await expectTabsRender(authenticatedPage);
  });

  test('configuration detail and edit screens render when data exists', async ({
    authenticatedPage,
  }) => {
    await authenticatedPage.goto('/configurations');
    await authenticatedPage.waitForLoadState('networkidle');

    const detailLink = authenticatedPage
      .locator('a[href^="/configurations/"]')
      .filter({ hasNotText: /new/i })
      .first();
    if (!(await detailLink.isVisible({ timeout: 5_000 }).catch(() => false))) {
      return;
    }

    await detailLink.click();
    await authenticatedPage.waitForURL(/\/configurations\/[^/]+$/, {
      timeout: 10_000,
    });
    await expectPageStructure(authenticatedPage);

    const editButton = authenticatedPage
      .locator('a[href$="/edit"], button', { hasText: /edit/i })
      .first();
    if (await editButton.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await editButton.click();
      await authenticatedPage.waitForURL(/\/configurations\/[^/]+\/edit$/, {
        timeout: 10_000,
      });
      await expectPageStructure(authenticatedPage);
    }
  });

  test('OANDA account detail screen renders when data exists', async ({
    authenticatedPage,
  }) => {
    await authenticatedPage.goto('/oanda-accounts');
    await authenticatedPage.waitForLoadState('networkidle');

    const detailLink = authenticatedPage
      .locator('a[href^="/oanda-accounts/"]')
      .first();
    if (!(await detailLink.isVisible({ timeout: 5_000 }).catch(() => false))) {
      return;
    }

    await detailLink.click();
    await authenticatedPage.waitForURL(/\/oanda-accounts\/[^/]+$/, {
      timeout: 10_000,
    });
    await expectPageStructure(authenticatedPage);
  });

  test('backtest task detail tabs, tables, and charts render when data exists', async ({
    authenticatedPage,
  }) => {
    const hasDetail = await openFirstCardDetail(
      authenticatedPage,
      '/backtest-tasks',
      'backtest-task-card',
      /\/backtest-tasks\/[^/]+$/
    );
    if (!hasDetail) return;

    await expectTabsRender(authenticatedPage);

    await authenticatedPage.setViewportSize({ width: 390, height: 844 });
    if (await switchToTab(authenticatedPage, /trades|取引/i)) {
      await expectFirstDataTableCanScrollHorizontally(authenticatedPage);
    }

    await authenticatedPage.setViewportSize({ width: 1366, height: 768 });
    if (await switchToTab(authenticatedPage, /metrics|メトリクス/i)) {
      await expectVisibleMetricChartsFillPanels(authenticatedPage);
    }
  });

  test('trading task detail tabs, tables, and charts render when data exists', async ({
    authenticatedPage,
  }) => {
    const hasDetail = await openFirstCardDetail(
      authenticatedPage,
      '/trading-tasks',
      'trading-task-card',
      /\/trading-tasks\/[^/]+$/
    );
    if (!hasDetail) return;

    await expectTabsRender(authenticatedPage);

    await authenticatedPage.setViewportSize({ width: 390, height: 844 });
    if (await switchToTab(authenticatedPage, /trades|取引/i)) {
      await expectFirstDataTableCanScrollHorizontally(authenticatedPage);
    }

    await authenticatedPage.setViewportSize({ width: 1366, height: 768 });
    if (await switchToTab(authenticatedPage, /metrics|メトリクス/i)) {
      await expectVisibleMetricChartsFillPanels(authenticatedPage);
    }
  });
});
