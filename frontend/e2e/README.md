# End-to-End Tests with Playwright

This directory contains end-to-end tests for the Auto Forex Trading System using Playwright.

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

### Run all tests

```bash
npm run test:e2e
```

### Run tests in headed mode (see browser)

```bash
npx playwright test --headed
```

### Run specific test file

```bash
npx playwright test e2e/chart-scrolling.spec.ts
```

### Run tests in debug mode

```bash
npx playwright test --debug
```

### Run tests in UI mode (interactive)

```bash
npx playwright test --ui
```

## Test Structure

### Fixtures

- `fixtures/auth.ts` - Authentication fixtures for logged-in user tests

### Helpers

- `helpers/chart.ts` - Helper functions for interacting with the OHLC chart component

### Test Files

- `chart-scrolling.spec.ts` - Tests for chart scrolling functionality (older/newer data loading)
- `chart-controls.spec.ts` - Tests for instrument and granularity changes
- `chart-errors.spec.ts` - Tests for error handling scenarios

## Writing Tests

### Using Authentication Fixture

```typescript
import { test, expect } from './fixtures/auth';

test('my authenticated test', async ({ authenticatedPage }) => {
  // authenticatedPage is already logged in
  await authenticatedPage.goto('/dashboard');
  // ... rest of test
});
```

### Using Chart Helper

```typescript
import { ChartHelper } from './helpers/chart';

test('chart interaction', async ({ page }) => {
  await page.goto('/dashboard');

  const chart = new ChartHelper(page);
  await chart.waitForChartRender();
  await chart.scrollLeft();
  // ... rest of test
});
```

## Debugging

### View test report

After running tests, view the HTML report:

```bash
npx playwright show-report
```

### View traces

If a test fails, you can view the trace:

```bash
npx playwright show-trace trace.zip
```

## CI/CD

Tests are configured to run in CI with:

- 2 retries on failure
- Single worker (no parallelization)
- Automatic server startup

## Tips

1. **Waiting for elements**: Use `waitFor()` instead of `waitForTimeout()` when possible
2. **Selectors**: Prefer data-testid attributes or accessible roles over CSS classes
3. **Assertions**: Use Playwright's built-in assertions for better error messages
4. **Screenshots**: Automatically captured on failure
5. **Videos**: Recorded on failure for debugging

## Common Issues

### Port already in use

If port 5173 is already in use, the tests will reuse the existing server. Make sure your dev server is running the latest code.

### Tests timing out

Increase timeout in playwright.config.ts or use `test.setTimeout()` for specific tests.

### Authentication failing

Check that test credentials match your backend configuration. Update `fixtures/auth.ts` if needed.
