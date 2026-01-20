/**
 * E2E tests for Trading Tasks
 *
 * Tests the complete trading task workflow including:
 * - Creating trading tasks
 * - Starting and stopping tasks
 * - Resume and restart functionality
 * - Viewing metrics with different granularities
 * - Viewing events, logs, and trades tabs
 *
 * Requirements: 11.10, 11.11, 11.12, 11.13, 11.14, 11.15, 11.16, 11.17, 11.18
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

// Helper function to navigate to trading tasks page
async function navigateToTradingTasks(page: Page) {
  await page.goto('/trading-tasks');
  await page.waitForLoadState('networkidle');
}

test.describe('Trading Tasks E2E', () => {
  test.beforeEach(async ({ authenticatedPage }) => {
    await navigateToTradingTasks(authenticatedPage);
  });

  test('should display trading tasks list', async ({ authenticatedPage }) => {
    // Verify page title
    await expect(authenticatedPage.locator('h1, h4')).toContainText(/trading/i);

    // Verify task list or empty state is visible
    const taskList = authenticatedPage.locator(
      '[data-testid="trading-task-list"]'
    );
    const emptyState = authenticatedPage.locator('text=/no.*tasks/i');

    const hasTaskList = await taskList.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);

    expect(hasTaskList || hasEmptyState).toBeTruthy();
  });

  test('should create a new trading task', async ({ authenticatedPage }) => {
    // Click create button
    const createButton = authenticatedPage.locator('button', {
      hasText: /create|new/i,
    });
    await createButton.click();

    // Wait for form to appear
    await authenticatedPage.waitForSelector('form');

    // Fill in task details
    await authenticatedPage.fill('input[name="name"]', 'E2E Test Trading Task');
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

    // Select OANDA account
    const accountSelect = authenticatedPage
      .locator('select[name="account"], [role="combobox"]')
      .nth(1);
    if (await accountSelect.isVisible()) {
      await accountSelect.click();
      await authenticatedPage.waitForTimeout(500);

      const firstAccount = authenticatedPage.locator('[role="option"]').first();
      if (await firstAccount.isVisible()) {
        await firstAccount.click();
      }
    }

    // Submit form
    const submitButton = authenticatedPage.locator('button[type="submit"]');
    await submitButton.click();

    // Wait for redirect to task detail page or list
    await authenticatedPage.waitForURL(/\/trading-tasks/, { timeout: 10000 });

    // Verify task was created
    await expect(
      authenticatedPage.locator('text=/E2E Test Trading Task/i')
    ).toBeVisible();
  });

  test('should start, view metrics, and stop a trading task', async ({
    authenticatedPage,
  }) => {
    // Find first task or create one
    const taskCard = authenticatedPage
      .locator('[data-testid="trading-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No trading tasks available for testing');
    }

    // Click on task to view details
    await taskCard.click();
    await authenticatedPage.waitForURL(/\/trading-tasks\/\d+/);

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

  test('should resume a paused trading task', async ({ authenticatedPage }) => {
    // Find a paused task or create and pause one
    const taskCard = authenticatedPage
      .locator('[data-testid="trading-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No trading tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/trading-tasks\/\d+/);

    // If task is not paused, start and pause it first
    const statusBadge = authenticatedPage.locator(
      '[data-testid="task-status-badge"]'
    );
    const currentStatus = await statusBadge.textContent();

    if (!currentStatus?.toLowerCase().includes('paused')) {
      // Start task if not running
      const startButton = authenticatedPage.locator('button', {
        hasText: /start/i,
      });
      if (await startButton.isVisible()) {
        await startButton.click();
        await waitForTaskStatus(authenticatedPage, 'running');
      }

      // Pause the task
      const pauseButton = authenticatedPage.locator('button', {
        hasText: /pause/i,
      });
      if (await pauseButton.isVisible()) {
        await pauseButton.click();
        await waitForTaskStatus(authenticatedPage, 'paused');
      }
    }

    // Now resume the task
    const resumeButton = authenticatedPage.locator('button', {
      hasText: /resume/i,
    });
    if (await resumeButton.isVisible()) {
      await resumeButton.click();

      // Wait for task to resume
      await waitForTaskStatus(authenticatedPage, 'running');

      // Verify task is running
      await expect(statusBadge).toContainText(/running/i);

      // Stop the task to clean up
      const stopButton = authenticatedPage.locator('button', {
        hasText: /stop/i,
      });
      if (await stopButton.isVisible()) {
        await stopButton.click();
        const confirmButton = authenticatedPage.locator('button', {
          hasText: /confirm|yes/i,
        });
        if (await confirmButton.isVisible({ timeout: 2000 })) {
          await confirmButton.click();
        }
      }
    }
  });

  test('should restart a trading task', async ({ authenticatedPage }) => {
    // Find a stopped task
    const taskCard = authenticatedPage
      .locator('[data-testid="trading-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No trading tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/trading-tasks\/\d+/);

    // Get current execution count
    const executionsList = authenticatedPage.locator(
      '[data-testid="executions-list"]'
    );
    let initialExecutionCount = 0;
    if (await executionsList.isVisible({ timeout: 2000 })) {
      const executionItems = authenticatedPage.locator(
        '[data-testid="execution-item"]'
      );
      initialExecutionCount = await executionItems.count();
    }

    // Find and click restart button
    const restartButton = authenticatedPage.locator('button', {
      hasText: /restart/i,
    });

    if (await restartButton.isVisible()) {
      await restartButton.click();

      // Confirm restart if dialog appears
      const confirmButton = authenticatedPage.locator('button', {
        hasText: /confirm|yes|restart/i,
      });
      if (await confirmButton.isVisible({ timeout: 2000 })) {
        await confirmButton.click();
      }

      // Wait for new execution to start
      await waitForTaskStatus(authenticatedPage, 'running');

      // Verify new execution was created
      await authenticatedPage.waitForTimeout(2000);
      if (await executionsList.isVisible({ timeout: 2000 })) {
        const executionItems = authenticatedPage.locator(
          '[data-testid="execution-item"]'
        );
        const newExecutionCount = await executionItems.count();
        expect(newExecutionCount).toBeGreaterThan(initialExecutionCount);
      }

      // Stop the task to clean up
      const stopButton = authenticatedPage.locator('button', {
        hasText: /stop/i,
      });
      if (await stopButton.isVisible()) {
        await stopButton.click();
        const confirmButton = authenticatedPage.locator('button', {
          hasText: /confirm|yes/i,
        });
        if (await confirmButton.isVisible({ timeout: 2000 })) {
          await confirmButton.click();
        }
      }
    }
  });

  test('should view equity curve with different granularities', async ({
    authenticatedPage,
  }) => {
    // Navigate to a task with execution data
    const taskCard = authenticatedPage
      .locator('[data-testid="trading-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No trading tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/trading-tasks\/\d+/);

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
      .locator('[data-testid="trading-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No trading tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/trading-tasks\/\d+/);

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

  test('should display task control buttons with correct states', async ({
    authenticatedPage,
  }) => {
    const taskCard = authenticatedPage
      .locator('[data-testid="trading-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No trading tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/trading-tasks\/\d+/);

    // Verify control buttons exist
    const controlButtons = authenticatedPage.locator(
      '[data-testid="task-control-buttons"]'
    );
    await expect(controlButtons).toBeVisible();

    // Check for start/stop/pause/resume/restart buttons
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
    const restartButton = authenticatedPage.locator('button', {
      hasText: /restart/i,
    });

    // At least one control button should be visible
    const hasAnyButton =
      (await startButton.isVisible().catch(() => false)) ||
      (await stopButton.isVisible().catch(() => false)) ||
      (await pauseButton.isVisible().catch(() => false)) ||
      (await resumeButton.isVisible().catch(() => false)) ||
      (await restartButton.isVisible().catch(() => false));

    expect(hasAnyButton).toBeTruthy();
  });

  test('should display metrics panel with latest data', async ({
    authenticatedPage,
  }) => {
    const taskCard = authenticatedPage
      .locator('[data-testid="trading-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No trading tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/trading-tasks\/\d+/);

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

  test('should display real-time updates for running task', async ({
    authenticatedPage,
  }) => {
    const taskCard = authenticatedPage
      .locator('[data-testid="trading-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No trading tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/trading-tasks\/\d+/);

    // Start task if not running
    const startButton = authenticatedPage.locator('button', {
      hasText: /start/i,
    });
    if (await startButton.isVisible()) {
      await startButton.click();
      await waitForTaskStatus(authenticatedPage, 'running');

      // Wait for metrics to update
      await authenticatedPage.waitForTimeout(5000);

      // Verify metrics panel is updating
      const metricsPanel = authenticatedPage.locator(
        '[data-testid="metrics-panel"]'
      );
      await expect(metricsPanel).toBeVisible();

      // Stop the task
      const stopButton = authenticatedPage.locator('button', {
        hasText: /stop/i,
      });
      if (await stopButton.isVisible()) {
        await stopButton.click();
        const confirmButton = authenticatedPage.locator('button', {
          hasText: /confirm|yes/i,
        });
        if (await confirmButton.isVisible({ timeout: 2000 })) {
          await confirmButton.click();
        }
      }
    }
  });

  test('should delete a trading task', async ({ authenticatedPage }) => {
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

      // Select account
      const accountSelect = authenticatedPage
        .locator('select[name="account"], [role="combobox"]')
        .nth(1);
      if (await accountSelect.isVisible()) {
        await accountSelect.click();
        await authenticatedPage.waitForTimeout(500);

        const firstAccount = authenticatedPage
          .locator('[role="option"]')
          .first();
        if (await firstAccount.isVisible()) {
          await firstAccount.click();
        }
      }

      const submitButton = authenticatedPage.locator('button[type="submit"]');
      await submitButton.click();

      await authenticatedPage.waitForURL(/\/trading-tasks/);
    }

    // Find the task we just created
    const taskToDelete = authenticatedPage
      .locator('text=/E2E Test Task to Delete/i')
      .first();

    if (await taskToDelete.isVisible()) {
      // Click on task
      await taskToDelete.click();
      await authenticatedPage.waitForURL(/\/trading-tasks\/\d+/);

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
      await authenticatedPage.waitForURL(/\/trading-tasks$/);

      // Verify task is no longer in list
      await expect(
        authenticatedPage.locator('text=/E2E Test Task to Delete/i')
      ).not.toBeVisible();
    }
  });
});
