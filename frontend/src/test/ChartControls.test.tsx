import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChartControls from '../components/chart/ChartControls';
import type { Granularity } from '../types/chart';
import type { ChartType, Indicator } from '../components/chart/ChartControls';

describe('ChartControls', () => {
  const defaultProps = {
    instrument: 'EUR_USD',
    granularity: 'H1' as Granularity,
    chartType: 'Candlestick' as ChartType,
    indicators: [] as Indicator[],
    onInstrumentChange: vi.fn(),
    onGranularityChange: vi.fn(),
    onChartTypeChange: vi.fn(),
    onIndicatorsChange: vi.fn(),
  };

  it('renders all control selectors', () => {
    render(<ChartControls {...defaultProps} />);

    expect(screen.getByLabelText(/currency pair/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/timeframe/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/chart type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/indicators/i)).toBeInTheDocument();
  });

  it('displays current instrument value', () => {
    render(<ChartControls {...defaultProps} />);

    const instrumentSelect = screen.getByLabelText(/currency pair/i);
    expect(instrumentSelect).toHaveTextContent('EUR/USD');
  });

  it('displays current granularity value', () => {
    render(<ChartControls {...defaultProps} />);

    const granularitySelect = screen.getByLabelText(/timeframe/i);
    expect(granularitySelect).toHaveTextContent('1 Hour');
  });

  it('displays current chart type value', () => {
    render(<ChartControls {...defaultProps} />);

    const chartTypeSelect = screen.getByLabelText(/chart type/i);
    expect(chartTypeSelect).toHaveTextContent('Candlestick');
  });

  it('calls onInstrumentChange when currency pair is changed', async () => {
    const user = userEvent.setup();
    const onInstrumentChange = vi.fn();

    render(
      <ChartControls
        {...defaultProps}
        onInstrumentChange={onInstrumentChange}
      />
    );

    const instrumentSelect = screen.getByLabelText(/currency pair/i);
    await user.click(instrumentSelect);

    const gbpUsdOption = screen.getByRole('option', { name: /GBP\/USD/i });
    await user.click(gbpUsdOption);

    expect(onInstrumentChange).toHaveBeenCalledWith('GBP_USD');
  });

  it('calls onGranularityChange when timeframe is changed', async () => {
    const user = userEvent.setup();
    const onGranularityChange = vi.fn();

    render(
      <ChartControls
        {...defaultProps}
        onGranularityChange={onGranularityChange}
      />
    );

    const granularitySelect = screen.getByLabelText(/timeframe/i);
    await user.click(granularitySelect);

    const m5Option = screen.getByRole('option', { name: /^5 Minutes$/i });
    await user.click(m5Option);

    expect(onGranularityChange).toHaveBeenCalledWith('M5');
  });

  it('calls onChartTypeChange when chart type is changed', async () => {
    const user = userEvent.setup();
    const onChartTypeChange = vi.fn();

    render(
      <ChartControls {...defaultProps} onChartTypeChange={onChartTypeChange} />
    );

    const chartTypeSelect = screen.getByLabelText(/chart type/i);
    await user.click(chartTypeSelect);

    const lineOption = screen.getByRole('option', { name: /Line/i });
    await user.click(lineOption);

    expect(onChartTypeChange).toHaveBeenCalledWith('Line');
  });

  it('calls onIndicatorsChange when indicators are selected', async () => {
    const user = userEvent.setup();
    const onIndicatorsChange = vi.fn();

    render(
      <ChartControls
        {...defaultProps}
        onIndicatorsChange={onIndicatorsChange}
      />
    );

    const indicatorsSelect = screen.getByLabelText(/indicators/i);
    await user.click(indicatorsSelect);

    const atrOption = screen.getByRole('option', { name: /ATR/i });
    await user.click(atrOption);

    expect(onIndicatorsChange).toHaveBeenCalled();
  });

  it('displays all OANDA granularities', async () => {
    const user = userEvent.setup();
    render(<ChartControls {...defaultProps} />);

    const granularitySelect = screen.getByLabelText(/timeframe/i);
    await user.click(granularitySelect);

    // Check for some key granularities
    expect(
      screen.getByRole('option', { name: /^5 Seconds$/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: /^1 Minute$/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: /^1 Hour$/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: /^Daily$/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: /^Weekly$/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: /^Monthly$/i })
    ).toBeInTheDocument();
  });

  it('displays all chart types', async () => {
    const user = userEvent.setup();
    render(<ChartControls {...defaultProps} />);

    const chartTypeSelect = screen.getByLabelText(/chart type/i);
    await user.click(chartTypeSelect);

    expect(
      screen.getByRole('option', { name: /Candlestick/i })
    ).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Line/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Bar/i })).toBeInTheDocument();
  });

  it('displays all indicators', async () => {
    const user = userEvent.setup();
    render(<ChartControls {...defaultProps} />);

    const indicatorsSelect = screen.getByLabelText(/indicators/i);
    await user.click(indicatorsSelect);

    expect(screen.getByRole('option', { name: /ATR/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /MA/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /RSI/i })).toBeInTheDocument();
  });

  it('displays selected indicators', () => {
    render(<ChartControls {...defaultProps} indicators={['ATR', 'RSI']} />);

    const indicatorsSelect = screen.getByLabelText(/indicators/i);
    expect(indicatorsSelect).toHaveTextContent('ATR, RSI');
  });
});
