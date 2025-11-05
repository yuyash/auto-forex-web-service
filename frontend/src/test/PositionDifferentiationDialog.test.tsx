import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import PositionDifferentiationDialog from '../components/settings/PositionDifferentiationDialog';
import { AuthProvider } from '../contexts/AuthContext';
import { ToastContext } from '../components/common/ToastContext';
import type { ToastContextType } from '../components/common/ToastContext';
import type { Account } from '../types/strategy';
import '../i18n/config';

// Mock fetch
globalThis.fetch = vi.fn();

// Mock toast context
const mockShowSuccess = vi.fn();
const mockShowError = vi.fn();
const mockToastContext: ToastContextType = {
  showToast: vi.fn(),
  showSuccess: mockShowSuccess,
  showError: mockShowError,
  showWarning: vi.fn(),
  showInfo: vi.fn(),
};

const mockAccount: Account = {
  id: 1,
  account_id: '001-001-1234567-001',
  api_type: 'practice',
  currency: 'USD',
  balance: 10000,
  margin_used: 1000,
  margin_available: 9000,
  is_active: true,
  jurisdiction: 'US',
  enable_position_differentiation: false,
  position_diff_increment: 1,
  position_diff_pattern: 'increment',
};

const mockOnClose = vi.fn();
const mockOnSave = vi.fn();

const renderComponent = (account: Account = mockAccount) => {
  return render(
    <BrowserRouter>
      <AuthProvider>
        <ToastContext.Provider value={mockToastContext}>
          <PositionDifferentiationDialog
            open={true}
            account={account}
            onClose={mockOnClose}
            onSave={mockOnSave}
          />
        </ToastContext.Provider>
      </AuthProvider>
    </BrowserRouter>
  );
};

