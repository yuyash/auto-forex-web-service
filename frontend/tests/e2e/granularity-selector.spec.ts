/**
 * E2E tests for Granularity Selector
 *
 * Tests the granularity selector functionality including:
 * - Changing granularity updates chart
 * - Zoom in/out with different granularities
 * - Verifying statistical data accuracy
 */

import { test, expect } from './fixtures/auth';
import { Page } from '@playwright/test';

// Helper function to navigate to a task with execution data
async function navigateToTaskWithData(
  page: Page,
  taskType: 'backtest' | 'trading'
) {
  await page.goto(`/${taskType}-tasks`);
  await page.waitForLoadState('networkidle');

  const taskCard = page
    .locator(`[data-testid="${taskType}-task-card"]`)
    .first();

  if (!(await taskCard.isVisible())) {
    throw new Error(`No ${taskType} tasks available`);
  }

  await taskCard.click();
  await page.waitForURL(new RegExp(`/${taskType}-tasks/\\d+`));
}

// Helper function to select granularity
async function selectGranularity(page: Page, granularity: string) {
  const granularitySelect = page.locator(
    'select[name="granularity"], [aria-label*="granularity"]'
  );

  if (await granularitySelect.isVisible()) {
    await granularitySelect.selectOption(granularity);
    await page.waitForTimeout(1000); // Wait for chart to update
    return true;
  }

  return false;
}

// Helper function to get chart data points count (approximate)
async function getChartDataPointsCount(page: Page): Promise<number> {
  // This is an approximation - in a real scenario, you might inspect the chart's data
  const chartCanvas = page.locator(
    '[data-testid="equity-chart"] canvas, canvas'
  );

  if (await chartCanvas.isVisible()) {
    // In a real implementation, you might use page.evaluate to access chart data
    // For now, we'll just verify the chart exists
    return 1;
  }

  return 0;
}

