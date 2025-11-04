import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import AddAccountModal from '../components/settings/AddAccountModal';
import '../i18n/config';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

const mockOnClose = vi.fn();
const mockOnSuccess = vi.fn();
const testToken = 'test-token-123';

const renderComponent = (props = {}) => {
  return render(
    <BrowserRouter>
      <AddAccountModal
        open={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        token={testToken}
        {...props}
      />
    </BrowserRouter>
  );
};

describe('AddAccountModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders modal with form fields', () => {
    renderComponent();

    expect(screen.getByText('Add Account')).toBeInTheDocument();
    expect(screen.getByLabelText(/Account ID/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/API Token/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/API Type/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Add$/i })).toBeInTheDocument();
  });

  it('does not render when open is false', () => {
    renderComponent({ open: false });

    expect(screen.queryByText('Add Account')).not.toBeInTheDocument();
  });

  it('validates required fields', async () => {
    const user = userEvent.setup();
    renderComponent();

    // Try to submit without filling fields
    const submitButton = screen.getByRole('button', { name: /^Add$/i });
    await user.click(submitButton);

    // Should show validation errors
    await waitFor(() => {
      const errors = screen.getAllByText(/This field is required/i);
      expect(errors.length).toBe(2); // Account ID and API Token
    });

    // Should not call API
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('submits form with valid data', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 1,
        account_id: '001-001-1234567-001',
        api_type: 'practice',
      }),
    });

    const user = userEvent.setup();
    renderComponent();

    // Fill form
    const accountIdInput = screen.getByLabelText(/Account ID/i);
    const apiTokenInput = screen.getByLabelText(/API Token/i);

    await user.type(accountIdInput, '001-001-1234567-001');
    await user.type(apiTokenInput, 'test-api-token-123');

    // Submit
    const submitButton = screen.getByRole('button', { name: /^Add$/i });
    await user.click(submitButton);

    // Should call API with correct data
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/accounts',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${testToken}`,
          },
          body: JSON.stringify({
            account_id: '001-001-1234567-001',
            api_token: 'test-api-token-123',
            api_type: 'practice',
          }),
        })
      );
    });

    // Should call success callback and close
    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled();
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it('allows selecting API type', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 1 }),
    });

    const user = userEvent.setup();
    renderComponent();

    // Fill required fields
    await user.type(
      screen.getByLabelText(/Account ID/i),
      '001-001-1234567-001'
    );
    await user.type(screen.getByLabelText(/API Token/i), 'test-token');

    // Change API type to live
    const apiTypeSelect = screen.getByLabelText(/API Type/i);
    await user.click(apiTypeSelect);

    const liveOption = screen.getByRole('option', { name: /Live/i });
    await user.click(liveOption);

    // Submit
    const submitButton = screen.getByRole('button', { name: /^Add$/i });
    await user.click(submitButton);

    // Should submit with live API type
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/accounts',
        expect.objectContaining({
          body: JSON.stringify({
            account_id: '001-001-1234567-001',
            api_token: 'test-token',
            api_type: 'live',
          }),
        })
      );
    });
  });

  it('toggles API token visibility', async () => {
    const user = userEvent.setup();
    renderComponent();

    const apiTokenInput = screen.getByLabelText(
      /API Token/i
    ) as HTMLInputElement;
    const toggleButton = screen.getByLabelText(/Show password/i);

    // Initially should be password type
    expect(apiTokenInput.type).toBe('password');

    // Click to show
    await user.click(toggleButton);

    await waitFor(() => {
      expect(apiTokenInput.type).toBe('text');
    });

    // Click to hide again
    const hideButton = screen.getByLabelText(/Hide password/i);
    await user.click(hideButton);

    await waitFor(() => {
      expect(apiTokenInput.type).toBe('password');
    });
  });

  it('displays error message on API failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ message: 'Invalid credentials' }),
    });

    const user = userEvent.setup();
    renderComponent();

    // Fill and submit form
    await user.type(
      screen.getByLabelText(/Account ID/i),
      '001-001-1234567-001'
    );
    await user.type(screen.getByLabelText(/API Token/i), 'invalid-token');

    const submitButton = screen.getByRole('button', { name: /^Add$/i });
    await user.click(submitButton);

    // Should display error message
    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });

    // Should not call success callback
    expect(mockOnSuccess).not.toHaveBeenCalled();
  });

  it('displays generic error message on network failure', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const user = userEvent.setup();
    renderComponent();

    // Fill and submit form
    await user.type(
      screen.getByLabelText(/Account ID/i),
      '001-001-1234567-001'
    );
    await user.type(screen.getByLabelText(/API Token/i), 'test-token');

    const submitButton = screen.getByRole('button', { name: /^Add$/i });
    await user.click(submitButton);

    // Should display error message
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('disables form during submission', async () => {
    let resolvePromise: (value: unknown) => void;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });

    mockFetch.mockImplementation(() => promise);

    const user = userEvent.setup();
    renderComponent();

    // Fill form
    await user.type(
      screen.getByLabelText(/Account ID/i),
      '001-001-1234567-001'
    );
    await user.type(screen.getByLabelText(/API Token/i), 'test-token');

    // Submit
    const submitButton = screen.getByRole('button', { name: /^Add$/i });
    await user.click(submitButton);

    // Form fields should be disabled during submission
    await waitFor(() => {
      expect(screen.getByLabelText(/Account ID/i)).toBeDisabled();
      expect(screen.getByLabelText(/API Token/i)).toBeDisabled();
      // Select uses aria-disabled instead of disabled attribute
      const apiTypeSelect = screen.getByLabelText(/API Type/i);
      expect(apiTypeSelect).toHaveAttribute('aria-disabled', 'true');
      expect(submitButton).toBeDisabled();
    });

    // Resolve the promise to complete the test
    resolvePromise!({
      ok: true,
      json: async () => ({ id: 1 }),
    });
  });

  it('closes modal when cancel button is clicked', async () => {
    const user = userEvent.setup();
    renderComponent();

    const cancelButton = screen.getByRole('button', { name: /Cancel/i });
    await user.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('resets form when modal is closed and reopened', async () => {
    const user = userEvent.setup();
    const { rerender } = renderComponent();

    // Fill form
    await user.type(
      screen.getByLabelText(/Account ID/i),
      '001-001-1234567-001'
    );
    await user.type(screen.getByLabelText(/API Token/i), 'test-token');

    // Close modal
    rerender(
      <BrowserRouter>
        <AddAccountModal
          open={false}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
          token={testToken}
        />
      </BrowserRouter>
    );

    // Reopen modal
    rerender(
      <BrowserRouter>
        <AddAccountModal
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
          token={testToken}
        />
      </BrowserRouter>
    );

    // Form should be reset - wait for the effect to run
    await waitFor(() => {
      const accountIdInput = screen.getByLabelText(
        /Account ID/i
      ) as HTMLInputElement;
      const apiTokenInput = screen.getByLabelText(
        /API Token/i
      ) as HTMLInputElement;

      expect(accountIdInput.value).toBe('');
      expect(apiTokenInput.value).toBe('');
    });
  });

  it('handles API error with error field', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ error: 'Account already exists' }),
    });

    const user = userEvent.setup();
    renderComponent();

    // Fill and submit form
    await user.type(
      screen.getByLabelText(/Account ID/i),
      '001-001-1234567-001'
    );
    await user.type(screen.getByLabelText(/API Token/i), 'test-token');

    const submitButton = screen.getByRole('button', { name: /^Add$/i });
    await user.click(submitButton);

    // Should display error message
    await waitFor(() => {
      expect(screen.getByText('Account already exists')).toBeInTheDocument();
    });
  });
});
