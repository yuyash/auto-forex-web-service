/**
 * Integration test for LoginPage.
 * Tests form validation, submission, error handling, and navigation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiError } from '../../../src/api/apiClient';
import { authApi } from '../../../src/services/api';
import { useLogin } from '../../../src/hooks/useAuthMutations';
import { createAuthPageWrapper } from '../../utils/authPageTestUtils';
import { changeInputByLabel } from '../../utils/formTestUtils';

// Lazy-loaded page — import the default export
import LoginPage from '../../../src/pages/LoginPage';

vi.mock('../../../src/api', () => ({
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
}));

vi.mock('../../../src/services/api', () => ({
  authApi: {
    getPublicSettings: vi.fn(),
    refresh: vi.fn(),
    logout: vi.fn(),
  },
}));

vi.mock('../../../src/hooks/useAuthMutations', () => ({
  useLogin: vi.fn(),
}));

vi.mock('../../../src/utils/persistentState', () => ({
  readRawStoredValue: vi.fn(() => null),
  readStoredValue: vi.fn((_key, _schema, fallback) => fallback),
  removeStoredValue: vi.fn(),
  writeStoredValue: vi.fn(),
}));

async function getEnabledSubmitButton() {
  const button = await screen.findByRole('button', {
    name: /sign in|login|log in/i,
  });
  await waitFor(() => {
    expect(button).toBeEnabled();
  });
  return button;
}

async function renderLoginPage() {
  const rendered = render(<LoginPage />, {
    wrapper: createAuthPageWrapper('/login').wrapper,
  });
  await waitFor(() => {
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });
  return rendered;
}

describe('LoginPage', () => {
  const authApiMock = vi.mocked(authApi);
  const useLoginMock = vi.mocked(useLogin);
  let loginMutateMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    localStorage.clear();
    authApiMock.getPublicSettings.mockResolvedValue({
      login_enabled: true,
      registration_enabled: true,
    });
    authApiMock.refresh.mockRejectedValue(
      new ApiError('/api/accounts/auth/refresh', 401, 'Unauthorized', null)
    );
    authApiMock.logout.mockResolvedValue({
      message: 'Logged out successfully.',
      sessions_terminated: 0,
    });
    loginMutateMock = vi.fn();
    useLoginMock.mockReturnValue({
      mutate: loginMutateMock,
    } as never);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders email and password fields', async () => {
    await renderLoginPage();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it('renders submit button', async () => {
    await renderLoginPage();
    // Button text comes from i18n — may be "Sign In" or "Login"
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /sign in|login|log in/i })
      ).toBeInTheDocument();
    });
  });

  it('shows validation error for empty email', async () => {
    const user = userEvent.setup();
    await renderLoginPage();

    const btn = await getEnabledSubmitButton();
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for invalid email format', async () => {
    const user = userEvent.setup();
    await renderLoginPage();

    await screen.findByLabelText(/email/i);
    const btn = await getEnabledSubmitButton();

    changeInputByLabel(/email/i, 'notanemail');
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for empty password', async () => {
    const user = userEvent.setup();
    await renderLoginPage();

    await screen.findByLabelText(/email/i);
    const btn = await getEnabledSubmitButton();

    changeInputByLabel(/email/i, 'user@example.com');
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });
  });

  it('shows error alert on failed login', async () => {
    const user = userEvent.setup();
    loginMutateMock.mockRejectedValueOnce(
      new ApiError('/api/accounts/auth/login', 401, 'Unauthorized', {
        error: 'Invalid credentials',
      })
    );

    await renderLoginPage();

    await screen.findByLabelText(/email/i);
    await screen.findByLabelText(/password/i);
    const btn = await getEnabledSubmitButton();

    changeInputByLabel(/email/i, 'user@example.com');
    changeInputByLabel(/password/i, 'wrongpassword');
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('clears field error when user starts typing', async () => {
    const user = userEvent.setup();
    await renderLoginPage();

    const btn = await getEnabledSubmitButton();
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
