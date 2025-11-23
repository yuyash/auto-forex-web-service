import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChartControls from '../components/chart/ChartControls';
import type { Granularity } from '../types/chart';

// Mock the useMarketConfig hooks
vi.mock('../hooks/useMarketConfig', () => ({
  useSupportedInstruments: () => ({
    instruments: [
      'EUR_USD',
      'GBP_USD',
      'USD_JPY',
      'USD_CHF',
      'AUD_USD',
      'USD_CAD',
      'NZD_USD',
    ],
    isLoading: false,
    error: null,
  }),
  useSupportedGranularities: () => ({
    granularities: [
      { value: 'S5', label: '5 Seconds' },
      { value: 'S10', label: '10 Seconds' },
      { value: 'S15', label: '15 Seconds' },
      { value: 'S30', label: '30 Seconds' },
      { value: 'M1', label: '1 Minute' },
      { value: 'M2', label: '2 Minutes' },
      { value: 'M4', label: '4 Minutes' },
      { value: 'M5', label: '5 Minutes' },
      { value: 'M10', label: '10 Minutes' },
      { value: 'M15', label: '15 Minutes' },
      { value: 'M30', label: '30 Minutes' },
      { value: 'H1', label: '1 Hour' },
      { value: 'H2', label: '2 Hours' },
      { value: 'H3', label: '3 Hours' },
      { value: 'H4', label: '4 Hours' },
      { value: 'H6', label: '6 Hours' },
      { value: 'H8', label: '8 Hours' },
      { value: 'H12', label: '12 Hours' },
      { value: 'D', label: 'Daily' },
      { value: 'W', label: 'Weekly' },
      { value: 'M', label: 'Monthly' },
    ],
    isLoading: false,
    error: null,
  }),
}));

describe('ChartControls', () => {
  const defaultProps = {
    instrument: 'EUR_USD',
    granularity: 'H1' as Granularity,
    onInstrumentChange: vi.fn(),
    onGranularityChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all control selectors', () => {
    render(<ChartControls {...defaultProps} />);

    expect(screen.getByLabelText(/currency pair/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/timeframe/i)).toBeInTheDocument();
  });

  it('does not render reset button by default', () => {
    render(<ChartControls {...defaultProps} />);

    expect(screen.queryByText(/^reset$/i)).not.toBeInTheDocument();
  });

  it('renders reset button when showResetButton is true', () => {
    render(
      <ChartControls
        {...defaultProps}
        showResetButton={true}
        onResetView={vi.fn()}
      />
    );

    expect(screen.getByText(/^reset$/i)).toBeInTheDocument();
  });

  it('calls onResetView when reset button is clicked', async () => {
    const user = userEvent.setup();
    const onResetView = vi.fn();

    render(
      <ChartControls
        {...defaultProps}
        showResetButton={true}
        onResetView={onResetView}
      />
    );

    const resetButton = screen.getByText(/^reset$/i);
    await user.click(resetButton);

    expect(onResetView).toHaveBeenCalledTimes(1);
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
});
