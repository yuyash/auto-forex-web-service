import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SystemSettingsPanel from '../components/admin/SystemSettingsPanel';
import type { SystemSettings } from '../types/admin';

// Mock the AuthContext
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    token: 'mock-token',
    user: { id: 1, username: 'admin', is_staff: true },
    isAuthenticated: true,
  }),
}));

const mockSettings: SystemSettings = {
  registration_enabled: true,
  login_enabled: true,
  email_whitelist_enabled: false,
  last_updated: '2025-01-15T10:00:00Z',
  updated_by: 'admin',
};

describe('SystemSettingsPanel', () => {
  beforeEach(() => {
    // Reset fetch mock before each test
    global.fetch = vi.fn();
  });

  it('renders system settings panel', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSettings,
    });

    render(<SystemSettingsPanel />);

    await waitFor(() => {
      expect(screen.getByText('System Settings')).toBeInTheDocument();
    });
  });

  it('displays loading state initially', () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );

    render(<SystemSettingsPanel />);

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('fetches and displays current settings', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSettings,
    });

    render(<SystemSettingsPanel />);

    await waitFor(() => {
      expect(screen.getByText('System Settings')).toBeInTheDocument();
    });

    // Check that switches are rendered with correct states
    const switches = screen.getAllByRole('switch');
    expect(switches).toHaveLength(3);
    expect(switches[0]).toBeChecked(); // registration_enabled
    expect(switches[1]).toBeChecked(); // login_enabled
    expect(switches[2]).not.toBeChecked(); // email_whitelist_enabled
  });

  it('displays last updated timestamp and user', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSettings,
    });

    render(<SystemSettingsPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
      expect(screen.getByText(/Updated by: admin/)).toBeInTheDocument();
    });
  });

  it('toggles registration enabled switch', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSettings,
    });

    render(<SystemSettingsPanel />);

    await waitFor(() => {
      expect(screen.getByText('System Settings')).toBeInTheDocument();
    });

    const switches = screen.getAllByRole('switch');
    const registrationSwitch = switches[0];

    fireEvent.click(registrationSwitch);

    expect(registrationSwitch).not.toBeChecked();
  });

  it('shows warning dialog when disabling login', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSettings,
    });

    render(<SystemSettingsPanel />);

    await waitFor(() => {
      expect(screen.getByText('System Settings')).toBeInTheDocument();
    });

    const switches = screen.getAllByRole('switch');
    const loginSwitch = switches[1];

    fireEvent.click(loginSwitch);

    await waitFor(() => {
      expect(screen.getByText('Warning: Disable Login')).toBeInTheDocument();
    });
  });

  it('confirms login disable when user accepts warning', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSettings,
    });

    render(<SystemSettingsPanel />);

    await waitFor(() => {
      expect(screen.getByText('System Settings')).toBeInTheDocument();
    });

    const switches = screen.getAllByRole('switch');
    const loginSwitch = switches[1];

    fireEvent.click(loginSwitch);

    await waitFor(() => {
      expect(screen.getByText('Warning: Disable Login')).toBeInTheDocument();
    });

    const confirmButton = screen.getByRole('button', {
      name: /disable login/i,
    });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(loginSwitch).not.toBeChecked();
    });
  });

  it('cancels login disable when user cancels warning', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSettings,
    });

    render(<SystemSettingsPanel />);

    await waitFor(() => {
      expect(screen.getByText('System Settings')).toBeInTheDocument();
    });

    const switches = screen.getAllByRole('switch');
    const loginSwitch = switches[1];

    fireEvent.click(loginSwitch);

    await waitFor(() => {
      expect(screen.getByText('Warning: Disable Login')).toBeInTheDocument();
    });

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(
        screen.queryByText('Warning: Disable Login')
      ).not.toBeInTheDocument();
    });

    expect(loginSwitch).toBeChecked();
  });

  it('saves settings when save button is clicked', async () => {
    const updatedSettings = {
      ...mockSettings,
      registration_enabled: false,
      last_updated: '2025-01-15T11:00:00Z',
    };

    (global.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSettings,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => updatedSettings,
      });

    render(<SystemSettingsPanel />);

    await waitFor(() => {
      expect(screen.getByText('System Settings')).toBeInTheDocument();
    });

    const switches = screen.getAllByRole('switch');
    const registrationSwitch = switches[0];

    fireEvent.click(registrationSwitch);

    const saveButton = screen.getByRole('button', { name: /save settings/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/admin/system/settings',
        expect.objectContaining({
          method: 'PUT',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });
  });

  it('displays success message after successful save', async () => {
    (global.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSettings,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSettings,
      });

    render(<SystemSettingsPanel />);

    await waitFor(() => {
      expect(screen.getByText('System Settings')).toBeInTheDocument();
    });

    const saveButton = screen.getByRole('button', { name: /save settings/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(
        screen.getByText('System settings updated successfully')
      ).toBeInTheDocument();
    });
  });

  it('displays error message when save fails', async () => {
    (global.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSettings,
      })
      .mockResolvedValueOnce({
        ok: false,
      });

    render(<SystemSettingsPanel />);

    await waitFor(() => {
      expect(screen.getByText('System Settings')).toBeInTheDocument();
    });

    const saveButton = screen.getByRole('button', { name: /save settings/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(
        screen.getByText(/Failed to update system settings/)
      ).toBeInTheDocument();
    });
  });

  it('displays error when fetch fails', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
    });

    render(<SystemSettingsPanel />);

    await waitFor(() => {
      expect(
        screen.getByText(/Failed to fetch system settings/)
      ).toBeInTheDocument();
    });
  });

  it('disables switches while saving', async () => {
    (global.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSettings,
      })
      .mockImplementation(() => new Promise(() => {}));

    render(<SystemSettingsPanel />);

    await waitFor(() => {
      expect(screen.getByText('System Settings')).toBeInTheDocument();
    });

    const saveButton = screen.getByRole('button', { name: /save settings/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      const switches = screen.getAllByRole('switch');
      switches.forEach((switchElement) => {
        expect(switchElement).toBeDisabled();
      });
    });
  });

  it('toggles email whitelist enabled switch', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSettings,
    });

    render(<SystemSettingsPanel />);

    await waitFor(() => {
      expect(screen.getByText('System Settings')).toBeInTheDocument();
    });

    const switches = screen.getAllByRole('switch');
    const emailWhitelistSwitch = switches[2];

    expect(emailWhitelistSwitch).not.toBeChecked();

    fireEvent.click(emailWhitelistSwitch);

    expect(emailWhitelistSwitch).toBeChecked();
  });
});
