import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '../i18n/config';
import StrategyStatus from '../components/strategy/StrategyStatus';
import type { StrategyStatus as StrategyStatusType } from '../types/strategy';
import type { Position } from '../types/position';

const mockInactiveStatus: StrategyStatusType = {
  is_active: false,
  strategy_type: null,
  config: null,
  instrument: [],
  state: null,
  created_at: null,
  updated_at: null,
};

const mockActiveStatus: StrategyStatusType = {
  is_active: true,
  strategy_type: 'floor',
  config: {
    base_lot_size: 1.0,
    retracement_lot_mode: 'additive',
  },
  instrument: 'EUR_USD',
  state: {
    status: 'trading',
    positions_count: 3,
    total_pnl: 250.75,
    last_tick_time: '2025-01-01T12:00:00Z',
  },
  created_at: '2025-01-01T10:00:00Z',
  updated_at: '2025-01-01T12:00:00Z',
};

const mockPausedStatus: StrategyStatusType = {
  ...mockActiveStatus,
  state: {
    status: 'paused',
    positions_count: 2,
    total_pnl: 100.0,
    last_tick_time: '2025-01-01T11:00:00Z',
  },
};

const mockErrorStatus: StrategyStatusType = {
  ...mockActiveStatus,
  state: {
    status: 'error',
    positions_count: 0,
    total_pnl: 0,
    last_tick_time: '2025-01-01T10:30:00Z',
  },
};

const mockPositions: Position[] = [
  {
    id: '1',
    position_id: 'P001',
    instrument: 'EUR_USD',
    direction: 'LONG',
    units: 10000,
    entry_price: 1.1234,
    current_price: 1.1254,
    unrealized_pnl: 200.0,
    status: 'OPEN',
    layer: 1,
    opened_at: '2025-01-01T10:00:00Z',
    closed_at: null,
    account: 1,
    user: 1,
    strategy: 'floor',
  },
  {
    id: '2',
    position_id: 'P002',
    instrument: 'GBP_USD',
    direction: 'SHORT',
    units: 5000,
    entry_price: 1.2567,
    current_price: 1.2557,
    unrealized_pnl: 50.0,
    status: 'OPEN',
    layer: 1,
    opened_at: '2025-01-01T10:30:00Z',
    closed_at: null,
    account: 1,
    user: 1,
    strategy: 'floor',
  },
  {
    id: '3',
    position_id: 'P003',
    instrument: 'EUR_USD',
    direction: 'LONG',
    units: 15000,
    entry_price: 1.1244,
    current_price: 1.1244,
    unrealized_pnl: 0.75,
    status: 'OPEN',
    layer: 2,
    opened_at: '2025-01-01T11:00:00Z',
    closed_at: null,
    account: 1,
    user: 1,
    strategy: 'floor',
  },
  {
    id: '4',
    position_id: 'P004',
    instrument: 'EUR_USD',
    direction: 'LONG',
    units: 10000,
    entry_price: 1.12,
    current_price: 1.118,
    unrealized_pnl: -200.0,
    status: 'CLOSED',
    layer: 1,
    opened_at: '2025-01-01T09:00:00Z',
    closed_at: '2025-01-01T09:30:00Z',
    account: 1,
    user: 1,
    strategy: 'floor',
  },
];

const renderWithI18n = (component: React.ReactElement) => {
  return render(<I18nextProvider i18n={i18n}>{component}</I18nextProvider>);
};

