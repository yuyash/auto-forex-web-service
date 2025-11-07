import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChartControls from '../components/chart/ChartControls';
import type { Granularity } from '../types/chart';

describe('ChartControls', () => {
  const defaultProps = {
    instrument: 'EUR_USD',
    granularity: 'H1' as Granularity,
    onInstrumentChange: vi.fn(),
    onGranularityChange: vi.fn(),
  };

  it('renders all control selectors', () => {
    render(<ChartControls {...defaultProps} />);

    expect(screen.getByLabelText(/currency pair/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/timeframe/i)).toBeInTheDocument();
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
