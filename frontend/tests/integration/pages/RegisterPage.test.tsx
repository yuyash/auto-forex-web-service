/**
 * Integration tests for RegisterPage.
 * Tests form rendering, validation, password strength, submission, and registration-disabled state.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../../../src/contexts/AuthContext';
import { I18nextProvider } from 'react-i18next';
import i18n from '../../../src/i18n/config';
import { ApiError } from '../../../src/api/apiClient';
import { authApi } from '../../../src/services/api';
import { useRegister } from '../../../src/hooks/useAuthMutations';
import RegisterPage from '../../../src/pages/RegisterPage';

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
  useRegister: vi.fn(),
}));

async function getEnabledSubmitButton() {
  const button = await screen.findByRole('button', {
    name: /register|sign up/i,
  });
  await waitFor(() => {
    expect(button).toBeEnabled();
  });
  return button;
}

async function renderRegisterPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const rendered = render(
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={['/register']}>
          <AuthProvider>
            <RegisterPage />
          </AuthProvider>
        </MemoryRouter>
      </I18nextProvider>
    </QueryClientProvider>
  );
  await waitFor(() => {
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });
  return rendered;
}

describe('RegisterPage', () => {
  const authApiMock = vi.mocked(authApi);
  const useRegisterMock = vi.mocked(useRegister);
  let registerMutateMock: ReturnType<typeof vi.fn>;

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
    registerMutateMock = vi.fn();
    useRegisterMock.mockReturnValue({
      mutate: registerMutateMock,
    } as never);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders all form fields', async () => {
    await renderRegisterPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    });
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
  });

  it('shows validation error for empty username', async () => {
    const user = userEvent.setup();
    await renderRegisterPage();

    const btn = await getEnabledSubmitButton();
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/username is required/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for short username', async () => {
    const user = userEvent.setup();
    await renderRegisterPage();

    const usernameField = await screen.findByLabelText(/username/i);
    await user.type(usernameField, 'ab');

    const btn = await getEnabledSubmitButton();
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/at least 3 characters/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for invalid email', async () => {
    const user = userEvent.setup();
    await renderRegisterPage();

    const usernameField = await screen.findByLabelText(/username/i);
    const emailField = screen.getByLabelText(/email/i);

    await user.type(usernameField, 'testuser');
    await user.type(emailField, 'notanemail');

    const btn = await getEnabledSubmitButton();
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for short password', async () => {
    const user = userEvent.setup();
    await renderRegisterPage();

    const usernameField = await screen.findByLabelText(/username/i);
    const emailField = screen.getByLabelText(/email/i);
    const passwordField = screen.getByLabelText(/^password/i);

    await user.type(usernameField, 'testuser');
    await user.type(emailField, 'test@example.com');
    await user.type(passwordField, 'short');

    const btn = await getEnabledSubmitButton();
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for password mismatch', async () => {
    const user = userEvent.setup();
    await renderRegisterPage();

    const usernameField = await screen.findByLabelText(/username/i);
    const emailField = screen.getByLabelText(/email/i);
    const passwordField = screen.getByLabelText(/^password/i);
    const confirmField = screen.getByLabelText(/confirm password/i);

    await user.type(usernameField, 'testuser');
    await user.type(emailField, 'test@example.com');
    await user.type(passwordField, 'StrongPass1');
    await user.type(confirmField, 'DifferentPass1');

    const btn = await getEnabledSubmitButton();
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    });
  });

  it('shows password strength indicator', async () => {
    const user = userEvent.setup();
    await renderRegisterPage();

    const passwordField = await screen.findByLabelText(/^password/i);
    await user.type(passwordField, 'StrongP@ss1');

    await waitFor(() => {
      expect(screen.getByText(/password strength/i)).toBeInTheDocument();
    });
  });

  it('shows success message on successful registration', async () => {
    registerMutateMock.mockResolvedValueOnce({
      message: 'Registration successful!',
      user: { id: 1, email: 'test@example.com', username: 'testuser' },
    });

    const user = userEvent.setup();
    await renderRegisterPage();

    const usernameField = await screen.findByLabelText(/username/i);
    const emailField = screen.getByLabelText(/email/i);
    const passwordField = screen.getByLabelText(/^password/i);
    const confirmField = screen.getByLabelText(/confirm password/i);

    await user.type(usernameField, 'testuser');
    await user.type(emailField, 'test@example.com');
    await user.type(passwordField, 'StrongP@ss1');
    await user.type(confirmField, 'StrongP@ss1');

    const btn = await getEnabledSubmitButton();
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/registration successful/i)).toBeInTheDocument();
    });
  });

  it('shows server error on failed registration', async () => {
    registerMutateMock.mockRejectedValueOnce(
      new ApiError('/api/accounts/auth/register', 400, 'Bad Request', {
        error: 'Email already exists',
      })
    );

    const user = userEvent.setup();
    await renderRegisterPage();

    const usernameField = await screen.findByLabelText(/username/i);
    const emailField = screen.getByLabelText(/email/i);
    const passwordField = screen.getByLabelText(/^password/i);
    const confirmField = screen.getByLabelText(/confirm password/i);

    await user.type(usernameField, 'testuser');
    await user.type(emailField, 'test@example.com');
    await user.type(passwordField, 'StrongP@ss1');
    await user.type(confirmField, 'StrongP@ss1');

    const btn = await getEnabledSubmitButton();
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/email already exists/i)).toBeInTheDocument();
    });
  });

  it('disables form when registration is disabled', async () => {
    authApiMock.getPublicSettings.mockResolvedValueOnce({
      login_enabled: true,
      registration_enabled: false,
    });

    await renderRegisterPage();

    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /register|sign up/i });
      expect(btn).toBeDisabled();
    });
  });

  it('clears field error when user starts typing', async () => {
    const user = userEvent.setup();
    await renderRegisterPage();

    const btn = await getEnabledSubmitButton();
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
