import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';
import AppLayout from '../components/layout/AppLayout';
import ToastProvider from '../components/common/Toast';

describe('AppLayout', () => {
  it('renders header, footer, and content', async () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <ToastProvider>
            <Routes>
              <Route element={<AppLayout />}>
                <Route path="/" element={<div>Test Content</div>} />
              </Route>
            </Routes>
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    );

    // Wait for component to render
    await waitFor(() => {
      // Check header logo
      expect(screen.getByAltText('Logo')).toBeInTheDocument();
    });

    // Check content
    expect(screen.getByText('Test Content')).toBeInTheDocument();

    // Check footer status chips exist
    expect(screen.getByText(/connected|disconnected/i)).toBeInTheDocument();

    // Check that skip links are present for accessibility
    expect(screen.getByText('Skip to main content')).toBeInTheDocument();
    expect(screen.getByText('Skip to navigation')).toBeInTheDocument();
  });
});
