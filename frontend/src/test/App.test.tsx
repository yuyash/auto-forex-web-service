import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import App from '../App';

describe('App', () => {
  it('renders without crashing', async () => {
    render(<App />);
    // Since user is not authenticated, should redirect to login
    // Wait for i18n to load translations
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /sign in/i })
      ).toBeInTheDocument();
    });
  });

  it('renders login page for unauthenticated users', async () => {
    render(<App />);
    // Wait for i18n to load translations
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /sign in/i })
      ).toBeInTheDocument();
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    });
  });
});
