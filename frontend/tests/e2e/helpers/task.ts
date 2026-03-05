import { Page, Locator } from '@playwright/test';

/**
 * Task helper for common task operations (backtest and trading tasks)
 */
export class TaskHelper {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  /**
   * Wait for task to reach a specific status
   */
  async waitForTaskStatus(
    expectedStatus: string,
    timeout = 30000
  ): Promise<boolean> {
    const startTime = Date.now();
    while (Date.now() - startTime < timeout) {
      const statusBadge = this.page.locator(
        '[data-testid="task-status-badge"]'
      );
      const status = await statusBadge.textContent();
      if (status?.toLowerCase().includes(expectedStatus.toLowerCase())) {
        return true;
      }
      await this.page.waitForTimeout(1000);
    }
    throw new Error(
      `Task did not reach status ${expectedStatus} within ${timeout}ms`
    );
  }

  /**
   * Get current task status
   */
  async getTaskStatus(): Promise<string | null> {
    const statusBadge = this.page.locator('[data-testid="task-status-badge"]');
    return await statusBadge.textContent();
  }

  /**
   * Start a task
   */
  async startTask() {
    const startButton = this.page.locator('button', { hasText: /start/i });
    await startButton.click();
    await this.page.waitForTimeout(1000);
  }

  /**
   * Stop a task
   */
  async stopTask(confirmDialog = true) {
    const stopButton = this.page.locator('button', { hasText: /stop/i });
    await stopButton.click();

    if (confirmDialog) {
      const confirmButton = this.page.locator('button', {
        hasText: /confirm|yes/i,
      });
      if (await confirmButton.isVisible({ timeout: 2000 })) {
        await confirmButton.click();
      }
    }

    await this.page.waitForTimeout(1000);
  }

  /**
   * Pause a task
   */
  async pauseTask(confirmDialog = true) {
    const pauseButton = this.page.locator('button', { hasText: /pause/i });
    await pauseButton.click();

    if (confirmDialog) {
      const confirmButton = this.page.locator('button', {
        hasText: /confirm|yes/i,
      });
      if (await confirmButton.isVisible({ timeout: 2000 })) {
        await confirmButton.click();
      }
    }

    await this.page.waitForTimeout(1000);
  }

  /**
   * Resume a task
   */
  async resumeTask() {
    const resumeButton = this.page.locator('button', { hasText: /resume/i });
    await resumeButton.click();
    await this.page.waitForTimeout(1000);
  }

  /**
   * Restart a task
   */
  async restartTask(confirmDialog = true) {
    const restartButton = this.page.locator('button', { hasText: /restart/i });
    await restartButton.click();

    if (confirmDialog) {
      const confirmButton = this.page.locator('button', {
        hasText: /confirm|yes/i,
      });
      if (await confirmButton.isVisible({ timeout: 2000 })) {
        await confirmButton.click();
      }
    }

    await this.page.waitForTimeout(1000);
  }

  /**
   * Delete a task
   */
  async deleteTask(confirmDialog = true) {
    const deleteButton = this.page.locator('button', { hasText: /delete/i });
    await deleteButton.click();

    if (confirmDialog) {
      const confirmButton = this.page.locator('button', {
        hasText: /confirm|yes|delete/i,
      });
      await confirmButton.click();
    }

    await this.page.waitForTimeout(1000);
  }

  /**
   * Copy/duplicate a task
   */
  async copyTask() {
    const copyButton = this.page.locator('button', {
      hasText: /copy|duplicate/i,
    });
    await copyButton.click();
    await this.page.waitForTimeout(2000);
  }

  /**
   * Get task card by name
   */
  getTaskCardByName(taskName: string): Locator {
    return this.page.locator(
      `[data-testid="backtest-task-card"], [data-testid="trading-task-card"]`,
      {
        hasText: taskName,
      }
    );
  }

  /**
   * Get first task card
   */
  getFirstTaskCard(): Locator {
    return this.page
      .locator(
        '[data-testid="backtest-task-card"], [data-testid="trading-task-card"]'
      )
      .first();
  }

  /**
   * Click on a task card to view details
   */
  async clickTaskCard(taskCard: Locator) {
    await taskCard.click();
    await this.page.waitForTimeout(1000);
  }

  /**
   * Switch to a specific tab (Events, Logs, Trades, Equity, Metrics)
   */
  async switchToTab(tabName: string) {
    const tab = this.page.locator('button[role="tab"]', {
      hasText: new RegExp(tabName, 'i'),
    });
    await tab.click();
    await this.page.waitForTimeout(500);
  }

  /**
   * Check if metrics panel is visible
   */
  async isMetricsPanelVisible(): Promise<boolean> {
    const metricsPanel = this.page.locator(
      '[data-testid="metrics-panel"], [data-testid="latest-metrics"]'
    );
    return await metricsPanel.isVisible({ timeout: 5000 }).catch(() => false);
  }

  /**
   * Get execution ID from task detail page
   */
  async getExecutionId(): Promise<string | null> {
    const executionIdElement = this.page.locator(
      '[data-testid="execution-id"]'
    );
    return await executionIdElement.textContent();
  }

  /**
   * Check if control buttons are visible
   */
  async areControlButtonsVisible(): Promise<boolean> {
    const controlButtons = this.page.locator(
      '[data-testid="task-control-buttons"]'
    );
    return await controlButtons.isVisible().catch(() => false);
  }
}
