import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import App from '../App';

describe('App', () => {
  it('renders without crashing', async () => {
    render(<App />);
    // Since user is not authenticated, should redirect to login
    // Wait for i18n to load translations
    await waitFor(() => {
      expect(screen.getByText('Sign In')).toBeInTheDocument();
    });
  });

  it('renders login page for unauthenticated users', () => {
    render(<App />);
    expect(
      screen.getByText(/Login functionality will be implemented/i)
    ).toBeInTheDocument();
  });
});
