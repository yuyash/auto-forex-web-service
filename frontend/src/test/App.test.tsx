import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../App';

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    // Since user is not authenticated, should redirect to login
    expect(screen.getByText(/Sign In/i)).toBeInTheDocument();
  });

  it('renders login page for unauthenticated users', () => {
    render(<App />);
    expect(
      screen.getByText(/Login functionality will be implemented/i)
    ).toBeInTheDocument();
  });
});
