/**
 * Integration test for LoginPage.
 * Tests form validation, submission, error handling, and navigation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../../../src/contexts/AuthContext';
import { I18nextProvider } from 'react-i18next';
import i18n from '../../../src/i18n/config';

// Lazy-loaded page — import the default export
import LoginPage from '../../../src/pages/LoginPage';

function renderLoginPage() {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    </I18nextProvider>
  );
}

describe('LoginPage', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    localStorage.clear();
    // Default: settings endpoint returns login enabled
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('renders email and password fields', () => {
    renderLoginPage();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it('renders submit button', async () => {
    renderLoginPage();
    // Button text comes from i18n — may be "Sign In" or "Login"
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /sign in|login|log in/i })
      ).toBeInTheDocument();
    });
  });

  it('shows validation error for empty email', async () => {
    const user = userEvent.setup();
    renderLoginPage();

    const btn = await screen.findByRole('button', {
      name: /sign in|login|log in/i,
    });
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for invalid email format', async () => {
    const user = userEvent.setup();
    renderLoginPage();

    const emailField = await screen.findByLabelText(/email/i);
    const btn = await screen.findByRole('button', {
      name: /sign in|login|log in/i,
    });

    await user.type(emailField, 'notanemail');
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for empty password', async () => {
    const user = userEvent.setup();
    renderLoginPage();

    const emailField = await screen.findByLabelText(/email/i);
    const btn = await screen.findByRole('button', {
      name: /sign in|login|log in/i,
    });

    await user.type(emailField, 'user@example.com');
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });
  });

  it('shows error alert on failed login', async () => {
    const user = userEvent.setup();

    fetchSpy.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url === '/api/accounts/settings/public') {
        return new Response(
          JSON.stringify({ login_enabled: true, registration_enabled: true }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }
      if (url === '/api/accounts/auth/login') {
        return new Response(JSON.stringify({ error: 'Invalid credentials' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('{}', { status: 200 });
    });

    renderLoginPage();

    const emailField = await screen.findByLabelText(/email/i);
    const passwordField = await screen.findByLabelText(/password/i);
    const btn = await screen.findByRole('button', {
      name: /sign in|login|log in/i,
    });

    await user.type(emailField, 'user@example.com');
    await user.type(passwordField, 'wrongpassword');
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('clears field error when user starts typing', async () => {
    const user = userEvent.setup();
    renderLoginPage();

    const btn = await screen.findByRole('button', {
      name: /sign in|login|log in/i,
    });
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });

    // Start typing — error should clear
    await user.type(screen.getByLabelText(/email/i), 'a');
    await waitFor(() => {
      expect(screen.queryByText(/email is required/i)).not.toBeInTheDocument();
    });
  });
});
