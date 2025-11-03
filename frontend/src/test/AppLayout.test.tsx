import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import AppLayout from '../components/layout/AppLayout';

describe('AppLayout', () => {
  it('renders header, footer, and content', async () => {
    render(
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<div>Test Content</div>} />
          </Route>
        </Routes>
      </BrowserRouter>
    );

    // Wait for i18n to load translations
    await waitFor(() => {
      // Check header
      expect(screen.getByText('Auto Forex Trading System')).toBeInTheDocument();
    });

    // Check navigation links
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Orders')).toBeInTheDocument();
    expect(screen.getByText('Positions')).toBeInTheDocument();
    expect(screen.getByText('Strategy')).toBeInTheDocument();
    expect(screen.getByText('Backtest')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();

    // Check content
    expect(screen.getByText('Test Content')).toBeInTheDocument();

    // Check footer
    const currentYear = new Date().getFullYear();
    expect(
      screen.getByText(
        new RegExp(`© ${currentYear} Auto Forex Trading System`, 'i')
      )
    ).toBeInTheDocument();
  });
});
