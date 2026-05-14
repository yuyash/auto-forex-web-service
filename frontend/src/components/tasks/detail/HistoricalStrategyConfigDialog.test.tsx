import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import type { Strategy } from '../../../services/api/strategies';
import type { TaskExecution } from '../../../types/execution';
import { HistoricalStrategyConfigDialog } from './HistoricalStrategyConfigDialog';

const strategies: Strategy[] = [
  {
    id: 'snowball',
    name: 'Snowball',
    description: '',
    config_schema: {
      properties: {
        reseed_on_all_pending: {
          type: 'boolean',
          title: 'Start New Cycle When Pending',
        },
        rebuild_entry_price_buffer_pips: {
          type: 'string',
          title: 'Entry Price Buffer',
        },
      },
    },
  },
];

describe('HistoricalStrategyConfigDialog', () => {
  it('renders the execution snapshot instead of the live configuration fields', () => {
    const config: NonNullable<TaskExecution['strategy_config']> = {
      id: 'config-1',
      name: 'Live Config Name',
      strategy_type: 'snowball',
      parameters: {
        reseed_on_all_pending: true,
        rebuild_entry_price_buffer_pips: '0',
      },
      current: {
        id: 'config-1',
        name: 'Historical Config Name',
        strategy_type: 'snowball',
        parameters: {
          reseed_on_all_pending: false,
          rebuild_entry_price_buffer_pips: '5',
        },
      },
      initial: {},
      revisions: [],
    };

    render(
      <HistoricalStrategyConfigDialog
        open
        onClose={() => undefined}
        config={config}
        strategies={strategies}
      />
    );

    expect(
      screen.getByRole('heading', { name: 'Historical Config Name' })
    ).toBeInTheDocument();
    expect(screen.queryByText('Live Config Name')).not.toBeInTheDocument();
    expect(screen.getByText(/Strategy Type:\s*Snowball/)).toBeInTheDocument();
    expect(
      screen.getByText('Start New Cycle When Pending')
    ).toBeInTheDocument();
    expect(screen.getByText('false')).toBeInTheDocument();
    expect(screen.queryByText('true')).not.toBeInTheDocument();
    expect(screen.getByText('Entry Price Buffer')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });

  it('renders an edit link when the displayed snapshot is current', () => {
    const config: NonNullable<TaskExecution['strategy_config']> = {
      id: 'config-1',
      name: 'Current Config',
      strategy_type: 'snowball',
      configuration_revision: 3,
      configuration_hash: 'hash-3',
      parameters: {
        reseed_on_all_pending: true,
      },
      current: {
        id: 'config-1',
        name: 'Current Config',
        strategy_type: 'snowball',
        configuration_revision: 3,
        configuration_hash: 'hash-3',
        parameters: {
          reseed_on_all_pending: true,
        },
      },
      initial: {},
      revisions: [],
    };

    render(
      <MemoryRouter>
        <HistoricalStrategyConfigDialog
          open
          onClose={() => undefined}
          config={config}
          strategies={strategies}
          editHref="/configurations/config-1/edit"
        />
      </MemoryRouter>
    );

    expect(
      screen.getByRole('link', { name: /edit configuration/i })
    ).toHaveAttribute('href', '/configurations/config-1/edit');
  });
});
