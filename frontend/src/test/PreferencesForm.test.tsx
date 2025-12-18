import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import PreferencesForm from '../components/settings/PreferencesForm';
import { AuthProvider } from '../contexts/AuthContext';
import ToastProvider from '../components/common/Toast';
import '../i18n/config';

// Mock fetch
globalThis.fetch = vi.fn();

const mockUser = {
  id: 1,
  email: 'test@example.com',
  username: 'testuser',
  is_staff: false,
  timezone: 'UTC',
  language: 'en',
};

const mockToken = 'mock-token-123';

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>{component}</ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
};

describe('PreferencesForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('token', mockToken);
    localStorage.setItem('user', JSON.stringify(mockUser));

    // Mock system settings fetch + user settings fetch
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url) => {
      if (url === '/api/accounts/settings/public') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        });
      }
      if (url === '/api/accounts/settings/') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            user: {
              timezone: 'UTC',
              language: 'en',
            },
            settings: {
              notification_enabled: true,
            },
          }),
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });
  });

  it('renders preferences form', async () => {
    renderWithProviders(<PreferencesForm />);

    await waitFor(() => {
      expect(screen.getByText(/User Preferences/i)).toBeInTheDocument();
    });

    expect(screen.getByLabelText(/Timezone/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Language/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Enable Notifications/i)).toBeInTheDocument();
  });

  it('loads current settings on mount', async () => {
    renderWithProviders(<PreferencesForm />);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        '/api/accounts/settings/',
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${mockToken}`,
          }),
        })
      );
    });
  });

  it('displays timezone selector with options', async () => {
    renderWithProviders(<PreferencesForm />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Timezone/i)).toBeInTheDocument();
    });

    const timezoneSelect = screen.getByLabelText(/Timezone/i);
    fireEvent.mouseDown(timezoneSelect);

    await waitFor(() => {
      const options = screen.getAllByText('UTC');
      expect(options.length).toBeGreaterThan(0);
      expect(screen.getByText('America/New_York')).toBeInTheDocument();
      expect(screen.getByText('Asia/Tokyo')).toBeInTheDocument();
    });
  });

  it('displays language selector with English and Japanese', async () => {
    renderWithProviders(<PreferencesForm />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Language/i)).toBeInTheDocument();
    });

    const languageSelect = screen.getByLabelText(/Language/i);
    fireEvent.mouseDown(languageSelect);

    await waitFor(() => {
      const englishOptions = screen.getAllByText('English');
      expect(englishOptions.length).toBeGreaterThan(0);
      expect(screen.getByText(/Japanese/i)).toBeInTheDocument();
    });
  });

  it('allows toggling notification preferences', async () => {
    renderWithProviders(<PreferencesForm />);

    await waitFor(() => {
      expect(
        screen.getByLabelText(/Enable Notifications/i)
      ).toBeInTheDocument();
    });

    const notificationSwitch = screen.getByRole('switch', {
      name: /Enable Notifications/i,
    });

    expect(notificationSwitch).toBeChecked();

    fireEvent.click(notificationSwitch);
    expect(notificationSwitch).not.toBeChecked();

    fireEvent.click(notificationSwitch);
    expect(notificationSwitch).toBeChecked();
  });

  it('submits form with updated settings', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url) => {
      if (url === '/api/accounts/settings/public') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        });
      }
      if (url === '/api/accounts/settings/') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            user: {
              ...mockUser,
              timezone: 'UTC',
              language: 'en',
            },
            settings: {
              notification_enabled: true,
            },
          }),
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithProviders(<PreferencesForm />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Timezone/i)).toBeInTheDocument();
    });

    // Change timezone
    const timezoneSelect = screen.getByLabelText(/Timezone/i);
    fireEvent.mouseDown(timezoneSelect);
    await waitFor(() => {
      fireEvent.click(screen.getByText('Asia/Tokyo'));
    });

    // Submit form
    const saveButton = screen.getByRole('button', { name: /Save/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        '/api/accounts/settings/',
        expect.objectContaining({
          method: 'PUT',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            Authorization: `Bearer ${mockToken}`,
          }),
          body: expect.stringContaining('Asia/Tokyo'),
        })
      );
    });
  });

  it('displays error message on save failure', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url, options?: RequestInit) => {
        if (url === '/api/accounts/settings/public') {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              registration_enabled: true,
              login_enabled: true,
            }),
          });
        }
        if (url === '/api/accounts/settings/') {
          const method = options?.method;
          if (method === 'PUT') {
            return Promise.resolve({
              ok: false,
              json: async () => ({
                message: 'Failed to save settings',
              }),
            });
          }
          return Promise.resolve({
            ok: true,
            json: async () => ({
              user: {
                timezone: 'UTC',
                language: 'en',
              },
              settings: {
                notification_enabled: true,
              },
            }),
          });
        }
        return Promise.reject(new Error('Unknown URL'));
      }
    );

    renderWithProviders(<PreferencesForm />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Save/i })).toBeInTheDocument();
    });

    const saveButton = screen.getByRole('button', { name: /Save/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText(/Failed to save settings/i)).toBeInTheDocument();
    });
  });

  it('displays loading state while fetching settings', () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url) => {
      if (url === '/api/accounts/settings/public') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        });
      }
      if (url === '/api/accounts/settings/') {
        return new Promise(() => {}); // Never resolves
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithProviders(<PreferencesForm />);

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('displays info alert about timezone changes', async () => {
    renderWithProviders(<PreferencesForm />);

    await waitFor(() => {
      expect(
        screen.getByText(/Changing your timezone will affect/i)
      ).toBeInTheDocument();
    });
  });
});
