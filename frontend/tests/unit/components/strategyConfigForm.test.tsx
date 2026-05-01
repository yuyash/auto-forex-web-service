import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import StrategyConfigForm from '../../../src/components/strategy/StrategyConfigForm';
import type { ConfigSchema, StrategyConfig } from '../../../src/types/strategy';

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
