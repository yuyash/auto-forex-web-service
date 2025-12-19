import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import ConfigurationForm from '../components/configurations/ConfigurationForm';

let lastStrategyConfigProps: unknown = null;

vi.mock('../components/strategy/StrategyConfigForm', () => ({
  default: (props: unknown) => {
    lastStrategyConfigProps = props;
    return <div data-testid="strategy-config-form" />;
  },
}));

vi.mock('../hooks/useStrategies', () => ({
  useStrategies: () => ({
    strategies: [
      {
        id: 'floor',
        name: 'Floor Strategy',
        description: 'desc',
        config_schema: {
          type: 'object',
          properties: {
            instrument: { type: 'string', title: 'Instrument' },
            max_layers: { type: 'integer', title: 'Maximum Layers' },
          },
        },
      },
    ],
    isLoading: false,
    error: null,
  }),
}));

const defaultsMock = vi.hoisted(() => vi.fn());
vi.mock('../services/api', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  const strategiesApi = actual.strategiesApi as Record<string, unknown>;
  return {
    ...actual,
    strategiesApi: {
      ...strategiesApi,
      defaults: defaultsMock,
    },
  };
});

describe('ConfigurationForm defaults prefill', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    lastStrategyConfigProps = null;
  });

  it('prefills parameters from backend defaults', async () => {
    defaultsMock.mockResolvedValue({
      strategy_id: 'floor',
      defaults: { instrument: 'USD_JPY', max_layers: 3 },
    });

    render(
      <ConfigurationForm
        mode="create"
        initialData={{ strategy_type: 'floor', parameters: {} }}
        onSubmit={async () => undefined}
        onCancel={() => undefined}
      />
    );

    // Navigate to Parameters step (Basic Info -> Strategy Type -> Parameters)
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => {
      expect(defaultsMock).toHaveBeenCalledWith('floor');
    });

    await waitFor(() => {
      expect(lastStrategyConfigProps).not.toBeNull();
      const props = lastStrategyConfigProps as {
        config?: Record<string, unknown>;
      };
      expect(props.config).toMatchObject({
        instrument: 'USD_JPY',
        max_layers: 3,
      });
    });
  });
});
