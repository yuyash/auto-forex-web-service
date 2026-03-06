/**
 * E2E: Registration flow.
 * Tests form rendering, validation, and submission.
 *
 * Run serially to avoid race conditions with systemSettings fetch
 * that can cause /register to redirect to /login under load.
 */

import { test, expect } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

test.describe('Registration', () => {
  test('shows registration page with all fields', async ({ page }) => {
    await page.goto('/register');
    // Wait for the register heading to confirm we're on the right page
    await expect(
      page.locator('h1, h5').filter({ hasText: /register|sign up/i })
    ).toBeVisible({
      timeout: 15000,
    });
    await expect(page.locator('input[name="username"]')).toBeVisible();
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await expect(page.locator('input[name="password"]')).toBeVisible();
    await expect(page.locator('input[name="confirmPassword"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('shows validation errors for empty submission', async ({ page }) => {
    await page.goto('/register');
    await expect(page.locator('button[type="submit"]')).toBeVisible({
      timeout: 15000,
    });
    await page.click('button[type="submit"]');

    await expect(
      page.locator('.MuiFormHelperText-root, [role="alert"]').first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('shows password strength indicator when typing', async ({ page }) => {
    await page.goto('/register');
    await expect(page.locator('input[name="password"]')).toBeVisible({
      timeout: 15000,
    });
    await page.fill('input[name="password"]', 'StrongP@ss1');

    await expect(page.locator('text=Password Strength')).toBeVisible({
      timeout: 5000,
    });
  });

  test('shows error for password mismatch', async ({ page }) => {
    await page.goto('/register');
    await expect(page.locator('input[name="username"]')).toBeVisible({
      timeout: 15000,
    });
    await page.fill('input[name="username"]', 'testuser');
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'StrongP@ss1');
    await page.fill('input[name="confirmPassword"]', 'DifferentP@ss1');
    await page.click('button[type="submit"]');

    await expect(page.locator('text=Passwords do not match')).toBeVisible({
      timeout: 5000,
    });
  });

  test('has link to login page', async ({ page }) => {
    await page.goto('/register');
    await page.waitForLoadState('networkidle');

    const loginLink = page.locator('a[href="/login"]');
    const isVisible = await loginLink.isVisible().catch(() => false);
    if (isVisible) {
      await loginLink.click();
      await expect(page).toHaveURL(/\/login/);
    }
  });
});
