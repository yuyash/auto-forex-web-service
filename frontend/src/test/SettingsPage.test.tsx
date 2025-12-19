import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
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
      if (url === '/api/market/accounts/') {
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

  it('renders all two tabs', () => {
    renderSettingsPage();
    expect(screen.getByText('Accounts')).toBeInTheDocument();
    expect(screen.getByText('Security')).toBeInTheDocument();
  });

  it('displays accounts tab content by default', async () => {
    renderSettingsPage();
    await waitFor(() => {
      expect(screen.getByText('OANDA Accounts')).toBeInTheDocument();
    });
  });

  it('switches to security tab when first clicked', async () => {
    renderSettingsPage();
    const securityTab = screen.getByRole('tab', {
      name: /security/i,
    });
    fireEvent.click(securityTab);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /security settings/i })
      ).toBeInTheDocument();
    });
  });

  it('switches to security tab when clicked', async () => {
    renderSettingsPage();
    const securityTab = screen.getByRole('tab', {
      name: /security/i,
    });
    fireEvent.click(securityTab);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /security settings/i })
      ).toBeInTheDocument();
    });

    // Check that the security placeholder text is rendered
    expect(
      screen.getByText(
        /security settings \(password change, 2fa\) will be implemented in a future task/i
      )
    ).toBeInTheDocument();
  });

  it('displays security tab content when clicked', () => {
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

    // Switch to Security
    const securityTab = screen.getByRole('tab', {
      name: /security/i,
    });
    fireEvent.click(securityTab);

    // Wait for security content to be visible
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /security settings/i })
      ).toBeVisible();
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

    const securityTab = screen.getByRole('tab', {
      name: /security/i,
    });
    expect(securityTab).toHaveAttribute('id', 'settings-tab-1');
    expect(securityTab).toHaveAttribute('aria-controls', 'settings-tabpanel-1');

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

    // Switch back to Accounts tab
    const accountsTab = screen.getByRole('tab', {
      name: /accounts/i,
    });
    fireEvent.click(accountsTab);

    await waitFor(() => {
      expect(screen.getByText('OANDA Accounts')).toBeVisible();
    });

    // Security panel should have hidden attribute
    const securityPanel = document.getElementById('settings-tabpanel-1');
    expect(securityPanel).toHaveAttribute('hidden');
  });
});
