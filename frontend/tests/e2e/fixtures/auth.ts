import { test as base, Page } from '@playwright/test';

type AuthFixtures = {
  authenticatedPage: Page;
};

export const test = base.extend<AuthFixtures>({
  authenticatedPage: async ({ page }, use) => {
    // Retry login up to 3 times to handle race conditions with
    // systemSettings loading and parallel browser instances
    for (let attempt = 0; attempt < 3; attempt++) {
      await page.goto('/login');

      // Wait for the login form to be fully rendered
      const emailInput = page.locator('input[name="email"]');
      await emailInput.waitFor({ state: 'visible', timeout: 15000 });

      // Fill in login credentials
      await emailInput.fill('testuser@example.com');
      await page.locator('input[name="password"]').fill('testpassword');

      // Click login button
      await page.locator('button[type="submit"]').click();

      // Wait for navigation to dashboard
      try {
        await page.waitForURL('**/dashboard', { timeout: 10000 });
        break; // Success
      } catch {
        if (attempt === 2) {
          throw new Error(
            'Failed to login after 3 attempts. Current URL: ' + page.url()
          );
        }
        // Wait before retrying
        await page.waitForTimeout(1000);
      }
    }

    // eslint-disable-next-line react-hooks/rules-of-hooks
    await use(page);
  },
});

export { expect } from '@playwright/test';
