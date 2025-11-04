import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import EmailTestPanel from '../components/admin/EmailTestPanel';

// Mock the AuthContext
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    token: 'mock-token',
    user: { id: 1, username: 'admin', is_staff: true },
    isAuthenticated: true,
  }),
}));

describe('EmailTestPanel', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it('renders email test panel', () => {
    render(<EmailTestPanel />);

    expect(screen.getByText('Email Configuration Test')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Send a test email to verify your email configuration is working correctly'
      )
    ).toBeInTheDocument();
  });

  it('displays email input field', () => {
    render(<EmailTestPanel />);

    const emailInput = screen.getByLabelText('Test Email Address');
    expect(emailInput).toBeInTheDocument();
    expect(emailInput).toHaveAttribute('type', 'email');
  });

  it('displays send button', () => {
    render(<EmailTestPanel />);

    const sendButton = screen.getByRole('button', {
      name: /send test email/i,
    });
    expect(sendButton).toBeInTheDocument();
    expect(sendButton).toBeDisabled(); // Disabled when email is empty
  });

  it('enables send button when email is entered', () => {
    render(<EmailTestPanel />);

    const emailInput = screen.getByLabelText('Test Email Address');
    const sendButton = screen.getByRole('button', {
      name: /send test email/i,
    });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });

    expect(sendButton).not.toBeDisabled();
  });

  it('sends test email when button is clicked', async () => {
    const mockResponse = {
      success: true,
      message: 'Test email sent successfully to test@example.com',
      configuration: {
        backend: 'SMTP',
        host: 'smtp.gmail.com',
        port: 587,
        use_tls: true,
        from_email: 'noreply@example.com',
      },
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(<EmailTestPanel />);

    const emailInput = screen.getByLabelText('Test Email Address');
    const sendButton = screen.getByRole('button', {
      name: /send test email/i,
    });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/admin/test-email',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            Authorization: 'Bearer mock-token',
          }),
          body: JSON.stringify({ test_email: 'test@example.com' }),
        })
      );
    });
  });

  it('displays success message after successful email send', async () => {
    const mockResponse = {
      success: true,
      message: 'Test email sent successfully to test@example.com',
      configuration: {
        backend: 'SMTP',
        host: 'smtp.gmail.com',
        port: 587,
        use_tls: true,
        from_email: 'noreply@example.com',
      },
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(<EmailTestPanel />);

    const emailInput = screen.getByLabelText('Test Email Address');
    const sendButton = screen.getByRole('button', {
      name: /send test email/i,
    });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(
        screen.getByText('Test email sent successfully to test@example.com')
      ).toBeInTheDocument();
    });
  });

  it('displays email configuration after test', async () => {
    const mockResponse = {
      success: true,
      message: 'Test email sent successfully',
      configuration: {
        backend: 'SMTP',
        host: 'smtp.gmail.com',
        port: 587,
        use_tls: true,
        from_email: 'noreply@example.com',
      },
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(<EmailTestPanel />);

    const emailInput = screen.getByLabelText('Test Email Address');
    const sendButton = screen.getByRole('button', {
      name: /send test email/i,
    });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(
        screen.getByText('Current Email Configuration:')
      ).toBeInTheDocument();
      expect(screen.getByText('SMTP')).toBeInTheDocument();
      expect(screen.getByText('smtp.gmail.com')).toBeInTheDocument();
      expect(screen.getByText('587')).toBeInTheDocument();
      expect(screen.getByText('noreply@example.com')).toBeInTheDocument();
    });
  });

  it('displays error message when email send fails', async () => {
    const mockResponse = {
      success: false,
      error: 'SMTP authentication failed',
      configuration: {
        backend: 'SMTP',
        host: 'smtp.gmail.com',
        port: 587,
        use_tls: true,
        from_email: 'noreply@example.com',
      },
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      json: async () => mockResponse,
    });

    render(<EmailTestPanel />);

    const emailInput = screen.getByLabelText('Test Email Address');
    const sendButton = screen.getByRole('button', {
      name: /send test email/i,
    });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      const errorMessages = screen.getAllByText('SMTP authentication failed');
      expect(errorMessages.length).toBeGreaterThan(0);
    });
  });

  it('displays configuration help when email fails', async () => {
    const mockResponse = {
      success: false,
      error: 'Failed to send test email',
      configuration: {
        backend: 'SMTP',
        host: 'smtp.gmail.com',
        port: 587,
        use_tls: true,
        from_email: 'noreply@example.com',
      },
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      json: async () => mockResponse,
    });

    render(<EmailTestPanel />);

    const emailInput = screen.getByLabelText('Test Email Address');
    const sendButton = screen.getByRole('button', {
      name: /send test email/i,
    });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(
        screen.getByText(/Please check your email configuration/i)
      ).toBeInTheDocument();
      expect(screen.getByText(/EMAIL_HOST is correct/i)).toBeInTheDocument();
    });
  });

  it('disables input and button while sending', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );

    render(<EmailTestPanel />);

    const emailInput = screen.getByLabelText('Test Email Address');
    const sendButton = screen.getByRole('button', {
      name: /send test email/i,
    });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(emailInput).toBeDisabled();
      expect(sendButton).toBeDisabled();
      expect(
        screen.getByRole('button', { name: /sending test email/i })
      ).toBeInTheDocument();
    });
  });

  it('handles network errors gracefully', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('Network error')
    );

    render(<EmailTestPanel />);

    const emailInput = screen.getByLabelText('Test Email Address');
    const sendButton = screen.getByRole('button', {
      name: /send test email/i,
    });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('allows sending email by pressing Enter key', async () => {
    const mockResponse = {
      success: true,
      message: 'Test email sent successfully',
      configuration: {
        backend: 'SMTP',
        host: 'smtp.gmail.com',
        port: 587,
        use_tls: true,
        from_email: 'noreply@example.com',
      },
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(<EmailTestPanel />);

    const emailInput = screen.getByLabelText('Test Email Address');

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.keyPress(emailInput, {
      key: 'Enter',
      code: 'Enter',
      charCode: 13,
    });

    await waitFor(() => {
      expect(
        screen.getByText('Test email sent successfully')
      ).toBeInTheDocument();
    });
  });
});
