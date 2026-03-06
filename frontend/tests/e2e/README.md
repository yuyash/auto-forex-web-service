# E2E Tests

End-to-end tests using Playwright. These test full user flows against a running application.

## Test Files

| File                     | Coverage                                   |
| ------------------------ | ------------------------------------------ |
| `auth.spec.ts`           | Login form, route protection, validation   |
| `dashboard.spec.ts`      | Dashboard widgets, chart controls          |
| `navigation.spec.ts`     | Sidebar navigation, breadcrumbs, 404       |
| `backtest-tasks.spec.ts` | Backtest task list, detail, tab navigation |
| `trading-tasks.spec.ts`  | Trading task list, detail, controls        |
| `registration.spec.ts`   | Registration form, validation, strength    |
| `configurations.spec.ts` | Config listing, search, filter, create nav |
| `settings.spec.ts`       | Settings and profile page rendering        |

## Prerequisites

- Frontend dev server running (`npm run dev`)
- Backend API server running (`http://localhost:8000`)
- Playwright browsers installed: `npx playwright install`

## Running

```bash
npm run test:e2e                          # all tests
npm run test:e2e -- --project=chromium    # single browser
npm run test:e2e -- --headed              # see browser
npm run test:e2e -- --debug               # step through
npx playwright show-report                # view report
```

## Structure

```
e2e/
├── fixtures/       # Auth fixture (auto-login)
├── helpers/        # Reusable helpers (form, task, table, chart, navigation)
└── *.spec.ts       # Test files
```

## Writing Tests

Use the `authenticatedPage` fixture for tests that require login:

```typescript
import { test, expect } from './fixtures';

test('my test', async ({ authenticatedPage }) => {
  await authenticatedPage.goto('/dashboard');
});
```

Use `@playwright/test` directly for unauthenticated tests (e.g., login page).
