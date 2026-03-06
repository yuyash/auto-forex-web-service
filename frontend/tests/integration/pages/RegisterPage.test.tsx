/**
 * Integration tests for RegisterPage.
 * Tests form rendering, validation, password strength, submission, and registration-disabled state.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../../../src/contexts/AuthContext';
import { I18nextProvider } from 'react-i18next';
import i18n from '../../../src/i18n/config';
import RegisterPage from '../../../src/pages/RegisterPage';

let fetchSpy: ReturnType<typeof vi.spyOn>;

function mockFetch(overrides: Record<string, () => Response> = {}) {
  fetchSpy.mockImplementation(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString();
    if (overrides[url]) return overrides[url]();
    if (url === '/api/accounts/settings/public') {
      return new Response(
        JSON.stringify({ login_enabled: true, registration_enabled: true }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    }
    return new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
}

function renderRegisterPage() {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={['/register']}>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>
    </I18nextProvider>
  );
}

describe('RegisterPage', () => {
  beforeEach(() => {
    localStorage.clear();
    fetchSpy = vi.spyOn(globalThis, 'fetch');
    mockFetch();
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('renders all form fields', async () => {
    renderRegisterPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    });
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
  });

  it('shows validation error for empty username', async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    const btn = await screen.findByRole('button', {
      name: /register|sign up/i,
    });
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/username is required/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for short username', async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    const usernameField = await screen.findByLabelText(/username/i);
    await user.type(usernameField, 'ab');

    const btn = screen.getByRole('button', { name: /register|sign up/i });
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/at least 3 characters/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for invalid email', async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    const usernameField = await screen.findByLabelText(/username/i);
    const emailField = screen.getByLabelText(/email/i);

    await user.type(usernameField, 'testuser');
    await user.type(emailField, 'notanemail');

    const btn = screen.getByRole('button', { name: /register|sign up/i });
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for short password', async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    const usernameField = await screen.findByLabelText(/username/i);
    const emailField = screen.getByLabelText(/email/i);
    const passwordField = screen.getByLabelText(/^password/i);

    await user.type(usernameField, 'testuser');
    await user.type(emailField, 'test@example.com');
    await user.type(passwordField, 'short');

    const btn = screen.getByRole('button', { name: /register|sign up/i });
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for password mismatch', async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    const usernameField = await screen.findByLabelText(/username/i);
    const emailField = screen.getByLabelText(/email/i);
    const passwordField = screen.getByLabelText(/^password/i);
    const confirmField = screen.getByLabelText(/confirm password/i);

    await user.type(usernameField, 'testuser');
    await user.type(emailField, 'test@example.com');
    await user.type(passwordField, 'StrongPass1');
    await user.type(confirmField, 'DifferentPass1');

    const btn = screen.getByRole('button', { name: /register|sign up/i });
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    });
  });

  it('shows password strength indicator', async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    const passwordField = await screen.findByLabelText(/^password/i);
    await user.type(passwordField, 'StrongP@ss1');

    await waitFor(() => {
      expect(screen.getByText(/password strength/i)).toBeInTheDocument();
    });
  });

  it('shows success message on successful registration', async () => {
    mockFetch({
      '/api/accounts/settings/public': () =>
        new Response(
          JSON.stringify({ login_enabled: true, registration_enabled: true }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        ),
      '/api/accounts/auth/register': () =>
        new Response(
          JSON.stringify({
            message: 'Registration successful!',
            user: { id: 1, email: 'test@example.com', username: 'testuser' },
          }),
          { status: 201, headers: { 'Content-Type': 'application/json' } }
        ),
    });

    const user = userEvent.setup();
    renderRegisterPage();

    const usernameField = await screen.findByLabelText(/username/i);
    const emailField = screen.getByLabelText(/email/i);
    const passwordField = screen.getByLabelText(/^password/i);
    const confirmField = screen.getByLabelText(/confirm password/i);

    await user.type(usernameField, 'testuser');
    await user.type(emailField, 'test@example.com');
    await user.type(passwordField, 'StrongP@ss1');
    await user.type(confirmField, 'StrongP@ss1');

    const btn = screen.getByRole('button', { name: /register|sign up/i });
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/registration successful/i)).toBeInTheDocument();
    });
  });

  it('shows server error on failed registration', async () => {
    mockFetch({
      '/api/accounts/settings/public': () =>
        new Response(
          JSON.stringify({ login_enabled: true, registration_enabled: true }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        ),
      '/api/accounts/auth/register': () =>
        new Response(JSON.stringify({ error: 'Email already exists' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }),
    });

    const user = userEvent.setup();
    renderRegisterPage();

    const usernameField = await screen.findByLabelText(/username/i);
    const emailField = screen.getByLabelText(/email/i);
    const passwordField = screen.getByLabelText(/^password/i);
    const confirmField = screen.getByLabelText(/confirm password/i);

    await user.type(usernameField, 'testuser');
    await user.type(emailField, 'test@example.com');
    await user.type(passwordField, 'StrongP@ss1');
    await user.type(confirmField, 'StrongP@ss1');

    const btn = screen.getByRole('button', { name: /register|sign up/i });
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/email already exists/i)).toBeInTheDocument();
    });
  });

  it('disables form when registration is disabled', async () => {
    mockFetch({
      '/api/accounts/settings/public': () =>
        new Response(
          JSON.stringify({ login_enabled: true, registration_enabled: false }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        ),
    });

    renderRegisterPage();

    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /register|sign up/i });
      expect(btn).toBeDisabled();
    });
  });

  it('clears field error when user starts typing', async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    const btn = await screen.findByRole('button', {
      name: /register|sign up/i,
    });
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/username is required/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/username/i), 'a');
    await waitFor(() => {
      expect(
        screen.queryByText(/username is required/i)
      ).not.toBeInTheDocument();
    });
  });
});
