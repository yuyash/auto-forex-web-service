import { test, expect } from './fixtures/auth';
import { ChartHelper } from './helpers/chart';

test.describe('Chart Scrolling', () => {
  let consoleLogs: string[] = [];

  test.beforeEach(async ({ authenticatedPage }) => {
    // Clear console logs before each test
    consoleLogs = [];

    // Listen to console messages to track data loading
    authenticatedPage.on('console', (msg) => {
      const text = msg.text();
      // Capture logs related to data loading
      if (
        text.includes('Loading') ||
        text.includes('candles') ||
        text.includes('Prepended') ||
        text.includes('Appended') ||
        text.includes('Rendering')
      ) {
        consoleLogs.push(text);
      }
    });

    // Navigate to dashboard
    await authenticatedPage.goto('/dashboard');
  });

  test('should load older data when scrolling left', async ({
    authenticatedPage,
  }) => {
    const chart = new ChartHelper(authenticatedPage);

    // Wait for chart to render with initial data
    await chart.waitForChartRender();

    // Verify chart is visible
    await expect(chart.chartCanvas).toBeVisible();

    // Clear console logs after initial load
    consoleLogs = [];

    // Scroll left to trigger older data loading
    await chart.scrollLeft(10);

    // Verify loading indicator appears
    await expect(chart.loadingIndicator).toBeVisible({ timeout: 5000 });

    // Verify loading direction is "older"
    const loadingText = await chart.getLoadingDirection();
    expect(loadingText).toContain('older');

    // Wait for loading to complete
    await chart.waitForLoadingComplete(15000);

    // Verify loading indicator disappears
    await expect(chart.loadingIndicator).not.toBeVisible();

    // Verify console logs show data was prepended
    const prependedLog = consoleLogs.find((log) => log.includes('Prepended'));
    expect(prependedLog).toBeTruthy();

    // Verify console logs show rendering occurred
    const renderingLog = consoleLogs.find((log) => log.includes('Rendering'));
    expect(renderingLog).toBeTruthy();

    // Verify no error messages
    const hasError = await chart.hasErrorMessage();
    expect(hasError).toBe(false);

    // Verify chart is still visible (data didn't disappear)
    await expect(chart.chartCanvas).toBeVisible();
  });

  test('should load newer data when scrolling right', async ({
    authenticatedPage,
  }) => {
    const chart = new ChartHelper(authenticatedPage);

    // Wait for chart to render with initial data
    await chart.waitForChartRender();

    // Verify chart is visible
    await expect(chart.chartCanvas).toBeVisible();

    // First scroll left a bit to have room to scroll right
    await chart.scrollLeft(5);
    await chart.waitForLoadingComplete(10000);

    // Clear console logs
    consoleLogs = [];

    // Scroll right to trigger newer data loading
    await chart.scrollRight(10);

    // Check if loading indicator appears (it might not if already at current time)
    const loadingVisible = await chart.isLoadingIndicatorVisible();

    if (loadingVisible) {
      // Verify loading direction is "newer"
      const loadingText = await chart.getLoadingDirection();
      expect(loadingText).toContain('newer');

      // Wait for loading to complete
      await chart.waitForLoadingComplete(15000);

      // Verify loading indicator disappears
      await expect(chart.loadingIndicator).not.toBeVisible();

      // Verify console logs show data was appended or already at current time
      const appendedLog = consoleLogs.find(
        (log) => log.includes('Appended') || log.includes('Already at')
      );
      expect(appendedLog).toBeTruthy();
    } else {
      // If no loading indicator, we're already at the latest data
      // This is acceptable - no newer data to load
      console.log('Already at current time, no newer data to load');
    }

    // Verify no error messages
    const hasError = await chart.hasErrorMessage();
    expect(hasError).toBe(false);

    // Verify chart is still visible (data didn't disappear)
    await expect(chart.chartCanvas).toBeVisible();
  });

  test('should maintain data visibility during multiple scroll operations', async ({
    authenticatedPage,
  }) => {
    const chart = new ChartHelper(authenticatedPage);

    // Wait for chart to render with initial data
    await chart.waitForChartRender();

    // Verify chart is visible
    await expect(chart.chartCanvas).toBeVisible();

    // Perform multiple scroll operations
    for (let i = 0; i < 3; i++) {
      // Scroll left
      await chart.scrollLeft(5);
      await chart.waitForLoadingComplete(10000);

      // Verify chart is still visible
      await expect(chart.chartCanvas).toBeVisible();

      // Verify no error
      const hasError = await chart.hasErrorMessage();
      expect(hasError).toBe(false);

      // Scroll right
      await chart.scrollRight(3);
      await chart.waitForLoadingComplete(10000);

      // Verify chart is still visible
      await expect(chart.chartCanvas).toBeVisible();

      // Verify no error
      const hasError2 = await chart.hasErrorMessage();
      expect(hasError2).toBe(false);
    }

    // Verify console logs show multiple data operations
    const dataOperations = consoleLogs.filter(
      (log) => log.includes('Prepended') || log.includes('Appended')
    );
    expect(dataOperations.length).toBeGreaterThan(0);
  });

  test('should stop loading when reaching data boundaries', async ({
    authenticatedPage,
  }) => {
    const chart = new ChartHelper(authenticatedPage);

    // Wait for chart to render with initial data
    await chart.waitForChartRender();

    // Scroll left multiple times to potentially reach the oldest data
    for (let i = 0; i < 5; i++) {
      consoleLogs = [];
      await chart.scrollLeft(10);
      await chart.waitForLoadingComplete(10000);

      // Check if we've reached the boundary
      const noBoundaryLog = consoleLogs.find((log) =>
        log.includes('No older data')
      );

      if (noBoundaryLog) {
        // We've reached the boundary, verify no more loading attempts
        consoleLogs = [];
        await chart.scrollLeft(5);
        await authenticatedPage.waitForTimeout(2000);

        // Should not trigger loading again
        const loadingVisible = await chart.isLoadingIndicatorVisible();
        expect(loadingVisible).toBe(false);
        break;
      }
    }

    // Verify chart is still visible
    await expect(chart.chartCanvas).toBeVisible();
  });

  test('should handle rapid scroll events without breaking', async ({
    authenticatedPage,
  }) => {
    const chart = new ChartHelper(authenticatedPage);

    // Wait for chart to render with initial data
    await chart.waitForChartRender();

    // Perform rapid scroll operations
    await chart.scrollLeft(3);
    await chart.scrollRight(2);
    await chart.scrollLeft(4);
    await chart.scrollRight(3);

    // Wait for any pending operations
    await authenticatedPage.waitForTimeout(3000);

    // Verify chart is still functional
    await expect(chart.chartCanvas).toBeVisible();

    // Verify no error messages
    const hasError = await chart.hasErrorMessage();
    expect(hasError).toBe(false);

    // Wait for any loading to complete
    await chart.waitForLoadingComplete(10000);

    // Verify chart is still visible after all operations
    await expect(chart.chartCanvas).toBeVisible();
  });
});
