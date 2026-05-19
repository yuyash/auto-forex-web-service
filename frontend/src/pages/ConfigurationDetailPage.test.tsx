import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { StrategyConfig } from '../types/configuration';
import ConfigurationDetailPage from './ConfigurationDetailPage';

const configuration: StrategyConfig = {
  id: 'config-1',
  user_id: 1,
  name: 'Balanced Grid',
  strategy_type: 'snowball',
  parameters: {},
  revision: 7,
  config_hash: 'hash-7',
  description: 'Primary config',
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
}));

vi.mock('../hooks/useConfigurations', () => ({
  useConfiguration: () => ({
    data: configuration,
    isLoading: false,
    error: null,
  }),
}));

vi.mock('../hooks/useStrategies', () => ({
  useStrategies: () => ({
    strategies: [
      {
        id: 'snowball',
        name: 'Snowball',
        config_schema: { type: 'object', properties: {} },
      },
    ],
  }),
  getStrategyDisplayName: () => 'Snowball',
}));

vi.mock('../hooks/useConfigurationMutations', () => ({
  useCopyConfiguration: () => mocks.copyConfigurationMutation,
}));

vi.mock('../hooks/useDateTimeFormatter', () => ({
  useDateTimeFormatter: () => ({
    formatDate: () => '2026-05-01',
  }),
}));

function renderDetailPage() {
  return render(
    <MemoryRouter initialEntries={['/configurations/config-1']}>
      <Routes>
        <Route
          path="/configurations/:id"
          element={<ConfigurationDetailPage />}
        />
      </Routes>
    </MemoryRouter>
  );
}

describe('ConfigurationDetailPage', () => {
  beforeEach(() => {
    mocks.copyConfigurationMutation.mutate.mockClear();
    mocks.copyConfigurationMutation.mutate.mockResolvedValue(configuration);
    mocks.copyConfigurationMutation.reset.mockClear();
    mocks.copyConfigurationMutation.isLoading = false;
    mocks.copyConfigurationMutation.error = null;
  });

  it('opens a copy dialog and submits the requested configuration name', async () => {
    const user = userEvent.setup();
    renderDetailPage();

    await user.click(screen.getByRole('button', { name: 'Copy' }));

    expect(
      screen.getByRole('heading', { name: 'Copy Configuration' })
    ).toBeInTheDocument();

    const nameInput = screen.getByRole('textbox', {
      name: 'New Configuration Name',
    });
    expect(nameInput).toHaveValue('Balanced Grid (Copy)');

    await user.clear(nameInput);
    await user.type(nameInput, 'Balanced Grid Detail Copy');
    await user.click(
      screen.getByRole('button', { name: 'Copy Configuration' })
    );

    expect(mocks.copyConfigurationMutation.reset).toHaveBeenCalled();
    expect(mocks.copyConfigurationMutation.mutate).toHaveBeenCalledWith({
      id: 'config-1',
      name: 'Balanced Grid Detail Copy',
    });
  });
});
