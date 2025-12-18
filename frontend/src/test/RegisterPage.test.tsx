import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import RegisterPage from '../pages/RegisterPage';
import { AuthProvider } from '../contexts/AuthContext';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock system settings API call that AuthProvider makes on mount
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        registration_enabled: true,
        login_enabled: true,
      }),
    });
  });

  it('renders registration form with all required fields', async () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>
    );

    // Wait for system settings to load
    await waitFor(() => {
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    });

    expect(screen.getByLabelText(/^email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /sign up/i })
    ).toBeInTheDocument();
  });

  it('validates email format', async () => {
    const user = userEvent.setup({ delay: null });

    render(
      <MemoryRouter>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>
    );

    // Wait for system settings to load
    await waitFor(() => {
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    });

    const emailInput = screen.getByLabelText(/^email/i);
    const submitButton = screen.getByRole('button', { name: /sign up/i });

    await user.type(emailInput, 'invalid-email');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/invalid email format/i)).toBeInTheDocument();
    });
  });

  it('validates required fields', async () => {
    const user = userEvent.setup({ delay: null });

    render(
      <MemoryRouter>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>
    );

    // Wait for system settings to load
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /sign up/i })
      ).toBeInTheDocument();
    });

    const submitButton = screen.getByRole('button', { name: /sign up/i });
    await waitFor(() => {
      expect(submitButton).not.toBeDisabled();
    });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/username is required/i)).toBeInTheDocument();
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
      expect(
        screen.getByText(/please confirm your password/i)
      ).toBeInTheDocument();
    });
  });

  it('validates password strength requirements', async () => {
    const user = userEvent.setup({ delay: null });

    render(
      <MemoryRouter>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>
    );

    // Wait for system settings to load
    await waitFor(() => {
      expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
    });

    const passwordInput = screen.getByLabelText(/^password/i);
    const submitButton = screen.getByRole('button', { name: /sign up/i });

    // Test short password
    await user.type(passwordInput, 'short');
    await user.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText(/password must be at least 8 characters/i)
      ).toBeInTheDocument();
    });

    // Clear and test password without uppercase
    await user.clear(passwordInput);
    await user.type(passwordInput, 'lowercase123');
    await user.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText(/password must contain at least one uppercase letter/i)
      ).toBeInTheDocument();
    });

    // Clear and test password without lowercase
    await user.clear(passwordInput);
    await user.type(passwordInput, 'UPPERCASE123');
    await user.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText(/password must contain at least one lowercase letter/i)
      ).toBeInTheDocument();
    });

    // Clear and test password without number
    await user.clear(passwordInput);
    await user.type(passwordInput, 'NoNumbers');
    await user.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText(/password must contain at least one number/i)
      ).toBeInTheDocument();
    });
  }, 15000);

  it('validates password confirmation match', async () => {
    const user = userEvent.setup({ delay: null });

    render(
      <MemoryRouter>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>
    );

    // Wait for system settings to load
    await waitFor(() => {
      expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
    });

    const passwordInput = screen.getByLabelText(/^password/i);
    const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
    const submitButton = screen.getByRole('button', { name: /sign up/i });

    await user.type(passwordInput, 'Password123');
    await user.type(confirmPasswordInput, 'DifferentPassword123');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    });
  });

  it('displays password strength indicator', async () => {
    const user = userEvent.setup({ delay: null });

    render(
      <MemoryRouter>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>
    );

    // Wait for system settings to load
    await waitFor(() => {
      expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
    });

    const passwordInput = screen.getByLabelText(/^password/i);

    // Type a weak password
    await user.type(passwordInput, 'weak');

    await waitFor(() => {
      expect(screen.getByText(/password strength:/i)).toBeInTheDocument();
      expect(screen.getByText(/weak/i)).toBeInTheDocument();
    });

    // Type a strong password
    await user.clear(passwordInput);
    await user.type(passwordInput, 'StrongPass123!');

    await waitFor(() => {
      expect(screen.getByText(/strong/i)).toBeInTheDocument();
    });
  });

  it('calls register API with correct data', async () => {
    const user = userEvent.setup({ delay: null });

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          registration_enabled: true,
          login_enabled: true,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          message: 'Registration successful',
          user: {
            id: 1,
            email: 'test@example.com',
            username: 'testuser',
          },
        }),
      });

    render(
      <MemoryRouter>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>
    );

    // Wait for system settings to load
    await waitFor(() => {
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    });

    const usernameInput = screen.getByLabelText(/username/i);
    const emailInput = screen.getByLabelText(/^email/i);
    const passwordInput = screen.getByLabelText(/^password/i);
    const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
    const submitButton = screen.getByRole('button', { name: /sign up/i });

    await user.type(usernameInput, 'testuser');
    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'Password123');
    await user.type(confirmPasswordInput, 'Password123');
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/accounts/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: 'testuser',
          email: 'test@example.com',
          password: 'Password123',
          password_confirm: 'Password123',
        }),
      });
    });
  });

  it('shows success message and redirects to login on successful registration', async () => {
    const user = userEvent.setup({ delay: null });

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          registration_enabled: true,
          login_enabled: true,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          message: 'Registration successful',
          user: {
            id: 1,
            email: 'test@example.com',
            username: 'testuser',
          },
        }),
      });

    render(
      <MemoryRouter>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>
    );

    // Wait for system settings to load
    await waitFor(() => {
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    });

    const usernameInput = screen.getByLabelText(/username/i);
    const emailInput = screen.getByLabelText(/^email/i);
    const passwordInput = screen.getByLabelText(/^password/i);
    const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
    const submitButton = screen.getByRole('button', { name: /sign up/i });

    await user.type(usernameInput, 'testuser');
    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'Password123');
    await user.type(confirmPasswordInput, 'Password123');
    await user.click(submitButton);

    await waitFor(
      () => {
        expect(
          screen.getByText(/registration successful/i)
        ).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Wait for redirect (2 seconds in component)
    await waitFor(
      () => {
        expect(mockNavigate).toHaveBeenCalledWith('/login');
      },
      { timeout: 3000 }
    );
  });

  it('displays error message on failed registration', async () => {
    const user = userEvent.setup({ delay: null });

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          registration_enabled: true,
          login_enabled: true,
        }),
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({
          error: 'Email already exists',
        }),
      });

    render(
      <MemoryRouter>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>
    );

    // Wait for system settings to load
    await waitFor(() => {
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    });

    const usernameInput = screen.getByLabelText(/username/i);
    const emailInput = screen.getByLabelText(/^email/i);
    const passwordInput = screen.getByLabelText(/^password/i);
    const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
    const submitButton = screen.getByRole('button', { name: /sign up/i });

    await user.type(usernameInput, 'testuser');
    await user.type(emailInput, 'existing@example.com');
    await user.type(passwordInput, 'Password123');
    await user.type(confirmPasswordInput, 'Password123');
    await user.click(submitButton);

    await waitFor(
      () => {
        expect(screen.getByText(/email already exists/i)).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('shows loading state during registration', async () => {
    const user = userEvent.setup({ delay: null });

    let resolvePromise: ((value: unknown) => void) | undefined;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          registration_enabled: true,
          login_enabled: true,
        }),
      })
      .mockReturnValueOnce(promise as Promise<Response>);

    render(
      <MemoryRouter>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>
    );

    // Wait for system settings to load
    await waitFor(() => {
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    });

    const usernameInput = screen.getByLabelText(/username/i);
    const emailInput = screen.getByLabelText(/^email/i);
    const passwordInput = screen.getByLabelText(/^password/i);
    const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
    const submitButton = screen.getByRole('button', { name: /sign up/i });

    await user.type(usernameInput, 'testuser');
    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'Password123');
    await user.type(confirmPasswordInput, 'Password123');
    await user.click(submitButton);

    // Check for loading spinner (CircularProgress inside button)
    await waitFor(() => {
      const progressBars = screen.getAllByRole('progressbar');
      // Should have password strength bar + loading spinner
      expect(progressBars.length).toBeGreaterThan(1);
      // Button should be disabled during loading
      expect(submitButton).toBeDisabled();
    });

    // Resolve the promise to clean up
    resolvePromise!({
      ok: true,
      json: async () => ({
        message: 'Registration successful',
        user: {
          id: 1,
          email: 'test@example.com',
          username: 'testuser',
        },
      }),
    });
  });

  it('clears field errors when user starts typing', async () => {
    const user = userEvent.setup({ delay: null });

    render(
      <MemoryRouter>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>
    );

    // Wait for system settings to load
    await waitFor(() => {
      expect(screen.getByLabelText(/^email/i)).toBeInTheDocument();
    });

    const emailInput = screen.getByLabelText(/^email/i);
    const submitButton = screen.getByRole('button', { name: /sign up/i });

    // Trigger validation error
    await waitFor(() => {
      expect(submitButton).not.toBeDisabled();
    });
    await user.click(submitButton);

    await waitFor(
      () => {
        expect(screen.getByText(/email is required/i)).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Start typing to clear error
    await user.type(emailInput, 't');

    await waitFor(
      () => {
        expect(
          screen.queryByText(/email is required/i)
        ).not.toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });
});
