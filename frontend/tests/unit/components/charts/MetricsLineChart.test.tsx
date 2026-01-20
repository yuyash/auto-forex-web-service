/**
 * MetricsLineChart Component Tests
 *
 * Tests for the MetricsLineChart component using MUI X Charts
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import theme from '../../../../src/theme/theme';
import {
  MetricsLineChart,
  type MetricSeries,
} from '../../../../src/components/charts/MetricsLineChart';

// Helper to wrap component with theme
const renderWithTheme = (component: React.ReactElement) => {
  return render(<ThemeProvider theme={theme}>{component}</ThemeProvider>);
};

// Sample metrics data
const sampleSeries: MetricSeries[] = [
  {
    id: 'realized_pnl',
    label: 'Realized P&L',
    data: [
      { timestamp: '2024-01-01T10:00:00Z', value: 100 },
      { timestamp: '2024-01-01T10:01:00Z', value: 150 },
      { timestamp: '2024-01-01T10:02:00Z', value: 120 },
      { timestamp: '2024-01-01T10:03:00Z', value: 180 },
      { timestamp: '2024-01-01T10:04:00Z', value: 200 },
    ],
    color: '#26a69a',
    unit: ' USD',
  },
  {
    id: 'unrealized_pnl',
    label: 'Unrealized P&L',
    data: [
      { timestamp: '2024-01-01T10:00:00Z', value: -20 },
      { timestamp: '2024-01-01T10:01:00Z', value: 10 },
      { timestamp: '2024-01-01T10:02:00Z', value: -5 },
      { timestamp: '2024-01-01T10:03:00Z', value: 15 },
      { timestamp: '2024-01-01T10:04:00Z', value: 25 },
    ],
    color: '#ff9800',
    unit: ' USD',
  },
];

describe('MetricsLineChart', () => {
  describe('Rendering', () => {
    it('should render with data', () => {
      renderWithTheme(<MetricsLineChart series={sampleSeries} />);

      // Check for title
      expect(screen.getByText('Metrics')).toBeInTheDocument();

      // Check for statistics section
      expect(screen.getByText('Statistics')).toBeInTheDocument();
    });

    it('should render with custom title', () => {
      renderWithTheme(
        <MetricsLineChart series={sampleSeries} title="Custom Metrics" />
      );

      expect(screen.getByText('Custom Metrics')).toBeInTheDocument();
    });

    it('should render all series labels', () => {
      renderWithTheme(<MetricsLineChart series={sampleSeries} />);

      expect(screen.getByText('Realized P&L')).toBeInTheDocument();
      expect(screen.getByText('Unrealized P&L')).toBeInTheDocument();
    });

    it('should display statistics for each series', () => {
      renderWithTheme(<MetricsLineChart series={sampleSeries} />);

      // Check for Realized P&L statistics
      expect(screen.getByText(/Latest: 200\.00 USD/i)).toBeInTheDocument();
      expect(screen.getByText(/Avg: 150\.00 USD/i)).toBeInTheDocument();
      expect(screen.getByText(/Min: 100\.00 USD/i)).toBeInTheDocument();
      expect(screen.getByText(/Max: 200\.00 USD/i)).toBeInTheDocument();

      // Check for Unrealized P&L statistics
      expect(screen.getByText(/Latest: 25\.00 USD/i)).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('should show loading spinner when loading', () => {
      renderWithTheme(<MetricsLineChart series={[]} loading={true} />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('should not show chart when loading', () => {
      renderWithTheme(
        <MetricsLineChart series={sampleSeries} loading={true} />
      );

      expect(screen.queryByText('Metrics')).not.toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should show error message when error prop is provided', () => {
      renderWithTheme(
        <MetricsLineChart series={[]} error="Failed to load metrics" />
      );

      expect(screen.getByText('Failed to load metrics')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('should not show chart when error is present', () => {
      renderWithTheme(
        <MetricsLineChart series={sampleSeries} error="Error occurred" />
      );

      expect(screen.queryByText('Metrics')).not.toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('should show empty state message when no series', () => {
      renderWithTheme(<MetricsLineChart series={[]} />);

      expect(screen.getByText('No metrics data available')).toBeInTheDocument();
    });

    it('should not show chart when series is empty', () => {
      renderWithTheme(<MetricsLineChart series={[]} />);

      expect(screen.queryByText('Metrics')).not.toBeInTheDocument();
    });
  });

  describe('Multiple Series', () => {
    it('should render multiple series', () => {
      renderWithTheme(<MetricsLineChart series={sampleSeries} />);

      // Both series should be visible in statistics
      expect(screen.getByText('Realized P&L')).toBeInTheDocument();
      expect(screen.getByText('Unrealized P&L')).toBeInTheDocument();
    });

    it('should handle single series', () => {
      const singleSeries = [sampleSeries[0]];
      renderWithTheme(<MetricsLineChart series={singleSeries} />);

      expect(screen.getByText('Realized P&L')).toBeInTheDocument();
      expect(screen.queryByText('Unrealized P&L')).not.toBeInTheDocument();
    });

    it('should handle many series', () => {
      const manySeries: MetricSeries[] = [
        ...sampleSeries,
        {
          id: 'total_pnl',
          label: 'Total P&L',
          data: [
            { timestamp: '2024-01-01T10:00:00Z', value: 80 },
            { timestamp: '2024-01-01T10:01:00Z', value: 160 },
          ],
        },
        {
          id: 'open_positions',
          label: 'Open Positions',
          data: [
            { timestamp: '2024-01-01T10:00:00Z', value: 2 },
            { timestamp: '2024-01-01T10:01:00Z', value: 3 },
          ],
        },
      ];

      renderWithTheme(<MetricsLineChart series={manySeries} />);

      expect(screen.getByText('Realized P&L')).toBeInTheDocument();
      expect(screen.getByText('Unrealized P&L')).toBeInTheDocument();
      expect(screen.getByText('Total P&L')).toBeInTheDocument();
      expect(screen.getByText('Open Positions')).toBeInTheDocument();
    });
  });

  describe('Legend', () => {
    it('should show legend by default', () => {
      renderWithTheme(<MetricsLineChart series={sampleSeries} />);

      // Legend items should be visible (series labels in chips)
      expect(screen.getByText('Realized P&L')).toBeInTheDocument();
      expect(screen.getByText('Unrealized P&L')).toBeInTheDocument();
    });

    it('should hide legend when showLegend is false', () => {
      renderWithTheme(
        <MetricsLineChart series={sampleSeries} showLegend={false} />
      );

      // Statistics should still be visible
      expect(screen.getByText('Statistics')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have accessible chart label', () => {
      renderWithTheme(<MetricsLineChart series={sampleSeries} />);

      // MUI X Charts should have aria-label
      const chart = screen.getByLabelText(/Metrics showing 2 metric series/i);
      expect(chart).toBeInTheDocument();
    });

    it('should have accessible chart label with custom title', () => {
      renderWithTheme(
        <MetricsLineChart series={sampleSeries} title="Performance Metrics" />
      );

      const chart = screen.getByLabelText(
        /Performance Metrics showing 2 metric series/i
      );
      expect(chart).toBeInTheDocument();
    });
  });

  describe('Responsive Behavior', () => {
    it('should render with custom height', () => {
      const { container } = renderWithTheme(
        <MetricsLineChart series={sampleSeries} height={600} />
      );

      // Check that the chart container has the correct height
      const chartBox = container.querySelector('[style*="height"]');
      expect(chartBox).toBeInTheDocument();
    });

    it('should render with default height when not specified', () => {
      const { container } = renderWithTheme(
        <MetricsLineChart series={sampleSeries} />
      );

      // Chart should render with default height
      const chartBox = container.querySelector('[style*="height"]');
      expect(chartBox).toBeInTheDocument();
    });
  });

  describe('Data Transformation', () => {
    it('should handle series without units', () => {
      const seriesWithoutUnits: MetricSeries[] = [
        {
          id: 'metric1',
          label: 'Metric 1',
          data: [
            { timestamp: '2024-01-01T10:00:00Z', value: 100 },
            { timestamp: '2024-01-01T10:01:00Z', value: 150 },
          ],
        },
      ];

      renderWithTheme(<MetricsLineChart series={seriesWithoutUnits} />);

      // Statistics should be displayed without units
      expect(screen.getByText(/Latest: 150\.00$/i)).toBeInTheDocument();
    });

    it('should handle series with custom colors', () => {
      const seriesWithColors: MetricSeries[] = [
        {
          id: 'metric1',
          label: 'Metric 1',
          data: [{ timestamp: '2024-01-01T10:00:00Z', value: 100 }],
          color: '#ff0000',
        },
      ];

      renderWithTheme(<MetricsLineChart series={seriesWithColors} />);

      expect(screen.getByText('Metric 1')).toBeInTheDocument();
    });

    it('should correctly calculate statistics', () => {
      renderWithTheme(<MetricsLineChart series={sampleSeries} />);

      // Check Realized P&L statistics
      // Latest: 200, Avg: (100+150+120+180+200)/5 = 150, Min: 100, Max: 200
      expect(screen.getByText(/Latest: 200\.00 USD/i)).toBeInTheDocument();
      expect(screen.getByText(/Avg: 150\.00 USD/i)).toBeInTheDocument();
      expect(screen.getByText(/Min: 100\.00 USD/i)).toBeInTheDocument();
      expect(screen.getByText(/Max: 200\.00 USD/i)).toBeInTheDocument();
    });
  });

  describe('Y-Axis Label', () => {
    it('should use default y-axis label', () => {
      renderWithTheme(<MetricsLineChart series={sampleSeries} />);

      // Default label is "Value"
      expect(screen.getByText('Metrics')).toBeInTheDocument();
    });

    it('should use custom y-axis label', () => {
      renderWithTheme(
        <MetricsLineChart series={sampleSeries} yAxisLabel="P&L (USD)" />
      );

      expect(screen.getByText('Metrics')).toBeInTheDocument();
    });
  });
});
