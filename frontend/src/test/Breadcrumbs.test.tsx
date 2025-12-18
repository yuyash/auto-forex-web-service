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

  it('renders home breadcrumb for trading tasks', () => {
    renderBreadcrumbs('/trading-tasks');
    expect(screen.getByText('Home')).toBeInTheDocument();
  });

  it('renders breadcrumbs for configurations page', () => {
    renderBreadcrumbs('/configurations');
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Configurations')).toBeInTheDocument();
  });

  it('renders breadcrumbs for backtest tasks page', () => {
    renderBreadcrumbs('/backtest-tasks');
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Backtest Tasks')).toBeInTheDocument();
  });

  it('renders breadcrumbs for settings page', () => {
    renderBreadcrumbs('/settings');
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('renders home icon for first breadcrumb', () => {
    renderBreadcrumbs('/trading-tasks');
    const homeIcon = document.querySelector('[data-testid="HomeIcon"]');
    expect(homeIcon).toBeInTheDocument();
  });

  it('renders links for non-last breadcrumbs', () => {
    renderBreadcrumbs('/backtest-tasks/new');
    const links = screen.getAllByRole('link');
    expect(links.length).toBeGreaterThan(0);
  });

  it('renders last breadcrumb as text, not link', () => {
    renderBreadcrumbs('/backtest-tasks/new');
    const newTaskText = screen.getByText('New Task');
    expect(newTaskText.tagName).not.toBe('A');
  });
});
