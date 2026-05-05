import { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import StrategyConfigForm from '../../../src/components/strategy/StrategyConfigForm';
import type { ConfigSchema, StrategyConfig } from '../../../src/types/strategy';

function ControlledStrategyConfigForm({
  schema,
  initialConfig,
  onChange,
}: {
  schema: ConfigSchema;
  initialConfig: StrategyConfig;
  onChange: (config: StrategyConfig) => void;
}) {
  const [config, setConfig] = useState<StrategyConfig>(initialConfig);

  return (
    <StrategyConfigForm
      configSchema={schema}
      config={config}
      onChange={(nextConfig) => {
        onChange(nextConfig);
        setConfig(nextConfig);
      }}
    />
  );
}

describe('StrategyConfigForm presets', () => {
  it('applies schema preset parameters without dropping existing values', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const config: StrategyConfig = { base_units: 1000, max_net_units: 5000 };
    const schema: ConfigSchema = {
      type: 'object',
      properties: {
        base_units: {
          type: 'integer',
          title: 'Base Units',
          default: 1000,
        },
        max_net_units: {
          type: 'integer',
          title: 'Max Net Units',
          default: 10000,
        },
        grid_spacing_mode: {
          type: 'string',
          title: 'Grid Spacing Mode',
          enum: ['fixed', 'atr'],
          default: 'fixed',
        },
      },
      presets: [
        {
          id: 'balanced',
          label: 'Balanced',
          parameters: {
            grid_spacing_mode: 'atr',
            max_net_units: 7000,
          },
        },
      ],
    };

    render(
      <StrategyConfigForm
        configSchema={schema}
        config={config}
        onChange={onChange}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Balanced' }));

    expect(onChange).toHaveBeenCalledWith({
      base_units: 1000,
      max_net_units: 7000,
      grid_spacing_mode: 'atr',
    });
  });
});

describe('StrategyConfigForm dependencies', () => {
  it('removes hidden dependent values and restores defaults when shown again', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const schema: ConfigSchema = {
      type: 'object',
      properties: {
        capacity_limit_mode: {
          type: 'string',
          title: 'Position Capacity Limit',
          enum: ['add_count', 'max_net_units'],
          enum_labels: {
            add_count: 'By Add Steps',
            max_net_units: 'By Max Net Units',
          },
          default: 'add_count',
        },
        max_net_units: {
          type: 'integer',
          title: 'Max Net Units',
          default: 8000,
          dependsOn: {
            field: 'capacity_limit_mode',
            values: ['max_net_units'],
          },
        },
        add_unit_allocation_mode: {
          type: 'string',
          title: 'Add Unit Allocation',
          enum: ['fixed', 'remaining_linear'],
          default: 'fixed',
          dependsOn: {
            field: 'capacity_limit_mode',
            values: ['max_net_units'],
          },
        },
      },
    };

    render(
      <ControlledStrategyConfigForm
        schema={schema}
        initialConfig={{
          capacity_limit_mode: 'add_count',
          max_net_units: 5000,
          add_unit_allocation_mode: 'remaining_linear',
        }}
        onChange={onChange}
      />
    );

    await waitFor(() => {
      expect(screen.queryByLabelText('Max Net Units')).not.toBeInTheDocument();
      expect(onChange).toHaveBeenLastCalledWith({
        capacity_limit_mode: 'add_count',
      });
    });

    await user.click(screen.getByRole('combobox'));
    await user.click(screen.getByRole('option', { name: 'By Max Net Units' }));

    expect(onChange).toHaveBeenLastCalledWith({
      capacity_limit_mode: 'max_net_units',
      max_net_units: 8000,
      add_unit_allocation_mode: 'fixed',
    });
  });
});

describe('StrategyConfigForm comparisonRules', () => {
  it('shows cross-field validation errors for visible numeric fields', async () => {
    const schema: ConfigSchema = {
      type: 'object',
      properties: {
        interval_mode: {
          type: 'string',
          title: 'Add Interval Mode',
          enum: ['additive', 'subtractive'],
          default: 'additive',
        },
        n_pips_head: {
          type: 'number',
          title: 'Interval Head',
          default: 30,
        },
        n_pips_tail: {
          type: 'number',
          title: 'Interval Tail',
          default: 30,
          dependsOn: {
            field: 'interval_mode',
            values: ['additive', 'subtractive'],
          },
          comparisonRules: [
            {
              field: 'n_pips_head',
              operator: 'gte',
              dependsOn: {
                field: 'interval_mode',
                values: ['additive'],
              },
              message: 'Tail must be at least head for additive mode',
            },
          ],
        },
      },
    };

    render(
      <StrategyConfigForm
        configSchema={schema}
        config={{
          interval_mode: 'additive',
          n_pips_head: 30,
          n_pips_tail: 14,
        }}
        onChange={() => undefined}
        showValidation
      />
    );

    expect(
      await screen.findByText('Tail must be at least head for additive mode')
    ).toBeInTheDocument();
  });
});
