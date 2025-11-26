import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '../i18n/config';
import StrategySelector from '../components/strategy/StrategySelector';
import type { Strategy } from '../types/strategy';

const mockStrategies: Strategy[] = [
  {
    id: 'floor',
    name: 'Floor Strategy',
    class_name: 'FloorStrategy',
    description:
      'Multi-layer retracement strategy with retracement-based entries',
    config_schema: {
      type: 'object',
      properties: {
        base_lot_size: {
          type: 'number',
          default: 1.0,
          minimum: 0.01,
        },
        scaling_mode: {
          type: 'string',
          enum: ['additive', 'multiplicative'],
          default: 'additive',
        },
      },
    },
  },
  {
    id: 'ma_crossover',
    name: 'MA Crossover',
    class_name: 'MACrossoverStrategy',
    description: 'Moving average crossover strategy using EMA 12 and EMA 26',
    config_schema: {
      type: 'object',
      properties: {
        fast_period: {
          type: 'integer',
          default: 12,
        },
        slow_period: {
          type: 'integer',
          default: 26,
        },
      },
    },
  },
  {
    id: 'rsi',
    name: 'RSI Strategy',
    class_name: 'RSIStrategy',
    description: 'RSI-based strategy with oversold/overbought signals',
    config_schema: {
      type: 'object',
      properties: {
        period: {
          type: 'integer',
          default: 14,
        },
        oversold: {
          type: 'number',
          default: 30,
        },
        overbought: {
          type: 'number',
          default: 70,
        },
      },
    },
  },
];

const renderWithI18n = (component: React.ReactElement) => {
  return render(<I18nextProvider i18n={i18n}>{component}</I18nextProvider>);
};

describe('StrategySelector', () => {
  it('renders dropdown variant by default', () => {
    const handleChange = vi.fn();
    renderWithI18n(
      <StrategySelector
        strategies={mockStrategies}
        selectedStrategy=""
        onStrategyChange={handleChange}
      />
    );

    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('displays all available strategies in dropdown', () => {
    const handleChange = vi.fn();
    renderWithI18n(
      <StrategySelector
        strategies={mockStrategies}
        selectedStrategy=""
        onStrategyChange={handleChange}
      />
    );

    const select = screen.getByRole('combobox');
    fireEvent.mouseDown(select);

    mockStrategies.forEach((strategy) => {
      expect(screen.getByText(strategy.name)).toBeInTheDocument();
    });
  });

  it('shows strategy description when strategy is selected', () => {
    const handleChange = vi.fn();
    renderWithI18n(
      <StrategySelector
        strategies={mockStrategies}
        selectedStrategy="floor"
        onStrategyChange={handleChange}
      />
    );

    expect(
      screen.getByText(/multi-layer retracement strategy/i)
    ).toBeInTheDocument();
  });

  it('calls onStrategyChange when selection changes', () => {
    const handleChange = vi.fn();
    renderWithI18n(
      <StrategySelector
        strategies={mockStrategies}
        selectedStrategy=""
        onStrategyChange={handleChange}
      />
    );

    const select = screen.getByRole('combobox');
    fireEvent.mouseDown(select);

    const option = screen.getByText('MA Crossover');
    fireEvent.click(option);

    expect(handleChange).toHaveBeenCalledWith('ma_crossover');
  });

  it('renders cards variant when specified', () => {
    const handleChange = vi.fn();
    renderWithI18n(
      <StrategySelector
        strategies={mockStrategies}
        selectedStrategy=""
        onStrategyChange={handleChange}
        variant="cards"
      />
    );

    mockStrategies.forEach((strategy) => {
      expect(screen.getByText(strategy.name)).toBeInTheDocument();
      expect(screen.getByText(strategy.description)).toBeInTheDocument();
    });
  });

  it('highlights selected card in cards variant', () => {
    const handleChange = vi.fn();
    renderWithI18n(
      <StrategySelector
        strategies={mockStrategies}
        selectedStrategy="floor"
        onStrategyChange={handleChange}
        variant="cards"
      />
    );

    expect(screen.getByText('Selected')).toBeInTheDocument();
  });

  it('handles card click in cards variant', () => {
    const handleChange = vi.fn();
    renderWithI18n(
      <StrategySelector
        strategies={mockStrategies}
        selectedStrategy=""
        onStrategyChange={handleChange}
        variant="cards"
      />
    );

    const card = screen.getByText('RSI Strategy').closest('button');
    if (card) {
      fireEvent.click(card);
    }

    expect(handleChange).toHaveBeenCalledWith('rsi');
  });

  it('disables selection when disabled prop is true', () => {
    const handleChange = vi.fn();
    renderWithI18n(
      <StrategySelector
        strategies={mockStrategies}
        selectedStrategy=""
        onStrategyChange={handleChange}
        disabled={true}
      />
    );

    const select = screen.getByRole('combobox');
    expect(select).toHaveAttribute('aria-disabled', 'true');
  });

  it('shows loading state', () => {
    const handleChange = vi.fn();
    renderWithI18n(
      <StrategySelector
        strategies={[]}
        selectedStrategy=""
        onStrategyChange={handleChange}
        loading={true}
      />
    );

    expect(screen.getByText(/loading strategies/i)).toBeInTheDocument();
  });

  it('shows info message when no strategies available', () => {
    const handleChange = vi.fn();
    renderWithI18n(
      <StrategySelector
        strategies={[]}
        selectedStrategy=""
        onStrategyChange={handleChange}
      />
    );

    expect(screen.getByText(/no strategies available/i)).toBeInTheDocument();
  });

  it('displays strategy class name in dropdown', () => {
    const handleChange = vi.fn();
    renderWithI18n(
      <StrategySelector
        strategies={mockStrategies}
        selectedStrategy=""
        onStrategyChange={handleChange}
      />
    );

    const select = screen.getByRole('combobox');
    fireEvent.mouseDown(select);

    expect(screen.getByText('FloorStrategy')).toBeInTheDocument();
    expect(screen.getByText('MACrossoverStrategy')).toBeInTheDocument();
  });

  it('displays strategy class name in cards variant', () => {
    const handleChange = vi.fn();
    renderWithI18n(
      <StrategySelector
        strategies={mockStrategies}
        selectedStrategy=""
        onStrategyChange={handleChange}
        variant="cards"
      />
    );

    expect(screen.getByText('FloorStrategy')).toBeInTheDocument();
    expect(screen.getByText('MACrossoverStrategy')).toBeInTheDocument();
    expect(screen.getByText('RSIStrategy')).toBeInTheDocument();
  });

  it('does not call onStrategyChange when disabled card is clicked', () => {
    const handleChange = vi.fn();
    renderWithI18n(
      <StrategySelector
        strategies={mockStrategies}
        selectedStrategy=""
        onStrategyChange={handleChange}
        variant="cards"
        disabled={true}
      />
    );

    const card = screen.getByText('Floor Strategy').closest('button');
    if (card) {
      fireEvent.click(card);
    }

    expect(handleChange).not.toHaveBeenCalled();
  });
});
