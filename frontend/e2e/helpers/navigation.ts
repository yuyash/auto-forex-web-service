import { Page } from '@playwright/test';

/**
 * Navigation helper for common page navigation operations
 */
export class NavigationHelper {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  /**
   * Navigate to the dashboard
   */
  async goToDashboard() {
    await this.page.goto('/dashboard');
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Navigate to backtest tasks list
   */
  async goToBacktestTasks() {
    await this.page.goto('/backtest-tasks');
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Navigate to trading tasks list
   */
  async goToTradingTasks() {
    await this.page.goto('/trading-tasks');
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Navigate to a specific backtest task detail page
   */
  async goToBacktestTaskDetail(taskId: number | string) {
    await this.page.goto(`/backtest-tasks/${taskId}`);
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Navigate to a specific trading task detail page
   */
  async goToTradingTaskDetail(taskId: number | string) {
    await this.page.goto(`/trading-tasks/${taskId}`);
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Navigate to execution detail page
   */
  async goToExecutionDetail(executionId: number | string) {
    await this.page.goto(`/executions/${executionId}`);
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Navigate to strategy configurations
   */
  async goToStrategyConfigurations() {
    await this.page.goto('/strategy-configurations');
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Navigate to OANDA accounts
   */
  async goToOandaAccounts() {
    await this.page.goto('/oanda-accounts');
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Wait for URL to match a pattern
   */
  async waitForUrlPattern(pattern: RegExp, timeout = 10000) {
    await this.page.waitForURL(pattern, { timeout });
  }

  /**
   * Go back in browser history
   */
  async goBack() {
    await this.page.goBack();
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Reload the current page
   */
  async reload() {
    await this.page.reload();
    await this.page.waitForLoadState('networkidle');
  }
}
