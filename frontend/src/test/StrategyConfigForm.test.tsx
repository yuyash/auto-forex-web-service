import { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import StrategyConfigForm from '../components/strategy/StrategyConfigForm';
import type { ConfigSchema, StrategyConfig } from '../types/strategy';

// Mock i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) => {
      const translations: Record<string, string> = {
        'validation.required': 'This field is required',
        'validation.invalidNumber': 'Must be a valid number',
        'validation.minimum': `Must be at least ${options?.min}`,
        'validation.maximum': `Must be at most ${options?.max}`,
        'validation.integer': 'Must be a whole number',
        'validation.invalidArray': 'All items must be strings',
        'validation.invalidOption': 'Invalid option selected',
        'validation.formErrors':
          'Please fix the errors below before proceeding.',
        noParameters: 'This strategy has no configurable parameters.',
        strategyParameters: 'Strategy Parameters',
        requiredFields: 'Required fields',
      };
      return translations[key] || options?.defaultValue || key;
    },
  }),
}));

describe('StrategyConfigForm', () => {
  const mockOnChange = vi.fn();

  const floorStrategySchema: ConfigSchema = {
    type: 'object',
    properties: {
      base_lot_size: {
        type: 'number',
        description: 'Initial lot size for first position',
        default: 1.0,
        minimum: 0.01,
        maximum: 100.0,
      },
      scaling_mode: {
        type: 'string',
        description: 'Position scaling method',
        enum: ['additive', 'multiplicative'],
        default: 'additive',
      },
      retracement_pips: {
        type: 'integer',
        description: 'Pips retracement before adding position',
        default: 30,
        minimum: 5,
        maximum: 200,
      },
      max_layers: {
        type: 'integer',
        description: 'Maximum number of layers',
        default: 3,
        minimum: 1,
        maximum: 10,
      },
      take_profit_pips: {
        type: 'integer',
        description: 'Take profit target in pips',
        default: 25,
        minimum: 5,
        maximum: 500,
      },
      enable_trailing_stop: {
        type: 'boolean',
        description: 'Enable trailing stop loss',
        default: false,
      },
    },
    required: ['base_lot_size', 'scaling_mode', 'retracement_pips'],
  };

  const defaultConfig: StrategyConfig = {
    base_lot_size: 1.0,
    scaling_mode: 'additive',
    retracement_pips: 30,
    max_layers: 3,
    take_profit_pips: 25,
    enable_trailing_stop: false,
  };

  beforeEach(() => {
    mockOnChange.mockClear();
  });

  it('renders all form fields based on schema', () => {
    render(
      <StrategyConfigForm
        configSchema={floorStrategySchema}
        config={defaultConfig}
        onChange={mockOnChange}
      />
    );

    expect(
      screen.getByRole('spinbutton', { name: /Base Lot Size/i })
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Scaling Mode/i)[0]).toBeInTheDocument();
    expect(
      screen.getByRole('spinbutton', { name: /Retracement Pips/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('spinbutton', { name: /Max Layers/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('spinbutton', { name: /Take Profit Pips/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('checkbox', { name: /Enable Trailing Stop/i })
    ).toBeInTheDocument();
  });

  it('displays field descriptions as helper text', () => {
    render(
      <StrategyConfigForm
        configSchema={floorStrategySchema}
        config={defaultConfig}
        onChange={mockOnChange}
      />
    );

    expect(
      screen.getByText('Initial lot size for first position')
    ).toBeInTheDocument();
    expect(screen.getByText('Position scaling method')).toBeInTheDocument();
    expect(
      screen.getByText('Pips retracement before adding position')
    ).toBeInTheDocument();
  });

  it('displays current config values', () => {
    render(
      <StrategyConfigForm
        configSchema={floorStrategySchema}
        config={defaultConfig}
        onChange={mockOnChange}
      />
    );

    const baseLotInput = screen.getByRole('spinbutton', {
      name: /Base Lot Size/i,
    }) as HTMLInputElement;
    expect(baseLotInput.value).toBe('1');

    const retracementInput = screen.getByRole('spinbutton', {
      name: /Retracement Pips/i,
    }) as HTMLInputElement;
    expect(retracementInput.value).toBe('30');
  });

  it('calls onChange when number field is modified', async () => {
    render(
      <StrategyConfigForm
        configSchema={floorStrategySchema}
        config={defaultConfig}
        onChange={mockOnChange}
      />
    );

    const baseLotInput = screen.getByRole('spinbutton', {
      name: /Base Lot Size/i,
    });
    fireEvent.change(baseLotInput, { target: { value: '2.5' } });

    await waitFor(() => {
      expect(mockOnChange).toHaveBeenCalledWith({
        ...defaultConfig,
        base_lot_size: 2.5,
      });
    });
  });

  it('calls onChange when enum field is modified', async () => {
    render(
      <StrategyConfigForm
        configSchema={floorStrategySchema}
        config={defaultConfig}
        onChange={mockOnChange}
      />
    );

    // Find the select by its displayed value
    const scalingModeSelect = screen
      .getByText('Additive')
      .closest('div[role="combobox"]');
    expect(scalingModeSelect).toBeInTheDocument();
    fireEvent.mouseDown(scalingModeSelect!);

    const multiplicativeOption = await screen.findByText(/Multiplicative/i);
    fireEvent.click(multiplicativeOption);

    await waitFor(() => {
      expect(mockOnChange).toHaveBeenCalledWith({
        ...defaultConfig,
        scaling_mode: 'multiplicative',
      });
    });
  });

  it('calls onChange when boolean field is toggled', async () => {
    render(
      <StrategyConfigForm
        configSchema={floorStrategySchema}
        config={defaultConfig}
        onChange={mockOnChange}
      />
    );

    const trailingStopCheckbox = screen.getByRole('checkbox', {
      name: /Enable Trailing Stop/i,
    });
    fireEvent.click(trailingStopCheckbox);

    await waitFor(() => {
      expect(mockOnChange).toHaveBeenCalledWith({
        ...defaultConfig,
        enable_trailing_stop: true,
      });
    });
  });

  it('validates required fields when showValidation is true', () => {
    const emptyConfig: StrategyConfig = {};

    render(
      <StrategyConfigForm
        configSchema={floorStrategySchema}
        config={emptyConfig}
        onChange={mockOnChange}
        showValidation={true}
      />
    );

    expect(
      screen.getByText('Please fix the errors below before proceeding.')
    ).toBeInTheDocument();
    expect(screen.getAllByText('This field is required')).toHaveLength(3);
  });

  it('validates minimum value constraint', async () => {
    const invalidConfig: StrategyConfig = {
      ...defaultConfig,
      base_lot_size: 0.005,
    };

    render(
      <StrategyConfigForm
        configSchema={floorStrategySchema}
        config={invalidConfig}
        onChange={mockOnChange}
        showValidation={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Must be at least 0.01')).toBeInTheDocument();
    });
  });

  it('validates maximum value constraint', async () => {
    const invalidConfig: StrategyConfig = {
      ...defaultConfig,
      retracement_pips: 250,
    };

    render(
      <StrategyConfigForm
        configSchema={floorStrategySchema}
        config={invalidConfig}
        onChange={mockOnChange}
        showValidation={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Must be at most 200')).toBeInTheDocument();
    });
  });

  it('validates integer type constraint', async () => {
    render(
      <StrategyConfigForm
        configSchema={floorStrategySchema}
        config={defaultConfig}
        onChange={mockOnChange}
        showValidation={true}
      />
    );

    const retracementInput = screen.getByRole('spinbutton', {
      name: /Retracement Pips/i,
    });
    fireEvent.change(retracementInput, { target: { value: '30.5' } });

    await waitFor(() => {
      expect(mockOnChange).toHaveBeenCalledWith({
        ...defaultConfig,
        retracement_pips: 30,
      });
    });
  });

  it('disables all fields when disabled prop is true', () => {
    render(
      <StrategyConfigForm
        configSchema={floorStrategySchema}
        config={defaultConfig}
        onChange={mockOnChange}
        disabled={true}
      />
    );

    const baseLotInput = screen.getByRole('spinbutton', {
      name: /Base Lot Size/i,
    });
    expect(baseLotInput).toBeDisabled();

    const scalingModeSelect = screen
      .getByText('Additive')
      .closest('div[role="combobox"]');
    expect(scalingModeSelect).toHaveAttribute('aria-disabled', 'true');

    const trailingStopCheckbox = screen.getByRole('checkbox', {
      name: /Enable Trailing Stop/i,
    });
    expect(trailingStopCheckbox).toBeDisabled();
  });

  it('handles array type fields', () => {
    const schemaWithArray: ConfigSchema = {
      type: 'object',
      properties: {
        instrument: {
          type: 'array',
          description: 'Trading instrument',
          items: { type: 'string' },
        },
      },
    };

    const configWithArray: StrategyConfig = {
      instrument: ['EUR_USD', 'GBP_USD'],
    };

    render(
      <StrategyConfigForm
        configSchema={schemaWithArray}
        config={configWithArray}
        onChange={mockOnChange}
      />
    );

    const instrumentInput = screen.getByRole('textbox', {
      name: /Instrument/i,
    });
    expect(instrumentInput).toHaveValue('EUR_USD, GBP_USD');
  });

  it('updates array field when comma-separated values are entered', async () => {
    const schemaWithArray: ConfigSchema = {
      type: 'object',
      properties: {
        instrument: {
          type: 'array',
          description: 'Trading instrument',
          items: { type: 'string' },
        },
      },
    };

    const configWithArray: StrategyConfig = {
      instrument: [],
    };

    render(
      <StrategyConfigForm
        configSchema={schemaWithArray}
        config={configWithArray}
        onChange={mockOnChange}
      />
    );

    const instrumentInput = screen.getByRole('textbox', {
      name: /Instrument/i,
    });
    fireEvent.change(instrumentInput, {
      target: { value: 'EUR_USD, GBP_USD, USD_JPY' },
    });

    await waitFor(() => {
      expect(mockOnChange).toHaveBeenCalledWith({
        instrument: ['EUR_USD', 'GBP_USD', 'USD_JPY'],
      });
    });
  });

  it('displays message when no parameters are available', () => {
    const emptySchema: ConfigSchema = {
      type: 'object',
      properties: {},
    };

    render(
      <StrategyConfigForm
        configSchema={emptySchema}
        config={{}}
        onChange={mockOnChange}
      />
    );

    expect(
      screen.getByText('This strategy has no configurable parameters.')
    ).toBeInTheDocument();
  });

  it('marks required fields with asterisk', () => {
    render(
      <StrategyConfigForm
        configSchema={floorStrategySchema}
        config={defaultConfig}
        onChange={mockOnChange}
      />
    );

    const baseLotInput = screen.getByRole('spinbutton', {
      name: /Base Lot Size/i,
    });
    expect(baseLotInput).toHaveAttribute('required');

    expect(screen.getByText('* Required fields')).toBeInTheDocument();
  });

  it('formats field labels correctly', () => {
    const schemaWithUnderscores: ConfigSchema = {
      type: 'object',
      properties: {
        max_position_size: {
          type: 'number',
          default: 10,
        },
        stop_loss_pips: {
          type: 'integer',
          default: 50,
        },
      },
    };

    render(
      <StrategyConfigForm
        configSchema={schemaWithUnderscores}
        config={{}}
        onChange={mockOnChange}
      />
    );

    expect(
      screen.getByRole('spinbutton', { name: /Max Position Size/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('spinbutton', { name: /Stop Loss Pips/i })
    ).toBeInTheDocument();
  });

  it('formats enum values correctly', async () => {
    const schemaWithEnums: ConfigSchema = {
      type: 'object',
      properties: {
        order_type: {
          type: 'string',
          enum: ['market_order', 'limit_order', 'stop_order'],
          default: 'market_order',
        },
      },
    };

    render(
      <StrategyConfigForm
        configSchema={schemaWithEnums}
        config={{ order_type: 'market_order' }}
        onChange={mockOnChange}
      />
    );

    const orderTypeSelects = screen.getAllByText('Market Order');
    const orderTypeSelect = orderTypeSelects[0].closest('div[role="combobox"]');
    expect(orderTypeSelect).toBeInTheDocument();
    fireEvent.mouseDown(orderTypeSelect!);

    await waitFor(() => {
      expect(screen.getAllByText('Market Order').length).toBeGreaterThan(0);
      expect(screen.getByText('Limit Order')).toBeInTheDocument();
      expect(screen.getByText('Stop Order')).toBeInTheDocument();
    });
  });

  it('uses default values from schema when config is empty', () => {
    const emptyConfig: StrategyConfig = {};

    render(
      <StrategyConfigForm
        configSchema={floorStrategySchema}
        config={emptyConfig}
        onChange={mockOnChange}
      />
    );

    const baseLotInput = screen.getByRole('spinbutton', {
      name: /Base Lot Size/i,
    }) as HTMLInputElement;
    expect(baseLotInput.value).toBe('1');

    const maxLayersInput = screen.getByRole('spinbutton', {
      name: /Max Layers/i,
    }) as HTMLInputElement;
    expect(maxLayersInput.value).toBe('3');
  });

  it('handles string type fields', () => {
    const schemaWithString: ConfigSchema = {
      type: 'object',
      properties: {
        strategy_name: {
          type: 'string',
          description: 'Custom strategy name',
          default: 'My Strategy',
        },
      },
    };

    render(
      <StrategyConfigForm
        configSchema={schemaWithString}
        config={{ strategy_name: 'Floor Strategy' }}
        onChange={mockOnChange}
      />
    );

    const nameInput = screen.getByRole('textbox', { name: /Strategy Name/i });
    expect(nameInput).toHaveValue('Floor Strategy');
  });

  it('updates string field when text is entered', async () => {
    const schemaWithString: ConfigSchema = {
      type: 'object',
      properties: {
        strategy_name: {
          type: 'string',
          description: 'Custom strategy name',
        },
      },
    };

    render(
      <StrategyConfigForm
        configSchema={schemaWithString}
        config={{}}
        onChange={mockOnChange}
      />
    );

    const nameInput = screen.getByRole('textbox', { name: /Strategy Name/i });
    fireEvent.change(nameInput, { target: { value: 'New Strategy' } });

    await waitFor(() => {
      expect(mockOnChange).toHaveBeenCalledWith({
        strategy_name: 'New Strategy',
      });
    });
  });

  it('removes dependent field values when hidden', async () => {
    const schemaWithDepends: ConfigSchema = {
      type: 'object',
      properties: {
        progression_mode: {
          type: 'string',
          title: 'Progression Mode',
          enum: ['equal', 'additive'],
          default: 'additive',
        },
        progression_increment: {
          type: 'number',
          title: 'Progression Increment',
          default: 5,
          dependsOn: {
            field: 'progression_mode',
            values: ['additive'],
          },
        },
      },
    };

    const configWithDepends: StrategyConfig = {
      progression_mode: 'additive',
      progression_increment: 7,
    };

    const Wrapper = () => {
      const [configState, setConfigState] = useState(configWithDepends);
      return (
        <StrategyConfigForm
          configSchema={schemaWithDepends}
          config={configState}
          onChange={(nextConfig) => {
            setConfigState(nextConfig);
            mockOnChange(nextConfig);
          }}
        />
      );
    };

    render(<Wrapper />);

    const progressionSelect = screen
      .getByText('Additive')
      .closest('div[role="combobox"]');
    expect(progressionSelect).toBeInTheDocument();
    fireEvent.mouseDown(progressionSelect!);

    const equalOption = await screen.findByText('Equal');
    fireEvent.click(equalOption);

    await waitFor(() => {
      expect(mockOnChange).toHaveBeenLastCalledWith({
        progression_mode: 'equal',
      });
    });
  });
});
