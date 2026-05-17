import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import type { StrategyConfig } from '../types/configuration';
import ConfigurationsPage from './ConfigurationsPage';

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

const mocks = vi.hoisted(() => ({
  copyConfigurationMutation: {
    mutate: vi.fn(),
    reset: vi.fn(),
    isLoading: false,
    error: null as Error | null,
  },
  deleteConfigurationMutation: {
    mutate: vi.fn(),
  },
}));

vi.mock('../components/common', () => ({
  Breadcrumbs: () => null,
  BulkActionToolbar: () => null,
  ColumnCountControl: () => null,
  PageContainer: ({ children }: { children: ReactNode }) => (
    <main>{children}</main>
  ),
  useToast: () => ({
    showError: vi.fn(),
    showSuccess: vi.fn(),
  }),
}));

vi.mock('../components/configurations/ConfigurationDeleteDialog', () => ({
  default: () => null,
}));

vi.mock('../hooks/useConfigurations', () => ({
  useConfigurations: () => ({
    data: {
      count: 1,
      next: null,
      previous: null,
      results: [configuration],
    },
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  }),
}));

vi.mock('../hooks/useStrategies', () => ({
  useStrategies: () => ({
    strategies: [{ id: 'snowball', name: 'Snowball' }],
  }),
  getStrategyDisplayName: () => 'Snowball',
}));

vi.mock('../hooks/useConfigurationMutations', () => ({
  useCopyConfiguration: () => mocks.copyConfigurationMutation,
  useDeleteConfiguration: () => mocks.deleteConfigurationMutation,
}));

vi.mock('../hooks/useDateTimeFormatter', () => ({
  useDateTimeFormatter: () => ({
    formatDate: () => '2026-05-01',
  }),
}));

describe('ConfigurationsPage', () => {
  beforeEach(() => {
    mocks.copyConfigurationMutation.mutate.mockClear();
    mocks.copyConfigurationMutation.mutate.mockResolvedValue(configuration);
    mocks.copyConfigurationMutation.reset.mockClear();
    mocks.copyConfigurationMutation.isLoading = false;
    mocks.copyConfigurationMutation.error = null;
  });

  it('copies a strategy configuration from the list page card action', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <ConfigurationsPage />
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
    await user.type(nameInput, 'Balanced Grid List Copy');
    await user.click(
      screen.getByRole('button', { name: 'Copy Configuration' })
    );

    expect(mocks.copyConfigurationMutation.mutate).toHaveBeenCalledWith({
      id: 'config-1',
      name: 'Balanced Grid List Copy',
    });
  });
});
