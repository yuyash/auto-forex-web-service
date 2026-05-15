import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
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

vi.mock('../../hooks/useConfigurationMutations', () => ({
  useCopyConfiguration: () => ({
    mutate: vi.fn(),
  }),
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
  it('shows the configuration revision on list cards', () => {
    render(
      <MemoryRouter>
        <ConfigurationCard configuration={configuration} />
      </MemoryRouter>
    );

    expect(screen.getByText('Revision')).toBeInTheDocument();
    expect(screen.getByText('rev.7')).toBeInTheDocument();
  });
});
