import { describe, it, expect, vi, Mock } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';
import ResponsiveNavigation from '../components/layout/ResponsiveNavigation';
import { ThemeProvider, createTheme } from '@mui/material/styles';

// Mock useMediaQuery to test both mobile and desktop views
vi.mock('@mui/material', async () => {
  const actual = await vi.importActual('@mui/material');
  return {
    ...actual,
    useMediaQuery: vi.fn(),
  };
});

describe('ResponsiveNavigation', () => {
  const theme = createTheme();

  it('renders desktop sidebar navigation on large screens', async () => {
    const { useMediaQuery } = await import('@mui/material');
    (useMediaQuery as Mock).mockReturnValue(false); // Desktop view

    render(
      <BrowserRouter>
        <ThemeProvider theme={theme}>
          <AuthProvider>
            <ResponsiveNavigation />
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    );

    // Check that navigation items are present
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Orders')).toBeInTheDocument();
    expect(screen.getByText('Positions')).toBeInTheDocument();
    expect(screen.getByText('Strategy')).toBeInTheDocument();
    expect(screen.getByText('Backtest')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('renders mobile bottom navigation on small screens', async () => {
    const { useMediaQuery } = await import('@mui/material');
    (useMediaQuery as Mock).mockReturnValue(true); // Mobile view

    render(
      <BrowserRouter>
        <ThemeProvider theme={theme}>
          <AuthProvider>
            <ResponsiveNavigation />
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    );

    // Check that navigation items are present
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Orders')).toBeInTheDocument();
    expect(screen.getByText('Positions')).toBeInTheDocument();
    expect(screen.getByText('Strategy')).toBeInTheDocument();
    expect(screen.getByText('Backtest')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('does not show admin link for non-admin users', async () => {
    const { useMediaQuery } = await import('@mui/material');
    (useMediaQuery as Mock).mockReturnValue(false); // Desktop view

    render(
      <BrowserRouter>
        <ThemeProvider theme={theme}>
          <AuthProvider>
            <ResponsiveNavigation />
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    );

    // Admin link should not be present for non-admin users
    expect(screen.queryByText('Admin')).not.toBeInTheDocument();
  });
});
