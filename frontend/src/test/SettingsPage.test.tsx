import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import SettingsPage from '../pages/SettingsPage';
import { AuthProvider } from '../contexts/AuthContext';
import { ToastContext } from '../components/common/ToastContext';
import type { ToastContextType } from '../components/common/ToastContext';
import '../i18n/config';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

// Mock toast context
const mockToastContext: ToastContextType = {
  showToast: vi.fn(),
  showSuccess: vi.fn(),
  showError: vi.fn(),
  showWarning: vi.fn(),
  showInfo: vi.fn(),
};

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('token', 'test-token');
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 1, email: 'test@example.com' })
    );

    // Mock all API calls that components might make
    mockFetch.mockImplementation((url) => {
      if (url === '/api/system/settings/public') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        });
      }
      if (url === '/api/accounts') {
        return Promise.resolve({
          ok: true,
          json: async () => [],
        });
      }
      if (url === '/api/settings') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            default_lot_size: 1.0,
            default_scaling_mode: 'additive',
            default_retracement_pips: 30,
            default_take_profit_pips: 25,
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      });
    });
  });

  const renderSettingsPage = () => {
    return render(
      <BrowserRouter>
        <AuthProvider>
          <ToastContext.Provider value={mockToastContext}>
            <SettingsPage />
          </ToastContext.Provider>
        </AuthProvider>
      </BrowserRouter>
    );
  };

  it('renders settings page with title', () => {
    renderSettingsPage();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('renders all four tabs', () => {
    renderSettingsPage();
    expect(screen.getByText('Accounts')).toBeInTheDocument();
    expect(screen.getByText('Preferences')).toBeInTheDocument();
    expect(screen.getByText('Strategy Defaults')).toBeInTheDocument();
    expect(screen.getByText('Security')).toBeInTheDocument();
  });

  it('displays accounts tab content by default', async () => {
    renderSettingsPage();
    await waitFor(() => {
      expect(screen.getByText('OANDA Accounts')).toBeInTheDocument();
    });
  });

  it('switches to preferences tab when clicked', async () => {
    renderSettingsPage();
    const preferencesTab = screen.getByText('Preferences');
    fireEvent.click(preferencesTab);

    await waitFor(() => {
      expect(screen.getByText('User Preferences')).toBeInTheDocument();
    });

    // Check that the preferences form is rendered with timezone selector
    expect(screen.getByLabelText(/Timezone/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Language/i)).toBeInTheDocument();
  });

  it('switches to strategy defaults tab when clicked', async () => {
    renderSettingsPage();
    const strategyDefaultsTab = screen.getByRole('tab', {
      name: /strategy defaults/i,
    });
    fireEvent.click(strategyDefaultsTab);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /strategy defaults/i })
      ).toBeInTheDocument();
    });

    // Check that the strategy defaults form is rendered
    expect(screen.getByLabelText(/Default Lot Size/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Default Scaling Mode/i)).toBeInTheDocument();
  });

  it('switches to security tab when clicked', () => {
    renderSettingsPage();
    const securityTab = screen.getByText('Security');
    fireEvent.click(securityTab);
    expect(screen.getByText('Security Settings')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Security settings (password change, 2FA) will be implemented in a future task'
      )
    ).toBeInTheDocument();
  });

  it('hides other tab content when switching tabs', async () => {
    renderSettingsPage();

    // Wait for initial content to load
    await waitFor(() => {
      expect(screen.getByText('OANDA Accounts')).toBeInTheDocument();
    });

    // Switch to Preferences
    const preferencesTab = screen.getByText('Preferences');
    fireEvent.click(preferencesTab);

    // Wait for preferences content to be visible
    await waitFor(() => {
      expect(screen.getByText('User Preferences')).toBeVisible();
    });

    // Accounts panel should have hidden attribute
    const accountsPanel = document.getElementById('settings-tabpanel-0');
    expect(accountsPanel).toHaveAttribute('hidden');
  });

  it('has proper ARIA attributes for accessibility', () => {
    renderSettingsPage();

    // Check tabs have proper ARIA attributes
    const accountsTab = screen.getByRole('tab', { name: /accounts/i });
    expect(accountsTab).toHaveAttribute('id', 'settings-tab-0');
    expect(accountsTab).toHaveAttribute('aria-controls', 'settings-tabpanel-0');

    const preferencesTab = screen.getByRole('tab', { name: /preferences/i });
    expect(preferencesTab).toHaveAttribute('id', 'settings-tab-1');
    expect(preferencesTab).toHaveAttribute(
      'aria-controls',
      'settings-tabpanel-1'
    );

    // Check tabpanels have proper ARIA attributes
    const accountsPanel = screen.getByRole('tabpanel', { hidden: false });
    expect(accountsPanel).toHaveAttribute('id', 'settings-tabpanel-0');
    expect(accountsPanel).toHaveAttribute('aria-labelledby', 'settings-tab-0');
  });

  it('maintains tab selection state', async () => {
    renderSettingsPage();

    // Switch to Security tab
    const securityTab = screen.getByText('Security');
    fireEvent.click(securityTab);

    await waitFor(() => {
      expect(screen.getByText('Security Settings')).toBeVisible();
    });

    // Switch to Preferences tab
    const preferencesTab = screen.getByText('Preferences');
    fireEvent.click(preferencesTab);

    await waitFor(() => {
      expect(screen.getByText('User Preferences')).toBeVisible();
    });

    // Security panel should have hidden attribute
    const securityPanel = document.getElementById('settings-tabpanel-3');
    expect(securityPanel).toHaveAttribute('hidden');
  });
});
