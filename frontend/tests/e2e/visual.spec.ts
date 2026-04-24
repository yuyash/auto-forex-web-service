import type { Page } from '@playwright/test';
import { expect, test } from './fixtures';

const routes = [
  { name: 'dashboard', path: '/dashboard' },
  { name: 'backtest-tasks', path: '/backtest-tasks' },
  { name: 'trading-tasks', path: '/trading-tasks' },
  { name: 'configurations', path: '/configurations' },
  { name: 'settings', path: '/settings' },
  { name: 'profile', path: '/profile' },
] as const;

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => ({
    viewportWidth: (
      globalThis as unknown as {
        innerWidth: number;
      }
    ).innerWidth,
    documentWidth: (
      globalThis as unknown as {
        document: { documentElement: { scrollWidth: number } };
      }
    ).document.documentElement.scrollWidth,
    bodyWidth: (
      globalThis as unknown as {
        document: { body: { scrollWidth: number } };
      }
    ).document.body.scrollWidth,
  }));

  expect(
    Math.max(overflow.documentWidth, overflow.bodyWidth),
    JSON.stringify(overflow)
  ).toBeLessThanOrEqual(overflow.viewportWidth + 1);
}

test.describe('visual layout regression', () => {
  for (const route of routes) {
    test(`${route.name} desktop layout stays aligned`, async ({
      authenticatedPage,
    }) => {
      await authenticatedPage.setViewportSize({ width: 1366, height: 768 });
      await authenticatedPage.goto(route.path);
      await authenticatedPage.waitForLoadState('networkidle');

      await expectNoHorizontalOverflow(authenticatedPage);
      await expect(authenticatedPage.locator('body')).toHaveScreenshot(
        `${route.name}-desktop.png`,
        {
          animations: 'disabled',
          caret: 'hide',
          mask: [
            authenticatedPage.locator('canvas'),
            authenticatedPage.locator('.MuiCharts-root'),
          ],
          maxDiffPixelRatio: 0.02,
        }
      );
    });

    test(`${route.name} mobile layout stays aligned`, async ({
      authenticatedPage,
    }) => {
      await authenticatedPage.setViewportSize({ width: 390, height: 844 });
      await authenticatedPage.goto(route.path);
      await authenticatedPage.waitForLoadState('networkidle');

      await expectNoHorizontalOverflow(authenticatedPage);
      await expect(authenticatedPage.locator('body')).toHaveScreenshot(
        `${route.name}-mobile.png`,
        {
          animations: 'disabled',
          caret: 'hide',
          mask: [
            authenticatedPage.locator('canvas'),
            authenticatedPage.locator('.MuiCharts-root'),
          ],
          maxDiffPixelRatio: 0.02,
        }
      );
    });
  }
});
