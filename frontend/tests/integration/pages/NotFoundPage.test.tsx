/**
 * Integration tests for NotFoundPage.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NotFoundPage from '../../../src/pages/NotFoundPage';

function renderNotFound() {
  return render(
    <MemoryRouter>
      <NotFoundPage />
    </MemoryRouter>
  );
}

describe('NotFoundPage', () => {
  it('renders 404 heading', () => {
    renderNotFound();
    expect(screen.getByText('404')).toBeInTheDocument();
  });

  it('renders descriptive message', () => {
    renderNotFound();
    expect(screen.getByText(/page not found/i)).toBeInTheDocument();
    expect(screen.getByText(/does not exist/i)).toBeInTheDocument();
  });

  it('has a link to home', () => {
    renderNotFound();
    const link = screen.getByRole('link', { name: /go to home/i });
    expect(link).toHaveAttribute('href', '/');
  });
});
