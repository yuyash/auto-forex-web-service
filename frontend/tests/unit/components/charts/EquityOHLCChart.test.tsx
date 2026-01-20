/**
 * EquityOHLCChart Component Tests
 *
 * Tests for the EquityOHLCChart component using MUI X Charts
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from '@mui/material/styles';
import theme from '../../../../src/theme/theme';
import {
  EquityOHLCChart,
  type OHLCDataPoint,
} from '../../../../src/components/charts/EquityOHLCChart';

// Helper to wrap component with theme
const renderWithTheme = (component: React.ReactElement) => {
  return render(<ThemeProvider theme={theme}>{component}</ThemeProvider>);
};

// Sample OHLC data
const sampleData: OHLCDataPoint[] = [
  {
    timestamp: '2024-01-01T10:00:00Z',
    open: 100,
    high: 105,
    low: 98,
    close: 103,
  },
  {
    timestamp: '2024-01-01T10:01:00Z',
    open: 103,
    high: 108,
    low: 102,
    close: 106,
  },
  {
    timestamp: '2024-01-01T10:02:00Z',
    open: 106,
    high: 110,
    low: 104,
    close: 108,
  },
  {
    timestamp: '2024-01-01T10:03:00Z',
    open: 108,
    high: 112,
    low: 107,
    close: 110,
  },
  {
    timestamp: '2024-01-01T10:04:00Z',
    open: 110,
    high: 115,
    low: 109,
    close: 113,
  },
];

describe('EquityOHLCChart', () => {
  describe('Rendering', () => {
    it('should render with data', () => {
      renderWithTheme(<EquityOHLCChart data={sampleData} />);

      // Check for title
      expect(screen.getByText('Equity Curve')).toBeInTheDocument();

      // Check for granularity selector
      expect(screen.getByLabelText(/granularity/i)).toBeInTheDocument();

      // Check for data summary
      expect(screen.getByText(/Data Points: 5/i)).toBeInTheDocument();
    });

    it('should render with custom title', () => {
      renderWithTheme(
        <EquityOHLCChart data={sampleData} title="Custom Equity Chart" />
      );

      expect(screen.getByText('Custom Equity Chart')).toBeInTheDocument();
    });

    it('should render without granularity selector when disabled', () => {
      renderWithTheme(
        <EquityOHLCChart data={sampleData} showGranularitySelector={false} />
      );

      expect(screen.queryByLabelText(/granularity/i)).not.toBeInTheDocument();
    });

    it('should display data statistics', () => {
      renderWithTheme(<EquityOHLCChart data={sampleData} />);

      // Check for latest value
      expect(screen.getByText(/Latest: 113\.00/i)).toBeInTheDocument();

      // Check for high value
      expect(screen.getByText(/High: 115\.00/i)).toBeInTheDocument();

      // Check for low value
      expect(screen.getByText(/Low: 98\.00/i)).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('should show loading spinner when loading', () => {
      renderWithTheme(<EquityOHLCChart data={[]} loading={true} />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('should not show chart when loading', () => {
      renderWithTheme(<EquityOHLCChart data={sampleData} loading={true} />);

      expect(screen.queryByText('Equity Curve')).not.toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should show error message when error prop is provided', () => {
      renderWithTheme(
        <EquityOHLCChart data={[]} error="Failed to load data" />
      );

      expect(screen.getByText('Failed to load data')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('should not show chart when error is present', () => {
      renderWithTheme(
        <EquityOHLCChart data={sampleData} error="Error occurred" />
      );

      expect(screen.queryByText('Equity Curve')).not.toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('should show empty state message when no data', () => {
      renderWithTheme(<EquityOHLCChart data={[]} />);

      expect(screen.getByText('No equity data available')).toBeInTheDocument();
    });

    it('should not show chart when data is empty', () => {
      renderWithTheme(<EquityOHLCChart data={[]} />);

      expect(screen.queryByText('Equity Curve')).not.toBeInTheDocument();
    });
  });

  describe('Granularity Selector', () => {
    it('should have default granularity selected', () => {
      renderWithTheme(<EquityOHLCChart data={sampleData} />);

      const select = screen.getByLabelText(/granularity/i);
      expect(select).toHaveTextContent('1 Minute');
    });

    it('should use initial granularity prop', () => {
      renderWithTheme(
        <EquityOHLCChart data={sampleData} initialGranularity={300} />
      );

      const select = screen.getByLabelText(/granularity/i);
      expect(select).toHaveTextContent('5 Minutes');
    });

    it('should call onGranularityChange when granularity changes', async () => {
      const user = userEvent.setup();
      const handleChange = vi.fn();

      renderWithTheme(
        <EquityOHLCChart data={sampleData} onGranularityChange={handleChange} />
      );

      // Open the select
      const select = screen.getByLabelText(/granularity/i);
      await user.click(select);

      // Select a different granularity
      const option = screen.getByRole('option', { name: '5 Minutes' });
      await user.click(option);

      expect(handleChange).toHaveBeenCalledWith(300);
    });

    it('should have all granularity options available', async () => {
      const user = userEvent.setup();

      renderWithTheme(<EquityOHLCChart data={sampleData} />);

      // Open the select
      const select = screen.getByLabelText(/granularity/i);
      await user.click(select);

      // Check for some key options
      expect(
        screen.getByRole('option', { name: '1 Second' })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('option', { name: '1 Minute' })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('option', { name: '1 Hour' })
      ).toBeInTheDocument();
      expect(screen.getByRole('option', { name: '1 Day' })).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have accessible chart label', () => {
      renderWithTheme(<EquityOHLCChart data={sampleData} />);

      // MUI X Charts should have aria-label
      const chart = screen.getByLabelText(
        /Equity Curve showing equity curve with OHLC data/i
      );
      expect(chart).toBeInTheDocument();
    });

    it('should have accessible granularity selector', () => {
      renderWithTheme(<EquityOHLCChart data={sampleData} />);

      const select = screen.getByLabelText(
        /Select time granularity for chart/i
      );
      expect(select).toBeInTheDocument();
    });
  });

  describe('Responsive Behavior', () => {
    it('should render with custom height', () => {
      const { container } = renderWithTheme(
        <EquityOHLCChart data={sampleData} height={600} />
      );

      // Check that the chart container has the correct height
      const chartBox = container.querySelector('[style*="height"]');
      expect(chartBox).toBeInTheDocument();
    });

    it('should render with default height when not specified', () => {
      const { container } = renderWithTheme(
        <EquityOHLCChart data={sampleData} />
      );

      // Chart should render with default height
      const chartBox = container.querySelector('[style*="height"]');
      expect(chartBox).toBeInTheDocument();
    });
  });

  describe('Data Transformation', () => {
    it('should handle data with volume', () => {
      const dataWithVolume: OHLCDataPoint[] = [
        {
          timestamp: '2024-01-01T10:00:00Z',
          open: 100,
          high: 105,
          low: 98,
          close: 103,
          volume: 1000,
        },
      ];

      renderWithTheme(<EquityOHLCChart data={dataWithVolume} />);

      expect(screen.getByText('Equity Curve')).toBeInTheDocument();
    });

    it('should handle data without volume', () => {
      renderWithTheme(<EquityOHLCChart data={sampleData} />);

      expect(screen.getByText('Equity Curve')).toBeInTheDocument();
    });

    it('should correctly calculate statistics', () => {
      renderWithTheme(<EquityOHLCChart data={sampleData} />);

      // Latest should be the close of the last data point
      expect(screen.getByText(/Latest: 113\.00/i)).toBeInTheDocument();

      // High should be the maximum high across all data points
      expect(screen.getByText(/High: 115\.00/i)).toBeInTheDocument();

      // Low should be the minimum low across all data points
      expect(screen.getByText(/Low: 98\.00/i)).toBeInTheDocument();
    });
  });
});