describe('PositionDifferentiationDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('token', 'test-token');
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 1, email: 'test@example.com' })
    );
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({
        enable_position_differentiation: false,
        position_diff_increment: 1,
        position_diff_pattern: 'increment',
      }),
    });
  });

  it('renders dialog with title', async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByText(/Position Differentiation/i)).toBeInTheDocument();
    });
  });

  it('fetches current settings on open', async () => {
    renderComponent();
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        '/api/accounts/1/position-diff/',
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: expect.stringContaining('Bearer'),
          }),
        })
      );
    });
  });

  it('displays toggle switch for enabling position differentiation', async () => {
    renderComponent();
    await waitFor(() => {
      const toggle = screen.getByRole('switch', {
        name: /Enable Position Differentiation/i,
      });
      expect(toggle).toBeInTheDocument();
    });
  });

  it('displays explanation text', async () => {
    renderComponent();
    await waitFor(() => {
      expect(
        screen.getByText(
          /Makes each position unique to allow selective closing/i
        )
      ).toBeInTheDocument();
    });
  });

  it('displays US warning for US accounts', async () => {
    renderComponent();
    await waitFor(() => {
      expect(
        screen.getByText(/Recommended for FIFO compliance flexibility/i)
      ).toBeInTheDocument();
    });
  });

  it('does not display US warning for non-US accounts', async () => {
    const nonUSAccount = { ...mockAccount, jurisdiction: 'JP' };
    renderComponent(nonUSAccount);
    await waitFor(() => {
      expect(
        screen.queryByText(/Recommended for FIFO compliance flexibility/i)
      ).not.toBeInTheDocument();
    });
  });

  it('shows increment amount and pattern fields when enabled', async () => {
    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      const toggle = screen.getByRole('switch', {
        name: /Enable Position Differentiation/i,
      });
      expect(toggle).toBeInTheDocument();
    });

    const toggle = screen.getByRole('switch', {
      name: /Enable Position Differentiation/i,
    });
    await user.click(toggle);

    await waitFor(() => {
      expect(screen.getByLabelText(/Increment Amount/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Pattern/i)).toBeInTheDocument();
    });
  });

  it('validates increment amount range (1-100)', async () => {
    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      const toggle = screen.getByRole('switch', {
        name: /Enable Position Differentiation/i,
      });
      expect(toggle).toBeInTheDocument();
    });

    const toggle = screen.getByRole('switch', {
      name: /Enable Position Differentiation/i,
    });
    await user.click(toggle);

    await waitFor(() => {
      expect(screen.getByLabelText(/Increment Amount/i)).toBeInTheDocument();
    });

    const incrementInput = screen.getByLabelText(/Increment Amount/i);
    expect(incrementInput).toHaveAttribute('min', '1');
    expect(incrementInput).toHaveAttribute('max', '100');
  });

  it('displays pattern options', async () => {
    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      const toggle = screen.getByRole('switch', {
        name: /Enable Position Differentiation/i,
      });
      expect(toggle).toBeInTheDocument();
    });

    const toggle = screen.getByRole('switch', {
      name: /Enable Position Differentiation/i,
    });
    await user.click(toggle);

    await waitFor(() => {
      expect(screen.getByLabelText(/Pattern/i)).toBeInTheDocument();
    });

    const patternSelect = screen.getByLabelText(/Pattern/i);
    await user.click(patternSelect);

    await waitFor(() => {
      const options = screen.getAllByText('Increment');
      expect(options.length).toBeGreaterThan(0);
      expect(screen.getByText('Decrement')).toBeInTheDocument();
      expect(screen.getByText('Alternating')).toBeInTheDocument();
    });
  });

  it('displays current pattern preview', async () => {
    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      const toggle = screen.getByRole('switch', {
        name: /Enable Position Differentiation/i,
      });
      expect(toggle).toBeInTheDocument();
    });

    const toggle = screen.getByRole('switch', {
      name: /Enable Position Differentiation/i,
    });
    await user.click(toggle);

    await waitFor(() => {
      expect(screen.getByText(/Current Pattern/i)).toBeInTheDocument();
      expect(screen.getByText(/5000, 5001, 5002, 5003/i)).toBeInTheDocument();
    });
  });

  it('displays next order size preview', async () => {
    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      const toggle = screen.getByRole('switch', {
        name: /Enable Position Differentiation/i,
      });
      expect(toggle).toBeInTheDocument();
    });

    const toggle = screen.getByRole('switch', {
      name: /Enable Position Differentiation/i,
    });
    await user.click(toggle);

    await waitFor(() => {
      expect(screen.getByText(/Next Order Size/i)).toBeInTheDocument();
      const elements = screen.getAllByText(/5001/);
      expect(elements.length).toBeGreaterThan(0);
    });
  });

  it('saves settings when save button is clicked', async () => {
    const user = userEvent.setup();
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        enable_position_differentiation: false,
        position_diff_increment: 1,
        position_diff_pattern: 'increment',
      }),
    });
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    renderComponent();

    await waitFor(() => {
      const toggle = screen.getByRole('switch', {
        name: /Enable Position Differentiation/i,
      });
      expect(toggle).toBeInTheDocument();
    });

    const toggle = screen.getByRole('switch', {
      name: /Enable Position Differentiation/i,
    });
    await user.click(toggle);

    const saveButton = screen.getByRole('button', { name: /Save/i });
    await user.click(saveButton);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        '/api/accounts/1/position-diff/',
        expect.objectContaining({
          method: 'PUT',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            Authorization: expect.stringContaining('Bearer'),
          }),
          body: expect.stringContaining('enable_position_differentiation'),
        })
      );
    });
  });

  it('calls onSave and onClose after successful save', async () => {
    const user = userEvent.setup();
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        enable_position_differentiation: false,
        position_diff_increment: 1,
        position_diff_pattern: 'increment',
      }),
    });
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    renderComponent();

    await waitFor(() => {
      const toggle = screen.getByRole('switch', {
        name: /Enable Position Differentiation/i,
      });
      expect(toggle).toBeInTheDocument();
    });

    const saveButton = screen.getByRole('button', { name: /Save/i });
    await user.click(saveButton);

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalled();
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it('calls onClose when cancel button is clicked', async () => {
    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /Cancel/i })
      ).toBeInTheDocument();
    });

    const cancelButton = screen.getByRole('button', { name: /Cancel/i });
    await user.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('handles save error gracefully', async () => {
    const user = userEvent.setup();

    // Mock successful fetch for initial settings
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        enable_position_differentiation: false,
        position_diff_increment: 1,
        position_diff_pattern: 'increment',
      }),
    });

    // Mock failed save
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ message: 'Save failed' }),
    });

    renderComponent();

    await waitFor(() => {
      const toggle = screen.getByRole('switch', {
        name: /Enable Position Differentiation/i,
      });
      expect(toggle).toBeInTheDocument();
    });

    const saveButton = screen.getByRole('button', { name: /Save/i });
    await user.click(saveButton);

    // Wait for save attempt to complete
    await new Promise((resolve) => setTimeout(resolve, 200));

    // Dialog should still be visible after failed save
    expect(screen.getByText('Position Differentiation')).toBeInTheDocument();
  });
});
