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

    // Wait for component to render
    await waitFor(() => {
      // Check header logo
      expect(screen.getByAltText('Logo')).toBeInTheDocument();
    });

    // Check navigation links in header
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Orders')).toBeInTheDocument();
    expect(screen.getByText('Positions')).toBeInTheDocument();
    expect(screen.getByText('Strategy')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();

    // Check content
    expect(screen.getByText('Test Content')).toBeInTheDocument();

    // Check footer status chips exist
    expect(screen.getByText(/connected|disconnected/i)).toBeInTheDocument();
  });
});
