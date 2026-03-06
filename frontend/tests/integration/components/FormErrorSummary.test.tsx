/**
 * Integration test for FormErrorSummary component.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import FormErrorSummary from '../../../src/components/common/FormErrorSummary';

describe('FormErrorSummary', () => {
  it('renders nothing when there are no errors', () => {
    const { container } = render(<FormErrorSummary errors={{}} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders error messages for each field', () => {
    render(
      <FormErrorSummary
        errors={{
          email: 'Email is required',
          password: 'Password too short',
        }}
      />
    );
    expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    expect(screen.getByText(/password too short/i)).toBeInTheDocument();
  });

  it('renders array error messages', () => {
    render(
      <FormErrorSummary
        errors={{
          name: ['Too short', 'Contains invalid characters'],
        }}
      />
    );
    expect(screen.getByText(/too short/i)).toBeInTheDocument();
    expect(
      screen.getByText(/contains invalid characters/i)
    ).toBeInTheDocument();
  });

  it('renders custom title', () => {
    render(
      <FormErrorSummary errors={{ field: 'Error' }} title="Fix these issues:" />
    );
    expect(screen.getByText('Fix these issues:')).toBeInTheDocument();
  });

  it('renders as an alert', () => {
    render(<FormErrorSummary errors={{ field: 'Error' }} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});