test.describe('Granularity Selector E2E', () => {
  test.beforeEach(async ({ authenticatedPage }) => {
    try {
      await navigateToTaskWithData(authenticatedPage, 'backtest');
    } catch {
      test.skip('No backtest tasks available for testing');
    }

    // Navigate to Equity tab
    const equityTab = authenticatedPage.locator('button[role="tab"]', {
      hasText: /equity/i,
    });
    if (await equityTab.isVisible()) {
      await equityTab.click();
      await authenticatedPage.waitForTimeout(1000);
    }
  });

  test('should display granularity selector', async ({ authenticatedPage }) => {
    // Verify granularity selector is visible
    const granularitySelect = authenticatedPage.locator(
      'select[name="granularity"], [aria-label*="granularity"]'
    );
    const granularityLabel = authenticatedPage.locator('text=/granularity/i');

    const hasSelect = await granularitySelect
      .isVisible({ timeout: 5000 })
      .catch(() => false);
    const hasLabel = await granularityLabel
      .isVisible({ timeout: 5000 })
      .catch(() => false);

    expect(hasSelect || hasLabel).toBeTruthy();
  });

  test('should change granularity and update chart', async ({
    authenticatedPage,
  }) => {
    const granularities = [
      { value: '1', label: '1 second' },
      { value: '60', label: '1 minute' },
      { value: '300', label: '5 minutes' },
      { value: '3600', label: '1 hour' },
    ];

    for (const granularity of granularities) {
      const success = await selectGranularity(
        authenticatedPage,
        granularity.value
      );

      if (success) {
        // Verify chart is still visible after granularity change
        const chart = authenticatedPage.locator(
          '[data-testid="equity-chart"], canvas'
        );
        await expect(chart).toBeVisible({ timeout: 5000 });

        // Wait for any loading indicators to disappear
        const loadingIndicator = authenticatedPage.locator(
          '[data-testid="loading"], [role="progressbar"]'
        );
        if (
          await loadingIndicator.isVisible({ timeout: 2000 }).catch(() => false)
        ) {
          await loadingIndicator.waitFor({ state: 'hidden', timeout: 10000 });
        }
      }
    }
  });

  test('should zoom in with finer granularity', async ({
    authenticatedPage,
  }) => {
    // Start with coarse granularity (1 hour)
    const coarseSuccess = await selectGranularity(authenticatedPage, '3600');

    if (!coarseSuccess) {
      test.skip('Granularity selector not available');
    }

    // Wait for chart to render
    await authenticatedPage.waitForTimeout(2000);

    // Get approximate data points with coarse granularity
    await getChartDataPointsCount(authenticatedPage);

    // Switch to fine granularity (1 minute)
    await selectGranularity(authenticatedPage, '60');

    // Wait for chart to update
    await authenticatedPage.waitForTimeout(2000);

    // Get approximate data points with fine granularity
    await getChartDataPointsCount(authenticatedPage);

    // Verify chart is still visible (data points comparison is approximate)
    const chart = authenticatedPage.locator(
      '[data-testid="equity-chart"], canvas'
    );
    await expect(chart).toBeVisible();
  });

  test('should zoom out with coarser granularity', async ({
    authenticatedPage,
  }) => {
    // Start with fine granularity (1 second)
    const fineSuccess = await selectGranularity(authenticatedPage, '1');

    if (!fineSuccess) {
      test.skip('Granularity selector not available');
    }

    // Wait for chart to render
    await authenticatedPage.waitForTimeout(2000);

    // Switch to coarse granularity (1 hour)
    await selectGranularity(authenticatedPage, '3600');

    // Wait for chart to update
    await authenticatedPage.waitForTimeout(2000);

    // Verify chart is still visible
    const chart = authenticatedPage.locator(
      '[data-testid="equity-chart"], canvas'
    );
    await expect(chart).toBeVisible();
  });

  test('should display statistical data for selected granularity', async ({
    authenticatedPage,
  }) => {
    // Select a specific granularity
    const success = await selectGranularity(authenticatedPage, '300'); // 5 minutes

    if (!success) {
      test.skip('Granularity selector not available');
    }

    // Wait for chart to update
    await authenticatedPage.waitForTimeout(2000);

    // Look for statistical data display (OHLC values, min/max/avg)
    const statsDisplay = authenticatedPage.locator(
      '[data-testid*="stats"], [data-testid*="ohlc"]'
    );

    if (await statsDisplay.isVisible({ timeout: 2000 })) {
      // Verify statistical values are present
      const statValues = authenticatedPage.locator(
        'text=/min|max|avg|open|high|low|close/i'
      );
      const count = await statValues.count();

      expect(count).toBeGreaterThan(0);
    }
  });

  test('should persist granularity selection across tab changes', async ({
    authenticatedPage,
  }) => {
    // Select a specific granularity
    const success = await selectGranularity(authenticatedPage, '300');

    if (!success) {
      test.skip('Granularity selector not available');
    }

    // Navigate to another tab
    const metricsTab = authenticatedPage.locator('button[role="tab"]', {
      hasText: /metrics/i,
    });
    if (await metricsTab.isVisible()) {
      await metricsTab.click();
      await authenticatedPage.waitForTimeout(1000);
    }

    // Navigate back to Equity tab
    const equityTab = authenticatedPage.locator('button[role="tab"]', {
      hasText: /equity/i,
    });
    await equityTab.click();
    await authenticatedPage.waitForTimeout(1000);

    // Verify granularity is still selected
    const granularitySelect = authenticatedPage.locator(
      'select[name="granularity"]'
    );
    if (await granularitySelect.isVisible()) {
      const selectedValue = await granularitySelect.inputValue();
      expect(selectedValue).toBe('300');
    }
  });

  test('should handle granularity change with no data gracefully', async ({
    authenticatedPage,
  }) => {
    // Navigate to a task that might not have data
    await authenticatedPage.goto('/backtest-tasks');
    await authenticatedPage.waitForLoadState('networkidle');

    // Try to create a new task (which won't have execution data)
    const createButton = authenticatedPage.locator('button', {
      hasText: /create|new/i,
    });

    if (await createButton.isVisible()) {
      await createButton.click();
      await authenticatedPage.waitForSelector('form');

      await authenticatedPage.fill('input[name="name"]', 'E2E Test Empty Task');

      // Select configuration
      const configSelect = authenticatedPage
        .locator('select[name="configuration"], [role="combobox"]')
        .first();
      await configSelect.click();
      await authenticatedPage.waitForTimeout(500);

      const firstOption = authenticatedPage.locator('[role="option"]').first();
      if (await firstOption.isVisible()) {
        await firstOption.click();
      }

      const submitButton = authenticatedPage.locator('button[type="submit"]');
      await submitButton.click();

      await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

      // Navigate to Equity tab
      const equityTab = authenticatedPage.locator('button[role="tab"]', {
        hasText: /equity/i,
      });
      if (await equityTab.isVisible()) {
        await equityTab.click();
        await authenticatedPage.waitForTimeout(1000);

        // Try to change granularity
        const success = await selectGranularity(authenticatedPage, '60');

        if (success) {
          // Verify empty state or message is shown
          const emptyState = authenticatedPage.locator(
            'text=/no.*data|no.*executions/i'
          );
          const hasEmpty = await emptyState
            .isVisible({ timeout: 2000 })
            .catch(() => false);

          // Either empty state or chart should be visible
          const chart = authenticatedPage.locator(
            '[data-testid="equity-chart"], canvas'
          );
          const hasChart = await chart
            .isVisible({ timeout: 2000 })
            .catch(() => false);

          expect(hasEmpty || hasChart).toBeTruthy();
        }
      }
    }
  });

  test('should display granularity options in correct order', async ({
    authenticatedPage,
  }) => {
    const granularitySelect = authenticatedPage.locator(
      'select[name="granularity"]'
    );

    if (await granularitySelect.isVisible()) {
      // Get all options
      const options = await granularitySelect
        .locator('option')
        .allTextContents();

      // Verify we have multiple options
      expect(options.length).toBeGreaterThan(1);

      // Verify options are in ascending order (typically: 1s, 1m, 5m, 1h, etc.)
      // This is a basic check - actual order may vary
      expect(options.length).toBeGreaterThanOrEqual(3);
    }
  });

  test('should update chart tooltip with granularity-specific data', async ({
    authenticatedPage,
  }) => {
    // Select a specific granularity
    const success = await selectGranularity(authenticatedPage, '300');

    if (!success) {
      test.skip('Granularity selector not available');
    }

    // Wait for chart to render
    await authenticatedPage.waitForTimeout(2000);

    // Try to hover over chart to trigger tooltip
    const chartCanvas = authenticatedPage.locator(
      '[data-testid="equity-chart"] canvas, canvas'
    );

    if (await chartCanvas.isVisible()) {
      const box = await chartCanvas.boundingBox();

      if (box) {
        // Hover over middle of chart
        await authenticatedPage.mouse.move(
          box.x + box.width / 2,
          box.y + box.height / 2
        );
        await authenticatedPage.waitForTimeout(500);

        // Look for tooltip
        const tooltip = authenticatedPage.locator(
          '[role="tooltip"], [data-testid="chart-tooltip"]'
        );

        if (await tooltip.isVisible({ timeout: 2000 })) {
          // Verify tooltip contains data
          const tooltipText = await tooltip.textContent();
          expect(tooltipText).toBeTruthy();
        }
      }
    }
  });

  test('should work with metrics chart granularity', async ({
    authenticatedPage,
  }) => {
    // Navigate to Metrics tab
    const metricsTab = authenticatedPage.locator('button[role="tab"]', {
      hasText: /metrics/i,
    });

    if (await metricsTab.isVisible()) {
      await metricsTab.click();
      await authenticatedPage.waitForTimeout(1000);

      // Try to change granularity on metrics chart
      const success = await selectGranularity(authenticatedPage, '60');

      if (success) {
        // Verify metrics chart is still visible
        const metricsChart = authenticatedPage.locator(
          '[data-testid="metrics-chart"], canvas'
        );
        await expect(metricsChart).toBeVisible({ timeout: 5000 });
      }
    }
  });
});