describe('StrategyStatus', () => {
  describe('Component Rendering', () => {
    it('renders strategy status title', () => {
      renderWithI18n(
        <StrategyStatus strategyStatus={mockActiveStatus} positions={[]} />
      );

      expect(screen.getByText(/strategy status/i)).toBeInTheDocument();
    });

    it('shows loading state when loading prop is true', () => {
      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={[]}
          loading={true}
        />
      );

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('shows no strategy message when strategyStatus is null', () => {
      renderWithI18n(<StrategyStatus strategyStatus={null} positions={[]} />);

      expect(screen.getByText(/no strategy configured/i)).toBeInTheDocument();
    });
  });

  describe('Status Display', () => {
    it('displays idle status when strategy is inactive', () => {
      renderWithI18n(
        <StrategyStatus strategyStatus={mockInactiveStatus} positions={[]} />
      );

      expect(screen.getByText(/idle/i)).toBeInTheDocument();
      expect(screen.getByText(/strategy is not active/i)).toBeInTheDocument();
    });

    it('displays trading status when strategy is active and trading', () => {
      renderWithI18n(
        <StrategyStatus strategyStatus={mockActiveStatus} positions={[]} />
      );

      expect(screen.getByText(/trading/i)).toBeInTheDocument();
      expect(
        screen.getByText(/strategy is currently active/i)
      ).toBeInTheDocument();
    });

    it('displays paused status when strategy is paused', () => {
      renderWithI18n(
        <StrategyStatus strategyStatus={mockPausedStatus} positions={[]} />
      );

      expect(screen.getByText(/paused/i)).toBeInTheDocument();
    });

    it('displays error status when strategy has error', () => {
      renderWithI18n(
        <StrategyStatus strategyStatus={mockErrorStatus} positions={[]} />
      );

      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });

    it('displays strategy type when active', () => {
      renderWithI18n(
        <StrategyStatus strategyStatus={mockActiveStatus} positions={[]} />
      );

      expect(screen.getByText(/type: floor/i)).toBeInTheDocument();
    });
  });

  describe('Performance Metrics', () => {
    it('displays total P&L from positions', () => {
      const openPositions = mockPositions.filter((p) => p.status === 'OPEN');
      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={openPositions}
        />
      );

      // Total P&L: 200 + 50 + 0.75 = 250.75
      expect(screen.getByText(/\$250\.75/)).toBeInTheDocument();
    });

    it('displays negative P&L correctly', () => {
      const negativePositions: Position[] = [
        {
          ...mockPositions[0],
          unrealized_pnl: -150.5,
        },
      ];

      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={negativePositions}
        />
      );

      expect(screen.getAllByText(/-\$150\.50/)[0]).toBeInTheDocument();
    });

    it('displays open positions count', () => {
      const openPositions = mockPositions.filter((p) => p.status === 'OPEN');
      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={openPositions}
        />
      );

      expect(screen.getByText(/open positions/i)).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('displays active layers count', () => {
      const openPositions = mockPositions.filter((p) => p.status === 'OPEN');
      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={openPositions}
        />
      );

      expect(screen.getAllByText(/active layers/i)[0]).toBeInTheDocument();
      // Layers 1 and 2 are active
      expect(screen.getAllByText('2')[0]).toBeInTheDocument();
    });

    it('displays total units', () => {
      const openPositions = mockPositions.filter((p) => p.status === 'OPEN');
      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={openPositions}
        />
      );

      expect(screen.getByText(/total units/i)).toBeInTheDocument();
      // Total: 10000 + 5000 + 15000 = 30000
      expect(screen.getByText('30000')).toBeInTheDocument();
    });
  });

  describe('Position Breakdown', () => {
    it('displays long positions count', () => {
      const openPositions = mockPositions.filter((p) => p.status === 'OPEN');
      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={openPositions}
        />
      );

      expect(screen.getByText(/long/i)).toBeInTheDocument();
      // 2 long positions (P001, P003)
      expect(screen.getAllByText('2')[0]).toBeInTheDocument();
    });

    it('displays short positions count', () => {
      const openPositions = mockPositions.filter((p) => p.status === 'OPEN');
      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={openPositions}
        />
      );

      expect(screen.getByText(/short/i)).toBeInTheDocument();
      // 1 short position (P002)
      expect(screen.getByText('1')).toBeInTheDocument();
    });

    it('displays average entry price', () => {
      const openPositions = mockPositions.filter((p) => p.status === 'OPEN');
      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={openPositions}
        />
      );

      expect(screen.getByText(/avg entry/i)).toBeInTheDocument();
      // Weighted average: (1.1234*10000 + 1.2567*5000 + 1.1244*15000) / 30000
      // = (11234 + 6283.5 + 16866) / 30000 = 34383.5 / 30000 = 1.14612
      expect(screen.getByText(/1\.14612/)).toBeInTheDocument();
    });
  });

  describe('Active Layers Display', () => {
    it('displays active layers with P&L', () => {
      const openPositions = mockPositions.filter((p) => p.status === 'OPEN');
      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={openPositions}
        />
      );

      expect(screen.getAllByText(/active layers/i)[0]).toBeInTheDocument();
      // Layer 1: 200 + 50 = 250
      expect(screen.getByText(/layer 1: \$250\.00/i)).toBeInTheDocument();
      // Layer 2: 0.75
      expect(screen.getByText(/layer 2: \$0\.75/i)).toBeInTheDocument();
    });

    it('does not display layers section when no layers exist', () => {
      const positionsWithoutLayers: Position[] = [
        {
          ...mockPositions[0],
          layer: undefined,
        },
      ];

      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={positionsWithoutLayers}
        />
      );

      // Should not show "Active Layers" title
      const layersTitles = screen.queryAllByText(/active layers/i);
      // Only one instance should exist (in the metrics section)
      expect(layersTitles.length).toBe(1);
    });

    it('sorts layers in ascending order', () => {
      const openPositions = mockPositions.filter((p) => p.status === 'OPEN');
      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={openPositions}
        />
      );

      const layerChips = screen.getAllByText(/layer \d+:/i);
      expect(layerChips[0]).toHaveTextContent('Layer 1');
      expect(layerChips[1]).toHaveTextContent('Layer 2');
    });
  });

  describe('Last Update Time', () => {
    it('displays last update time when available', () => {
      renderWithI18n(
        <StrategyStatus strategyStatus={mockActiveStatus} positions={[]} />
      );

      expect(screen.getByText(/last update/i)).toBeInTheDocument();
      // Check that a date is displayed (format may vary by locale)
      expect(screen.getByText(/2025/)).toBeInTheDocument();
    });

    it('does not display last update time when not available', () => {
      const statusWithoutTime: StrategyStatusType = {
        ...mockActiveStatus,
        state: {
          ...mockActiveStatus.state!,
          last_tick_time: null,
        },
      };

      renderWithI18n(
        <StrategyStatus strategyStatus={statusWithoutTime} positions={[]} />
      );

      expect(screen.queryByText(/last update/i)).not.toBeInTheDocument();
    });
  });

  describe('Empty States', () => {
    it('handles empty positions array', () => {
      renderWithI18n(
        <StrategyStatus strategyStatus={mockActiveStatus} positions={[]} />
      );

      expect(screen.getByText(/\$0\.00/)).toBeInTheDocument();
      expect(screen.getAllByText('0')[0]).toBeInTheDocument();
    });

    it('handles positions without layers', () => {
      const positionsWithoutLayers: Position[] = [
        {
          ...mockPositions[0],
          layer: undefined,
        },
      ];

      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={positionsWithoutLayers}
        />
      );

      // Should show 0 active layers
      const metricsSection = screen.getByText(/active layers/i).closest('div');
      expect(metricsSection).toHaveTextContent('0');
    });
  });

  describe('Real-time Updates', () => {
    it('recalculates metrics when positions change', () => {
      const { rerender } = renderWithI18n(
        <StrategyStatus strategyStatus={mockActiveStatus} positions={[]} />
      );

      expect(screen.getByText(/\$0\.00/)).toBeInTheDocument();

      const openPositions = mockPositions.filter((p) => p.status === 'OPEN');
      rerender(
        <I18nextProvider i18n={i18n}>
          <StrategyStatus
            strategyStatus={mockActiveStatus}
            positions={openPositions}
          />
        </I18nextProvider>
      );

      expect(screen.getByText(/\$250\.75/)).toBeInTheDocument();
    });

    it('updates status when strategy status changes', () => {
      const { rerender } = renderWithI18n(
        <StrategyStatus strategyStatus={mockActiveStatus} positions={[]} />
      );

      expect(screen.getByText(/trading/i)).toBeInTheDocument();

      rerender(
        <I18nextProvider i18n={i18n}>
          <StrategyStatus strategyStatus={mockPausedStatus} positions={[]} />
        </I18nextProvider>
      );

      expect(screen.getByText(/paused/i)).toBeInTheDocument();
    });
  });

  describe('Currency Formatting', () => {
    it('formats positive P&L with dollar sign', () => {
      const openPositions = mockPositions.filter((p) => p.status === 'OPEN');
      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={openPositions}
        />
      );

      expect(screen.getByText(/\$250\.75/)).toBeInTheDocument();
    });

    it('formats negative P&L with dollar sign and minus', () => {
      const negativePositions: Position[] = [
        {
          ...mockPositions[0],
          unrealized_pnl: -100.5,
        },
      ];

      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={negativePositions}
        />
      );

      expect(screen.getAllByText(/-\$100\.50/)[0]).toBeInTheDocument();
    });

    it('formats zero P&L correctly', () => {
      const zeroPositions: Position[] = [
        {
          ...mockPositions[0],
          unrealized_pnl: 0,
        },
      ];

      renderWithI18n(
        <StrategyStatus
          strategyStatus={mockActiveStatus}
          positions={zeroPositions}
        />
      );

      expect(screen.getAllByText(/\$0\.00/)[0]).toBeInTheDocument();
    });
  });
});
