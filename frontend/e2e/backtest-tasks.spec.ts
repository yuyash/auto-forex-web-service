/**
 * E2E tests for Backtest Tasks
 *
 * Tests the complete backtest task workflow including:
 * - Creating backtest tasks
 * - Starting and stopping tasks
 * - Viewing metrics with different granularities
 * - Viewing events, logs, and trades tabs
 * - Copying and deleting tasks
 *
 */

import { test, expect } from './fixtures/auth';
import { Page } from '@playwright/test';

// Helper function to wait for task status
async function waitForTaskStatus(
  page: Page,
  expectedStatus: string,
  timeout = 30000
) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    const statusBadge = page.locator('[data-testid="task-status-badge"]');
    const status = await statusBadge.textContent();
    if (status?.toLowerCase().includes(expectedStatus.toLowerCase())) {
      return true;
    }
    await page.waitForTimeout(1000);
  }
  throw new Error(
    `Task did not reach status ${expectedStatus} within ${timeout}ms`
  );
}

// Helper function to navigate to backtest tasks page
async function navigateToBacktestTasks(page: Page) {
  await page.goto('/backtest-tasks');
  await page.waitForLoadState('networkidle');
}

test.describe('Backtest Tasks E2E', () => {
  test.beforeEach(async ({ authenticatedPage }) => {
    await navigateToBacktestTasks(authenticatedPage);
  });

  test('should display backtest tasks list', async ({ authenticatedPage }) => {
    // Verify page title
    await expect(authenticatedPage.locator('h1, h4')).toContainText(
      /backtest/i
    );

    // Verify task list or empty state is visible
    const taskList = authenticatedPage.locator(
      '[data-testid="backtest-task-list"]'
    );
    const emptyState = authenticatedPage.locator('text=/no.*tasks/i');

    const hasTaskList = await taskList.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);

    expect(hasTaskList || hasEmptyState).toBeTruthy();
  });

  test('should create a new backtest task', async ({ authenticatedPage }) => {
    // Click create button
    const createButton = authenticatedPage.locator('button', {
      hasText: /create|new/i,
    });
    await createButton.click();

    // Wait for form to appear
    await authenticatedPage.waitForSelector('form');

    // Fill in task details
    await authenticatedPage.fill(
      'input[name="name"]',
      'E2E Test Backtest Task'
    );
    await authenticatedPage.fill(
      'textarea[name="description"]',
      'Created by E2E test'
    );

    // Select a configuration (assuming at least one exists)
    const configSelect = authenticatedPage
      .locator('select[name="configuration"], [role="combobox"]')
      .first();
    await configSelect.click();
    await authenticatedPage.waitForTimeout(500);

    // Select first available option
    const firstOption = authenticatedPage.locator('[role="option"]').first();
    if (await firstOption.isVisible()) {
      await firstOption.click();
    }

    // Submit form
    const submitButton = authenticatedPage.locator('button[type="submit"]');
    await submitButton.click();

    // Wait for redirect to task detail page or list
    await authenticatedPage.waitForURL(/\/backtest-tasks/, { timeout: 10000 });

    // Verify task was created
    await expect(
      authenticatedPage.locator('text=/E2E Test Backtest Task/i')
    ).toBeVisible();
  });

  test('should start, view metrics, and stop a backtest task', async ({
    authenticatedPage,
  }) => {
    // Find first task or create one
    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    // Click on task to view details
    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Start the task
    const startButton = authenticatedPage.locator('button', {
      hasText: /start/i,
    });
    if (await startButton.isVisible()) {
      await startButton.click();

      // Wait for task to start
      await waitForTaskStatus(authenticatedPage, 'running');

      // Verify metrics are displayed
      await expect(
        authenticatedPage.locator('[data-testid="metrics-panel"]')
      ).toBeVisible({ timeout: 10000 });

      // Stop the task
      const stopButton = authenticatedPage.locator('button', {
        hasText: /stop|pause/i,
      });
      await stopButton.click();

      // Confirm stop if dialog appears
      const confirmButton = authenticatedPage.locator('button', {
        hasText: /confirm|yes/i,
      });
      if (await confirmButton.isVisible({ timeout: 2000 })) {
        await confirmButton.click();
      }

      // Wait for task to stop
      await waitForTaskStatus(authenticatedPage, 'stopped');
    }
  });

  test('should view equity curve with different granularities', async ({
    authenticatedPage,
  }) => {
    // Navigate to a completed task with data
    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Click on Equity tab
    const equityTab = authenticatedPage.locator('button[role="tab"]', {
      hasText: /equity/i,
    });
    await equityTab.click();

    // Wait for chart to load
    await authenticatedPage.waitForSelector(
      '[data-testid="equity-chart"], canvas',
      { timeout: 10000 }
    );

    // Test different granularities
    const granularities = ['60', '300', '3600']; // 1min, 5min, 1hour

    for (const granularity of granularities) {
      const granularitySelect = authenticatedPage.locator(
        'select[name="granularity"], [aria-label*="granularity"]'
      );

      if (await granularitySelect.isVisible()) {
        await granularitySelect.selectOption(granularity);

        // Wait for chart to update
        await authenticatedPage.waitForTimeout(1000);

        // Verify chart is still visible
        await expect(
          authenticatedPage.locator('[data-testid="equity-chart"], canvas')
        ).toBeVisible();
      }
    }
  });

  test('should view events, logs, and trades tabs', async ({
    authenticatedPage,
  }) => {
    // Navigate to a task with execution data
    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Test Events tab
    const eventsTab = authenticatedPage.locator('button[role="tab"]', {
      hasText: /events/i,
    });
    if (await eventsTab.isVisible()) {
      await eventsTab.click();

      // Verify events table or empty state
      const eventsTable = authenticatedPage.locator(
        '[data-testid="events-table"], table'
      );
      const emptyState = authenticatedPage.locator('text=/no.*events/i');

      const hasTable = await eventsTable
        .isVisible({ timeout: 5000 })
        .catch(() => false);
      const hasEmpty = await emptyState
        .isVisible({ timeout: 5000 })
        .catch(() => false);

      expect(hasTable || hasEmpty).toBeTruthy();
    }

    // Test Logs tab
    const logsTab = authenticatedPage.locator('button[role="tab"]', {
      hasText: /logs/i,
    });
    if (await logsTab.isVisible()) {
      await logsTab.click();

      // Verify logs table or empty state
      const logsTable = authenticatedPage.locator(
        '[data-testid="logs-table"], table'
      );
      const emptyState = authenticatedPage.locator('text=/no.*logs/i');

      const hasTable = await logsTable
        .isVisible({ timeout: 5000 })
        .catch(() => false);
      const hasEmpty = await emptyState
        .isVisible({ timeout: 5000 })
        .catch(() => false);

      expect(hasTable || hasEmpty).toBeTruthy();
    }

    // Test Trades tab
    const tradesTab = authenticatedPage.locator('button[role="tab"]', {
      hasText: /trades/i,
    });
    if (await tradesTab.isVisible()) {
      await tradesTab.click();

      // Verify trades table or empty state
      const tradesTable = authenticatedPage.locator(
        '[data-testid="trades-table"], table'
      );
      const emptyState = authenticatedPage.locator('text=/no.*trades/i');

      const hasTable = await tradesTable
        .isVisible({ timeout: 5000 })
        .catch(() => false);
      const hasEmpty = await emptyState
        .isVisible({ timeout: 5000 })
        .catch(() => false);

      expect(hasTable || hasEmpty).toBeTruthy();
    }
  });

  test('should copy a backtest task', async ({ authenticatedPage }) => {
    // Find first task
    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    // Get initial task count
    const initialCount = await authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .count();

    // Click on task to view details
    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Find and click copy button
    const copyButton = authenticatedPage.locator('button', {
      hasText: /copy|duplicate/i,
    });

    if (await copyButton.isVisible()) {
      await copyButton.click();

      // Wait for copy operation to complete
      await authenticatedPage.waitForTimeout(2000);

      // Navigate back to list
      await navigateToBacktestTasks(authenticatedPage);

      // Verify task count increased
      const newCount = await authenticatedPage
        .locator('[data-testid="backtest-task-card"]')
        .count();
      expect(newCount).toBeGreaterThan(initialCount);
    }
  });

  test('should delete a backtest task', async ({ authenticatedPage }) => {
    // Create a task specifically for deletion
    const createButton = authenticatedPage.locator('button', {
      hasText: /create|new/i,
    });

    if (await createButton.isVisible()) {
      await createButton.click();
      await authenticatedPage.waitForSelector('form');

      await authenticatedPage.fill(
        'input[name="name"]',
        'E2E Test Task to Delete'
      );
      await authenticatedPage.fill(
        'textarea[name="description"]',
        'Will be deleted'
      );

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

      await authenticatedPage.waitForURL(/\/backtest-tasks/);
    }

    // Find the task we just created
    const taskToDelete = authenticatedPage
      .locator('text=/E2E Test Task to Delete/i')
      .first();

    if (await taskToDelete.isVisible()) {
      // Click on task
      await taskToDelete.click();
      await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

      // Find and click delete button
      const deleteButton = authenticatedPage.locator('button', {
        hasText: /delete/i,
      });
      await deleteButton.click();

      // Confirm deletion
      const confirmButton = authenticatedPage.locator('button', {
        hasText: /confirm|yes|delete/i,
      });
      await confirmButton.click();

      // Wait for redirect to list
      await authenticatedPage.waitForURL(/\/backtest-tasks$/);

      // Verify task is no longer in list
      await expect(
        authenticatedPage.locator('text=/E2E Test Task to Delete/i')
      ).not.toBeVisible();
    }
  });

  test('should display task control buttons with correct states', async ({
    authenticatedPage,
  }) => {
    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Verify control buttons exist
    const controlButtons = authenticatedPage.locator(
      '[data-testid="task-control-buttons"]'
    );
    await expect(controlButtons).toBeVisible();

    // Check for start/stop/pause/resume buttons
    const startButton = authenticatedPage.locator('button', {
      hasText: /start/i,
    });
    const stopButton = authenticatedPage.locator('button', {
      hasText: /stop/i,
    });
    const pauseButton = authenticatedPage.locator('button', {
      hasText: /pause/i,
    });
    const resumeButton = authenticatedPage.locator('button', {
      hasText: /resume/i,
    });

    // At least one control button should be visible
    const hasAnyButton =
      (await startButton.isVisible().catch(() => false)) ||
      (await stopButton.isVisible().catch(() => false)) ||
      (await pauseButton.isVisible().catch(() => false)) ||
      (await resumeButton.isVisible().catch(() => false));

    expect(hasAnyButton).toBeTruthy();
  });

  test('should display metrics panel with latest data', async ({
    authenticatedPage,
  }) => {
    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Look for metrics display
    const metricsPanel = authenticatedPage.locator(
      '[data-testid="metrics-panel"], [data-testid="latest-metrics"]'
    );

    if (await metricsPanel.isVisible({ timeout: 5000 })) {
      // Verify some metric fields are present
      const metricCards = authenticatedPage.locator(
        '[data-testid*="metric-card"]'
      );
      const count = await metricCards.count();

      expect(count).toBeGreaterThan(0);
    }
  });
});
