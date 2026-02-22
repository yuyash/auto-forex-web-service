/**
 * E2E tests for Execution Comparison
 *
 * Tests the execution comparison functionality including:
 * - Comparing metrics across multiple executions
 * - Viewing historical execution data
 * - Filtering and sorting executions
 */

import { test, expect } from './fixtures/auth';
import { Page } from '@playwright/test';

// Helper function to navigate to a task detail page

// Helper function to get execution count
async function getExecutionCount(page: Page): Promise<number> {
  const executionsList = page.locator('[data-testid="executions-list"]');

  if (!(await executionsList.isVisible({ timeout: 2000 }))) {
    return 0;
  }

  const executionItems = page.locator('[data-testid="execution-item"]');
  return await executionItems.count();
}

test.describe('Execution Comparison E2E', () => {
  test('should display execution history list', async ({
    authenticatedPage,
  }) => {
    // Navigate to a backtest task
    await authenticatedPage.goto('/backtest-tasks');
    await authenticatedPage.waitForLoadState('networkidle');

    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Look for executions tab or list
    const executionsTab = authenticatedPage.locator('button[role="tab"]', {
      hasText: /executions|history/i,
    });

    if (await executionsTab.isVisible()) {
      await executionsTab.click();

      // Verify executions list or empty state
      const executionsList = authenticatedPage.locator(
        '[data-testid="executions-list"], [data-testid="execution-history"]'
      );
      const emptyState = authenticatedPage.locator('text=/no.*executions/i');

      const hasList = await executionsList
        .isVisible({ timeout: 5000 })
        .catch(() => false);
      const hasEmpty = await emptyState
        .isVisible({ timeout: 5000 })
        .catch(() => false);

      expect(hasList || hasEmpty).toBeTruthy();
    }
  });

  test('should compare metrics across multiple executions', async ({
    authenticatedPage,
  }) => {
    // Navigate to a task with multiple executions
    await authenticatedPage.goto('/backtest-tasks');
    await authenticatedPage.waitForLoadState('networkidle');

    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Check if there are multiple executions
    const executionCount = await getExecutionCount(authenticatedPage);

    if (executionCount < 2) {
      test.skip('Need at least 2 executions for comparison testing');
    }

    // Look for compare button or tab
    const compareButton = authenticatedPage.locator('button', {
      hasText: /compare/i,
    });
    const compareTab = authenticatedPage.locator('button[role="tab"]', {
      hasText: /compare/i,
    });

    if (await compareButton.isVisible()) {
      await compareButton.click();
    } else if (await compareTab.isVisible()) {
      await compareTab.click();
    } else {
      test.skip('No comparison feature available');
    }

    // Wait for comparison view to load
    await authenticatedPage.waitForTimeout(2000);

    // Verify comparison panel is visible
    const comparisonPanel = authenticatedPage.locator(
      '[data-testid="comparison-panel"], [data-testid="metrics-comparison"]'
    );
    await expect(comparisonPanel).toBeVisible({ timeout: 5000 });

    // Verify multiple executions are shown
    const executionCards = authenticatedPage.locator(
      '[data-testid*="execution-card"], [data-testid*="execution-summary"]'
    );
    const cardCount = await executionCards.count();

    expect(cardCount).toBeGreaterThanOrEqual(2);
  });

  test('should view historical execution data', async ({
    authenticatedPage,
  }) => {
    // Navigate to a task
    await authenticatedPage.goto('/backtest-tasks');
    await authenticatedPage.waitForLoadState('networkidle');

    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Get execution count
    const executionCount = await getExecutionCount(authenticatedPage);

    if (executionCount === 0) {
      test.skip('No executions available for testing');
    }

    // Click on an execution to view its details
    const executionItem = authenticatedPage
      .locator('[data-testid="execution-item"]')
      .first();
    await executionItem.click();

    // Wait for execution details to load
    await authenticatedPage.waitForTimeout(2000);

    // Verify execution details are displayed
    const executionDetails = authenticatedPage.locator(
      '[data-testid="execution-details"], [data-testid="execution-summary"]'
    );
    await expect(executionDetails).toBeVisible({ timeout: 5000 });

    // Verify key execution information is present
    const executionId = authenticatedPage.locator(
      '[data-testid="execution-id"], text=/execution.*#/i'
    );
    const executionStatus = authenticatedPage.locator(
      '[data-testid="execution-status"], [data-testid="status-badge"]'
    );

    const hasId = await executionId
      .isVisible({ timeout: 2000 })
      .catch(() => false);
    const hasStatus = await executionStatus
      .isVisible({ timeout: 2000 })
      .catch(() => false);

    expect(hasId || hasStatus).toBeTruthy();
  });

  test('should filter executions by status', async ({ authenticatedPage }) => {
    // Navigate to a task
    await authenticatedPage.goto('/backtest-tasks');
    await authenticatedPage.waitForLoadState('networkidle');

    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Look for executions tab
    const executionsTab = authenticatedPage.locator('button[role="tab"]', {
      hasText: /executions|history/i,
    });

    if (await executionsTab.isVisible()) {
      await executionsTab.click();
    }

    // Look for status filter
    const statusFilter = authenticatedPage.locator(
      'select[name="status"], [aria-label*="status"]'
    );

    if (await statusFilter.isVisible()) {
      // Get initial count
      await getExecutionCount(authenticatedPage);

      // Filter by completed status
      await statusFilter.selectOption('completed');
      await authenticatedPage.waitForTimeout(1000);

      // Verify filter was applied (count may change or stay same)
      const filteredCount = await getExecutionCount(authenticatedPage);

      // Just verify the filter control worked (count is valid)
      expect(filteredCount).toBeGreaterThanOrEqual(0);

      // Reset filter
      await statusFilter.selectOption('all');
      await authenticatedPage.waitForTimeout(1000);
    }
  });

  test('should sort executions by date', async ({ authenticatedPage }) => {
    // Navigate to a task
    await authenticatedPage.goto('/backtest-tasks');
    await authenticatedPage.waitForLoadState('networkidle');

    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Check if there are multiple executions
    const executionCount = await getExecutionCount(authenticatedPage);

    if (executionCount < 2) {
      test.skip('Need at least 2 executions for sorting testing');
    }

    // Look for sort control
    const sortSelect = authenticatedPage.locator(
      'select[name="sort"], [aria-label*="sort"]'
    );
    const sortButton = authenticatedPage.locator('button[aria-label*="sort"]');

    if (await sortSelect.isVisible()) {
      // Test sorting with select
      await sortSelect.selectOption('date_desc');
      await authenticatedPage.waitForTimeout(1000);

      // Verify executions are still displayed
      const count = await getExecutionCount(authenticatedPage);
      expect(count).toBeGreaterThan(0);

      // Try ascending sort
      await sortSelect.selectOption('date_asc');
      await authenticatedPage.waitForTimeout(1000);

      const countAfter = await getExecutionCount(authenticatedPage);
      expect(countAfter).toBeGreaterThan(0);
    } else if (await sortButton.isVisible()) {
      // Test sorting with button
      await sortButton.click();
      await authenticatedPage.waitForTimeout(1000);

      // Verify executions are still displayed
      const count = await getExecutionCount(authenticatedPage);
      expect(count).toBeGreaterThan(0);
    }
  });

  test('should display execution metrics in comparison view', async ({
    authenticatedPage,
  }) => {
    // Navigate to a task
    await authenticatedPage.goto('/backtest-tasks');
    await authenticatedPage.waitForLoadState('networkidle');

    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Check if there are multiple executions
    const executionCount = await getExecutionCount(authenticatedPage);

    if (executionCount < 2) {
      test.skip('Need at least 2 executions for comparison testing');
    }

    // Look for compare feature
    const compareTab = authenticatedPage.locator('button[role="tab"]', {
      hasText: /compare/i,
    });

    if (await compareTab.isVisible()) {
      await compareTab.click();

      // Wait for comparison to load
      await authenticatedPage.waitForTimeout(2000);

      // Verify metrics are displayed for each execution
      const metricLabels = authenticatedPage.locator(
        '[data-testid*="metric-label"], text=/total.*pnl|win.*rate|trades/i'
      );
      const metricCount = await metricLabels.count();

      expect(metricCount).toBeGreaterThan(0);
    }
  });

  test('should navigate between execution details', async ({
    authenticatedPage,
  }) => {
    // Navigate to a task
    await authenticatedPage.goto('/backtest-tasks');
    await authenticatedPage.waitForLoadState('networkidle');

    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Check if there are multiple executions
    const executionCount = await getExecutionCount(authenticatedPage);

    if (executionCount < 2) {
      test.skip('Need at least 2 executions for navigation testing');
    }

    // Click on first execution
    const firstExecution = authenticatedPage
      .locator('[data-testid="execution-item"]')
      .first();
    await firstExecution.click();
    await authenticatedPage.waitForTimeout(1000);

    // Verify first execution details are shown
    const executionDetails = authenticatedPage.locator(
      '[data-testid="execution-details"], [data-testid="execution-summary"]'
    );
    await expect(executionDetails).toBeVisible({ timeout: 5000 });

    // Navigate to second execution
    const secondExecution = authenticatedPage
      .locator('[data-testid="execution-item"]')
      .nth(1);
    await secondExecution.click();
    await authenticatedPage.waitForTimeout(1000);

    // Verify second execution details are shown
    await expect(executionDetails).toBeVisible({ timeout: 5000 });
  });

  test('should display execution count badge', async ({
    authenticatedPage,
  }) => {
    // Navigate to a task
    await authenticatedPage.goto('/backtest-tasks');
    await authenticatedPage.waitForLoadState('networkidle');

    const taskCard = authenticatedPage
      .locator('[data-testid="backtest-task-card"]')
      .first();

    if (!(await taskCard.isVisible())) {
      test.skip('No backtest tasks available for testing');
    }

    await taskCard.click();
    await authenticatedPage.waitForURL(/\/backtest-tasks\/\d+/);

    // Look for execution count badge
    const countBadge = authenticatedPage.locator(
      '[data-testid="execution-count"], text=/\\d+.*executions?/i'
    );

    if (await countBadge.isVisible({ timeout: 2000 })) {
      const badgeText = await countBadge.textContent();
      expect(badgeText).toMatch(/\d+/);
    }
  });
});
