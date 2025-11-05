import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';
import AppLayout from '../components/layout/AppLayout';

describe('AppLayout', () => {
  it('renders header, footer, and content', async () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<div>Test Content</div>} />
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    );

    // Wait for i18n to load translations
    await waitFor(() => {
      // Check header
      expect(screen.getByText('Auto Forex Trader')).toBeInTheDocument();
    });

    // Check navigation links (they appear in both header and sidebar on desktop)
    expect(screen.getAllByText('Dashboard').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Orders').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Positions').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Strategy').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Backtest').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Settings').length).toBeGreaterThan(0);

    // Check content
    expect(screen.getByText('Test Content')).toBeInTheDocument();

    // Check footer
    const currentYear = new Date().getFullYear();
    expect(
      screen.getByText(new RegExp(`© ${currentYear} Auto Forex Trader`, 'i'))
    ).toBeInTheDocument();
  });
});
