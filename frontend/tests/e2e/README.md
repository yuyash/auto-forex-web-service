# E2E Tests

This directory contains end-to-end tests for the Auto Forex trading application using Playwright.

## Configuration

The Playwright configuration is defined in `frontend/playwright.config.ts` and includes:

- **Test browsers**: Chromium, Firefox, and WebKit
- **Parallel execution**: Tests run in parallel for faster execution
- **Retries**: Automatic retries on CI (2 retries)
- **Screenshots**: Captured on test failure
- **Videos**: Recorded on test failure
- **Traces**: Collected on first retry for debugging

## Prerequisites

- Node.js and npm installed
- Frontend development server running (or will be started automatically)
- Backend API server running on `http://localhost:8000`

## Installation

Playwright is already installed as a dev dependency. To install browsers:

```bash
npx playwright install
```

## Running Tests

```bash
# Run all tests
npm run test:e2e

# Run tests in headed mode (see browser)
npm run test:e2e -- --headed

# Run tests in debug mode
npm run test:e2e -- --debug

# Run specific test file
npm run test:e2e backtest-tasks.spec.ts

# Run tests in specific browser
npm run test:e2e -- --project=chromium
npm run test:e2e -- --project=firefox
npm run test:e2e -- --project=webkit

# Run tests in all browsers
npm run test:e2e -- --project=chromium --project=firefox --project=webkit

# View test report
npx playwright show-report
```

## Test Structure

```
e2e/
├── fixtures/          # Test fixtures for authentication and setup
│   ├── auth.ts       # Authentication fixture
│   └── index.ts      # Fixture exports
├── helpers/          # Helper classes for common operations
│   ├── chart.ts      # Chart interaction helpers
│   ├── form.ts       # Form interaction helpers
│   ├── navigation.ts # Navigation helpers
│   ├── table.ts      # Table interaction helpers
│   ├── task.ts       # Task operation helpers
│   └── index.ts      # Helper exports
└── *.spec.ts         # Test files
```

## Fixtures

### Authentication Fixture

The `authenticatedPage` fixture automatically logs in before each test:

```typescript
import { test, expect } from './fixtures/auth';

test('my test', async ({ authenticatedPage }) => {
  await authenticatedPage.goto('/dashboard');
  // ... test code
});
```

## Helpers

### ChartHelper

Helper for interacting with charts (OHLC, line charts):

```typescript
import { ChartHelper } from './helpers';

const chartHelper = new ChartHelper(page);
await chartHelper.waitForChartRender();
await chartHelper.scrollLeft();
await chartHelper.changeGranularity('300');
```

### NavigationHelper

Helper for page navigation:

```typescript
import { NavigationHelper } from './helpers';

const nav = new NavigationHelper(page);
await nav.goToBacktestTasks();
await nav.goToBacktestTaskDetail(123);
```

### TaskHelper

Helper for task operations (start, stop, pause, resume, restart):

```typescript
import { TaskHelper } from './helpers';

const taskHelper = new TaskHelper(page);
await taskHelper.startTask();
await taskHelper.waitForTaskStatus('running');
await taskHelper.stopTask();
```

### TableHelper

Helper for table interactions (events, logs, trades):

```typescript
import { TableHelper } from './helpers';

const tableHelper = new TableHelper(page);
await tableHelper.waitForTableLoad('events-table');
const rowCount = await tableHelper.getRowCount();
await tableHelper.sortByColumn('Timestamp');
```

### FormHelper

Helper for form interactions:

```typescript
import { FormHelper } from './helpers';

const formHelper = new FormHelper(page);
await formHelper.fillInput('name', 'My Task');
await formHelper.selectOption('configuration', 'config-1');
await formHelper.submitForm();
```

## Writing Tests

### Basic Test Structure

```typescript
import { test, expect } from './fixtures/auth';
import { NavigationHelper, TaskHelper } from './helpers';

test.describe('My Feature', () => {
  test.beforeEach(async ({ authenticatedPage }) => {
    const nav = new NavigationHelper(authenticatedPage);
    await nav.goToBacktestTasks();
  });

  test('should do something', async ({ authenticatedPage }) => {
    const taskHelper = new TaskHelper(authenticatedPage);
    await taskHelper.startTask();
    await taskHelper.waitForTaskStatus('running');

    // Assertions
    expect(await taskHelper.getTaskStatus()).toBe('running');
  });
});
```

### Best Practices

1. **Use helpers**: Leverage helper classes for common operations
2. **Use data-testid**: Prefer `data-testid` attributes for element selection
3. **Wait for state**: Use `waitForLoadState('networkidle')` after navigation
4. **Avoid hardcoded waits**: Use `waitFor` methods instead of `waitForTimeout`
5. **Clean up**: Delete test data created during tests
6. **Isolate tests**: Each test should be independent and not rely on other tests

## Debugging

### Debug Mode

Run tests in debug mode to step through test execution:

```bash
npm run test:e2e -- --debug
```

### View Traces

View traces for failed tests:

```bash
npx playwright show-trace test-results/path-to-trace.zip
```

### Screenshots and Videos

Screenshots and videos are automatically captured on test failure and saved to `test-results/`.

## CI/CD

On CI:

- Tests run with 2 retries
- Tests run sequentially (workers=1)
- Dev server is started automatically
- Test artifacts are saved for debugging

## Environment Variables

- `PLAYWRIGHT_BASE_URL`: Override base URL (default: http://localhost:5173)
- `CI`: Set to enable CI-specific behavior (retries, sequential execution)

## Common Issues

### Port already in use

If port 5173 is already in use, the tests will reuse the existing server. Make sure your dev server is running the latest code.

### Tests timing out

Increase timeout in playwright.config.ts or use `test.setTimeout()` for specific tests.

### Authentication failing

Check that test credentials match your backend configuration. Update `fixtures/auth.ts` if needed.
