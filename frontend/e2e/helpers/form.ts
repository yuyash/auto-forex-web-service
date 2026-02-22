import { Page } from '@playwright/test';

/**
 * Form helper for common form operations
 */
export class FormHelper {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  /**
   * Fill a text input by name
   */
  async fillInput(name: string, value: string) {
    const input = this.page.locator(`input[name="${name}"]`);
    await input.fill(value);
  }

  /**
   * Fill a textarea by name
   */
  async fillTextarea(name: string, value: string) {
    const textarea = this.page.locator(`textarea[name="${name}"]`);
    await textarea.fill(value);
  }

  /**
   * Select an option from a dropdown by name
   */
  async selectOption(name: string, value: string) {
    const select = this.page.locator(`select[name="${name}"]`);
    await select.selectOption(value);
  }

  /**
   * Select an option from a MUI Autocomplete/Select
   */
  async selectMuiOption(label: string, optionText: string) {
    // Click on the autocomplete/select
    const autocomplete = this.page.locator(
      `[role="combobox"][aria-label*="${label}" i]`
    );
    await autocomplete.click();
    await this.page.waitForTimeout(500);

    // Select the option
    const option = this.page.locator(
      `[role="option"]:has-text("${optionText}")`
    );
    await option.click();
    await this.page.waitForTimeout(300);
  }

  /**
   * Check a checkbox by name
   */
  async checkCheckbox(name: string) {
    const checkbox = this.page.locator(
      `input[type="checkbox"][name="${name}"]`
    );
    await checkbox.check();
  }

  /**
   * Uncheck a checkbox by name
   */
  async uncheckCheckbox(name: string) {
    const checkbox = this.page.locator(
      `input[type="checkbox"][name="${name}"]`
    );
    await checkbox.uncheck();
  }

  /**
   * Select a radio button by name and value
   */
  async selectRadio(name: string, value: string) {
    const radio = this.page.locator(
      `input[type="radio"][name="${name}"][value="${value}"]`
    );
    await radio.check();
  }

  /**
   * Submit a form
   */
  async submitForm() {
    const submitButton = this.page.locator('button[type="submit"]');
    await submitButton.click();
  }

  /**
   * Cancel a form
   */
  async cancelForm() {
    const cancelButton = this.page.locator('button', { hasText: /cancel/i });
    await cancelButton.click();
  }

  /**
   * Wait for form to be visible
   */
  async waitForForm(timeout = 10000) {
    await this.page.waitForSelector('form', { timeout });
  }

  /**
   * Check if form has validation errors
   */
  async hasValidationErrors(): Promise<boolean> {
    const errorMessages = this.page.locator(
      '.MuiFormHelperText-root.Mui-error, [role="alert"]'
    );
    const count = await errorMessages.count();
    return count > 0;
  }

  /**
   * Get validation error messages
   */
  async getValidationErrors(): Promise<string[]> {
    const errorMessages = this.page.locator(
      '.MuiFormHelperText-root.Mui-error, [role="alert"]'
    );
    const count = await errorMessages.count();
    const errors: string[] = [];

    for (let i = 0; i < count; i++) {
      const text = await errorMessages.nth(i).textContent();
      if (text) errors.push(text);
    }

    return errors;
  }

  /**
   * Fill a complete form with data
   */
  async fillForm(formData: Record<string, string>) {
    for (const [name, value] of Object.entries(formData)) {
      // Try input first
      const input = this.page.locator(`input[name="${name}"]`);
      if (await input.isVisible({ timeout: 1000 }).catch(() => false)) {
        await input.fill(value);
        continue;
      }

      // Try textarea
      const textarea = this.page.locator(`textarea[name="${name}"]`);
      if (await textarea.isVisible({ timeout: 1000 }).catch(() => false)) {
        await textarea.fill(value);
        continue;
      }

      // Try select
      const select = this.page.locator(`select[name="${name}"]`);
      if (await select.isVisible({ timeout: 1000 }).catch(() => false)) {
        await select.selectOption(value);
      }
    }
  }

  /**
   * Get form field value
   */
  async getFieldValue(name: string): Promise<string | null> {
    const input = this.page.locator(
      `input[name="${name}"], textarea[name="${name}"]`
    );
    return await input.inputValue();
  }

  /**
   * Check if submit button is disabled
   */
  async isSubmitDisabled(): Promise<boolean> {
    const submitButton = this.page.locator('button[type="submit"]');
    return await submitButton.isDisabled();
  }

  /**
   * Wait for form submission to complete
   */
  async waitForSubmission(timeout = 10000) {
    // Wait for loading indicator or form to disappear
    await this.page.waitForTimeout(1000);

    // Check if form is still visible
    const form = this.page.locator('form');
    try {
      await form.waitFor({ state: 'hidden', timeout });
    } catch {
      // Form might still be visible if submission failed
    }
  }
}
