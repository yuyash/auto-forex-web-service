/**
 * Integration test for ConfirmDialog component.
 * Verifies rendering, user interaction, and callback behavior.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { act, type ComponentProps } from 'react';
import ConfirmDialog from '../../../src/components/common/ConfirmDialog';

describe('ConfirmDialog', () => {
  const defaultProps = {
    open: true,
    title: 'Delete Task',
    message: 'Are you sure you want to delete this task?',
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  };

  const renderConfirmDialog = async (
    props: Partial<ComponentProps<typeof ConfirmDialog>> = {}
  ) => {
    await act(async () => {
      render(<ConfirmDialog {...defaultProps} {...props} />);
    });
  };

  it('renders title and message when open', async () => {
    await renderConfirmDialog();
    expect(screen.getByText('Delete Task')).toBeInTheDocument();
    expect(
      screen.getByText('Are you sure you want to delete this task?')
    ).toBeInTheDocument();
  });

  it('does not render when closed', async () => {
    await renderConfirmDialog({ open: false });
    expect(screen.queryByText('Delete Task')).not.toBeInTheDocument();
  });

  it('calls onConfirm when confirm button is clicked', async () => {
    const user = userEvent.setup();
    await renderConfirmDialog();

    await user.click(screen.getByRole('button', { name: /confirm/i }));
    expect(defaultProps.onConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when cancel button is clicked', async () => {
    const user = userEvent.setup();
    await renderConfirmDialog();

    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(defaultProps.onCancel).toHaveBeenCalledTimes(1);
  });

  it('renders custom button text', async () => {
    await renderConfirmDialog({
      confirmText: 'Yes, delete',
      cancelText: 'No, keep',
    });
    expect(
      screen.getByRole('button', { name: /yes, delete/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /no, keep/i })
    ).toBeInTheDocument();
  });

  it('has proper ARIA attributes', async () => {
    await renderConfirmDialog();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
