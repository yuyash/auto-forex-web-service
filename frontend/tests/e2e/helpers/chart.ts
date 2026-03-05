import { Page, Locator } from '@playwright/test';

export class ChartHelper {
  readonly page: Page;
  readonly chartContainer: Locator;
  readonly chartCanvas: Locator;
  readonly loadingIndicator: Locator;
  readonly loadingDirectionText: Locator;
  readonly instrumentDropdown: Locator;
  readonly granularityDropdown: Locator;

  constructor(page: Page) {
    this.page = page;
    this.chartContainer = page.locator('[data-testid="ohlc-chart-container"]');
    this.chartCanvas = page.locator('[data-testid="chart-canvas"]');
    this.loadingIndicator = page.locator(
      '[data-testid="chart-loading-indicator"]'
    );
    this.loadingDirectionText = page.locator(
      '[data-testid="loading-direction-text"]'
    );
    this.instrumentDropdown = page.locator('select[name="instrument"]');
    this.granularityDropdown = page.locator('select[name="granularity"]');
  }

  /**
   * Wait for the chart to be rendered
   */
  async waitForChartRender(timeout = 10000) {
    await this.chartCanvas.waitFor({ state: 'visible', timeout });
    // Wait a bit for chart to fully initialize and load initial data
    await this.page.waitForTimeout(2000);
  }

  /**
   * Scroll the chart left (to view older data)
   * Performs multiple scroll actions to trigger the edge detection
   */
  async scrollLeft(scrollCount = 5) {
    const chartBox = await this.chartCanvas.boundingBox();
    if (!chartBox) throw new Error('Chart canvas not found');

    // Move mouse to center of chart
    await this.page.mouse.move(
      chartBox.x + chartBox.width / 2,
      chartBox.y + chartBox.height / 2
    );

    // Perform multiple scroll actions to reach the left edge
    for (let i = 0; i < scrollCount; i++) {
      await this.page.mouse.wheel(-200, 0);
      await this.page.waitForTimeout(100);
    }

    // Wait for any loading to start
    await this.page.waitForTimeout(500);
  }

  /**
   * Scroll the chart right (to view newer data)
   * Performs multiple scroll actions to trigger the edge detection
   */
  async scrollRight(scrollCount = 5) {
    const chartBox = await this.chartCanvas.boundingBox();
    if (!chartBox) throw new Error('Chart canvas not found');

    // Move mouse to center of chart
    await this.page.mouse.move(
      chartBox.x + chartBox.width / 2,
      chartBox.y + chartBox.height / 2
    );

    // Perform multiple scroll actions to reach the right edge
    for (let i = 0; i < scrollCount; i++) {
      await this.page.mouse.wheel(200, 0);
      await this.page.waitForTimeout(100);
    }

    // Wait for any loading to start
    await this.page.waitForTimeout(500);
  }

  /**
   * Check if loading indicator is visible
   */
  async isLoadingIndicatorVisible(): Promise<boolean> {
    try {
      await this.loadingIndicator.waitFor({ state: 'visible', timeout: 1000 });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Wait for loading to complete
   */
  async waitForLoadingComplete(timeout = 10000) {
    try {
      await this.loadingIndicator.waitFor({ state: 'hidden', timeout });
    } catch {
      // Loading indicator might not appear if data loads too quickly
    }
  }

  /**
   * Change the instrument
   */
  async changeInstrument(instrument: string) {
    await this.instrumentDropdown.selectOption(instrument);
    await this.page.waitForTimeout(500);
  }

  /**
   * Change the granularity (timeframe)
   */
  async changeGranularity(granularity: string) {
    await this.granularityDropdown.selectOption(granularity);
    await this.page.waitForTimeout(500);
  }

  /**
   * Get console logs related to data loading
   * Returns array of log messages that contain candle count information
   */
  async getDataLoadingLogs(): Promise<string[]> {
    // This will be populated by listening to console events in the test
    return [];
  }

  /**
   * Get the loading direction text
   */
  async getLoadingDirection(): Promise<string | null> {
    try {
      await this.loadingDirectionText.waitFor({
        state: 'visible',
        timeout: 1000,
      });
      return await this.loadingDirectionText.textContent();
    } catch {
      return null;
    }
  }

  /**
   * Check if error message is displayed
   */
  async hasErrorMessage(): Promise<boolean> {
    const errorLocator = this.page.locator('text=/error/i');
    try {
      await errorLocator.waitFor({ state: 'visible', timeout: 1000 });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Get error message text
   */
  async getErrorMessage(): Promise<string | null> {
    const errorLocator = this.page.locator('[class*="MuiTypography-root"]', {
      hasText: /error/i,
    });
    try {
      await errorLocator.waitFor({ state: 'visible', timeout: 1000 });
      return await errorLocator.textContent();
    } catch {
      return null;
    }
  }
}
