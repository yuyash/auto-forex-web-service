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
        refill_limit_enabled: {
          type: 'boolean',
          title: 'Move To Next Layer After Closed Steps',
        },
        refill_up_to: {
          type: 'integer',
          title: 'Reusable Steps Through',
          dependsOn: { field: 'refill_limit_enabled', values: [true] },
        },
        rebuild_entry_price_mode: {
          type: 'string',
          title: 'Rebuild Entry Price Mode',
          dependsOn: {
            field: 'stop_loss_enabled',
            values: [true],
            and: [{ field: 'rebuild_enabled', values: [true] }],
          },
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
        stop_loss_enabled: true,
        rebuild_enabled: true,
        rebuild_entry_price_mode: 'original_entry',
      },
      current: {
        id: 'config-1',
        name: 'Historical Config Name',
        strategy_type: 'snowball',
        parameters: {
          reseed_on_all_pending: false,
          stop_loss_enabled: true,
          rebuild_enabled: true,
          rebuild_entry_price_mode: 'stop_loss_exit',
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
    expect(screen.getByText('Rebuild Entry Price Mode')).toBeInTheDocument();
    expect(screen.getByText('stop_loss_exit')).toBeInTheDocument();
    expect(screen.queryByText('original_entry')).not.toBeInTheDocument();
  });

  it('keeps layer rollover visible when rebuild is disabled', () => {
    const config: NonNullable<TaskExecution['strategy_config']> = {
      id: 'config-1',
      name: 'No Rebuild Config',
      strategy_type: 'snowball',
      parameters: {
        stop_loss_enabled: true,
        rebuild_enabled: false,
        refill_limit_enabled: false,
        refill_up_to: 2,
        rebuild_entry_price_mode: 'stop_loss_exit',
      },
      current: {
        id: 'config-1',
        name: 'No Rebuild Config',
        strategy_type: 'snowball',
        parameters: {
          stop_loss_enabled: true,
          rebuild_enabled: false,
          refill_limit_enabled: false,
          refill_up_to: 2,
          rebuild_entry_price_mode: 'stop_loss_exit',
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
      screen.queryByText('Rebuild Entry Price Mode')
    ).not.toBeInTheDocument();
    expect(screen.queryByText('stop_loss_exit')).not.toBeInTheDocument();
    expect(
      screen.getByText('Move To Next Layer After Closed Steps')
    ).toBeInTheDocument();
    expect(screen.getAllByText('false').length).toBeGreaterThan(0);
    expect(
      screen.queryByText('Reusable Steps Through')
    ).not.toBeInTheDocument();
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
