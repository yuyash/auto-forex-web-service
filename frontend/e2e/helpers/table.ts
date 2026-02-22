import { Page, Locator } from '@playwright/test';

/**
 * Table helper for common table operations (events, logs, trades)
 */
export class TableHelper {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  /**
   * Get table by test ID or generic table selector
   */
  getTable(testId?: string): Locator {
    if (testId) {
      return this.page.locator(`[data-testid="${testId}"]`);
    }
    return this.page.locator('table').first();
  }

  /**
   * Check if table is visible
   */
  async isTableVisible(testId?: string): Promise<boolean> {
    const table = this.getTable(testId);
    return await table.isVisible({ timeout: 5000 }).catch(() => false);
  }

  /**
   * Check if empty state is visible
   */
  async isEmptyStateVisible(emptyText?: string): Promise<boolean> {
    const emptyLocator = emptyText
      ? this.page.locator(`text=/${emptyText}/i`)
      : this.page.locator('text=/no.*data|empty/i');

    return await emptyLocator.isVisible({ timeout: 5000 }).catch(() => false);
  }

  /**
   * Get row count
   */
  async getRowCount(testId?: string): Promise<number> {
    const table = this.getTable(testId);
    const rows = table.locator('tbody tr');
    return await rows.count();
  }

  /**
   * Get cell value by row and column index
   */
  async getCellValue(
    rowIndex: number,
    columnIndex: number,
    testId?: string
  ): Promise<string | null> {
    const table = this.getTable(testId);
    const cell = table.locator(
      `tbody tr:nth-child(${rowIndex + 1}) td:nth-child(${columnIndex + 1})`
    );
    return await cell.textContent();
  }

  /**
   * Get all values from a specific column
   */
  async getColumnValues(
    columnIndex: number,
    testId?: string
  ): Promise<string[]> {
    const table = this.getTable(testId);
    const cells = table.locator(`tbody tr td:nth-child(${columnIndex + 1})`);
    const count = await cells.count();
    const values: string[] = [];

    for (let i = 0; i < count; i++) {
      const value = await cells.nth(i).textContent();
      if (value) values.push(value);
    }

    return values;
  }

  /**
   * Click on a row
   */
  async clickRow(rowIndex: number, testId?: string) {
    const table = this.getTable(testId);
    const row = table.locator(`tbody tr:nth-child(${rowIndex + 1})`);
    await row.click();
  }

  /**
   * Sort table by column (if sortable)
   */
  async sortByColumn(columnName: string, testId?: string) {
    const table = this.getTable(testId);
    const header = table.locator(`th:has-text("${columnName}")`);
    await header.click();
    await this.page.waitForTimeout(500);
  }

  /**
   * Filter table (if filterable)
   */
  async filterTable(filterValue: string) {
    const filterInput = this.page.locator(
      'input[placeholder*="filter" i], input[placeholder*="search" i]'
    );
    await filterInput.fill(filterValue);
    await this.page.waitForTimeout(500);
  }

  /**
   * Go to next page (if paginated)
   */
  async goToNextPage() {
    const nextButton = this.page.locator('button[aria-label*="next" i]');
    await nextButton.click();
    await this.page.waitForTimeout(500);
  }

  /**
   * Go to previous page (if paginated)
   */
  async goToPreviousPage() {
    const prevButton = this.page.locator('button[aria-label*="previous" i]');
    await prevButton.click();
    await this.page.waitForTimeout(500);
  }

  /**
   * Check if pagination is visible
   */
  async isPaginationVisible(): Promise<boolean> {
    const pagination = this.page.locator(
      '[role="navigation"], .MuiPagination-root'
    );
    return await pagination.isVisible({ timeout: 2000 }).catch(() => false);
  }

  /**
   * Get current page number
   */
  async getCurrentPage(): Promise<number> {
    const currentPageButton = this.page.locator('button[aria-current="true"]');
    const pageText = await currentPageButton.textContent();
    return pageText ? parseInt(pageText, 10) : 1;
  }

  /**
   * Wait for table to load
   */
  async waitForTableLoad(testId?: string, timeout = 10000) {
    const table = this.getTable(testId);
    await table.waitFor({ state: 'visible', timeout });
    await this.page.waitForTimeout(500);
  }
}
