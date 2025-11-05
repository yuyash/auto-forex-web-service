import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';
import i18n from '../i18n/config';
import Breadcrumbs from '../components/common/Breadcrumbs';
import '@testing-library/jest-dom';

describe('Breadcrumbs', () => {
  const renderBreadcrumbs = (pathname: string) => {
    return render(
      <MemoryRouter initialEntries={[pathname]}>
        <I18nextProvider i18n={i18n}>
          <Breadcrumbs />
        </I18nextProvider>
      </MemoryRouter>
    );
  };

  it('renders home breadcrumb for dashboard', () => {
    renderBreadcrumbs('/dashboard');
    expect(screen.getByText('Home')).toBeInTheDocument();
  });

  it('renders breadcrumbs for orders page', () => {
    renderBreadcrumbs('/orders');
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Orders')).toBeInTheDocument();
  });

  it('renders breadcrumbs for positions page', () => {
    renderBreadcrumbs('/positions');
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Positions')).toBeInTheDocument();
  });

  it('renders breadcrumbs for strategy page', () => {
    renderBreadcrumbs('/strategy');
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Strategy')).toBeInTheDocument();
  });

  it('renders breadcrumbs for backtest page', () => {
    renderBreadcrumbs('/backtest');
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Backtest')).toBeInTheDocument();
  });

  it('renders breadcrumbs for settings page', () => {
    renderBreadcrumbs('/settings');
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('renders breadcrumbs for admin dashboard', () => {
    renderBreadcrumbs('/admin');
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Admin')).toBeInTheDocument();
  });

  it('renders breadcrumbs for admin settings', () => {
    renderBreadcrumbs('/admin/settings');
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('renders breadcrumbs for admin events', () => {
    renderBreadcrumbs('/admin/events');
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.getByText('Events')).toBeInTheDocument();
  });

  it('renders breadcrumbs for admin users', () => {
    renderBreadcrumbs('/admin/users');
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.getByText('User Management')).toBeInTheDocument();
  });

  it('renders home icon for first breadcrumb', () => {
    renderBreadcrumbs('/orders');
    const homeIcon = document.querySelector('[data-testid="HomeIcon"]');
    expect(homeIcon).toBeInTheDocument();
  });

  it('renders links for non-last breadcrumbs', () => {
    renderBreadcrumbs('/admin/settings');
    const links = screen.getAllByRole('link');
    expect(links.length).toBeGreaterThan(0);
  });

  it('renders last breadcrumb as text, not link', () => {
    renderBreadcrumbs('/orders');
    const ordersText = screen.getByText('Orders');
    expect(ordersText.tagName).not.toBe('A');
  });
});
