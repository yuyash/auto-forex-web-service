import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import type { StrategyConfig } from '../../types/configuration';
import ConfigurationCard from './ConfigurationCard';

vi.mock('./ConfigurationDeleteDialog', () => ({
  default: () => null,
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { timezone: 'UTC', language: 'en' },
  }),
}));

vi.mock('../../hooks/useStrategies', () => ({
  useStrategies: () => ({
    strategies: [{ id: 'snowball', name: 'Snowball' }],
  }),
  getStrategyDisplayName: () => 'Snowball',
}));

const mocks = vi.hoisted(() => ({
  copyConfigurationMutation: {
    mutate: vi.fn(),
    reset: vi.fn(),
    isLoading: false,
    error: null as Error | null,
  },
}));

vi.mock('../../hooks/useConfigurationMutations', () => ({
  useCopyConfiguration: () => mocks.copyConfigurationMutation,
}));

const configuration: StrategyConfig = {
  id: 'config-1',
  user_id: 1,
  name: 'Balanced Grid',
  strategy_type: 'snowball',
  parameters: {},
  revision: 7,
  config_hash: 'hash-7',
  description: '',
  is_in_use: false,
  has_running_tasks: false,
  created_at: '2026-05-01T00:00:00Z',
  updated_at: '2026-05-01T00:00:00Z',
};

describe('ConfigurationCard', () => {
  beforeEach(() => {
    mocks.copyConfigurationMutation.mutate.mockClear();
    mocks.copyConfigurationMutation.mutate.mockResolvedValue(configuration);
    mocks.copyConfigurationMutation.reset.mockClear();
    mocks.copyConfigurationMutation.isLoading = false;
    mocks.copyConfigurationMutation.error = null;
  });

  it('shows the configuration revision on list cards', () => {
    render(
      <MemoryRouter>
        <ConfigurationCard configuration={configuration} />
      </MemoryRouter>
    );

    expect(screen.getByText('Revision')).toBeInTheDocument();
    expect(screen.getByText('Rev.7')).toBeInTheDocument();
  });

  it('opens a copy dialog and submits the requested configuration name', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <ConfigurationCard configuration={configuration} />
      </MemoryRouter>
    );

    await user.click(screen.getByRole('button', { name: 'Copy' }));

    expect(
      screen.getByRole('heading', { name: 'Copy Configuration' })
    ).toBeInTheDocument();
    const nameInput = screen.getByRole('textbox', {
      name: 'New Configuration Name',
    });
    expect(nameInput).toHaveValue('Balanced Grid (Copy)');

    await user.clear(nameInput);
    await user.type(nameInput, 'Balanced Grid Variant');
    await user.click(
      screen.getByRole('button', { name: 'Copy Configuration' })
    );

    expect(mocks.copyConfigurationMutation.reset).toHaveBeenCalled();
    expect(mocks.copyConfigurationMutation.mutate).toHaveBeenCalledWith({
      id: 'config-1',
      name: 'Balanced Grid Variant',
    });
  });

  it('opens the same copy dialog from the 3dots menu', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <ConfigurationCard configuration={configuration} />
      </MemoryRouter>
    );

    await user.click(screen.getByRole('button', { name: 'More actions' }));
    await user.click(screen.getByRole('menuitem', { name: 'Copy' }));

    expect(
      screen.getByRole('heading', { name: 'Copy Configuration' })
    ).toBeInTheDocument();

    const nameInput = screen.getByRole('textbox', {
      name: 'New Configuration Name',
    });
    expect(nameInput).toHaveValue('Balanced Grid (Copy)');

    await user.clear(nameInput);
    await user.type(nameInput, 'Balanced Grid Menu Copy');
    await user.click(
      screen.getByRole('button', { name: 'Copy Configuration' })
    );

    expect(mocks.copyConfigurationMutation.mutate).toHaveBeenCalledWith({
      id: 'config-1',
      name: 'Balanced Grid Menu Copy',
    });
  });
});
