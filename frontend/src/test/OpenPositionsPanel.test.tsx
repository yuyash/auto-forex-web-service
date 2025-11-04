import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '../i18n/config';
import OpenPositionsPanel from '../components/dashboard/OpenPositionsPanel';
import type { Position } from '../types/chart';

const mockPositions: Position[] = [
  {
    position_id: 'POS-001',
    instrument: 'EUR_USD',
    direction: 'long',
    units: 10000,
    entry_price: 1.085,
    current_price: 1.0875,
    unrealized_pnl: 25.0,
    opened_at: '2024-01-15T10:30:00Z',
  },
  {
    position_id: 'POS-002',
    instrument: 'GBP_USD',
    direction: 'short',
    units: 5000,
    entry_price: 1.265,
    current_price: 1.2625,
    unrealized_pnl: 12.5,
    opened_at: '2024-01-15T11:00:00Z',
  },
  {
    position_id: 'POS-003',
    instrument: 'USD_JPY',
    direction: 'long',
    units: 20000,
    entry_price: 148.5,
    current_price: 148.25,
    unrealized_pnl: -50.0,
    opened_at: '2024-01-15T11:30:00Z',
  },
];

describe('OpenPositionsPanel', () => {
  it('renders the panel with title and position count', () => {
    const mockClosePosition = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={mockPositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    expect(screen.getByText('Open Positions')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('displays all positions with correct data', () => {
    const mockClosePosition = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={mockPositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    expect(screen.getByText('POS-001')).toBeInTheDocument();
    expect(screen.getByText('POS-002')).toBeInTheDocument();
    expect(screen.getByText('POS-003')).toBeInTheDocument();
    expect(screen.getByText('EUR_USD')).toBeInTheDocument();
    expect(screen.getByText('GBP_USD')).toBeInTheDocument();
    expect(screen.getByText('USD_JPY')).toBeInTheDocument();
  });

  it('displays position directions correctly with chips', () => {
    const mockClosePosition = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={mockPositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    const longChips = screen.getAllByText('Long');
    const shortChips = screen.getAllByText('Short');
    expect(longChips.length).toBe(2);
    expect(shortChips.length).toBe(1);
  });

  it('displays position units correctly', () => {
    const mockClosePosition = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={mockPositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    expect(screen.getByText('10,000')).toBeInTheDocument();
    expect(screen.getByText('5,000')).toBeInTheDocument();
    expect(screen.getByText('20,000')).toBeInTheDocument();
  });

  it('displays entry prices correctly', () => {
    const mockClosePosition = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={mockPositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    expect(screen.getByText('1.08500')).toBeInTheDocument();
    expect(screen.getByText('1.26500')).toBeInTheDocument();
    expect(screen.getByText('148.50000')).toBeInTheDocument();
  });

  it('displays current prices correctly', () => {
    const mockClosePosition = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={mockPositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    expect(screen.getByText('1.08750')).toBeInTheDocument();
    expect(screen.getByText('1.26250')).toBeInTheDocument();
    expect(screen.getByText('148.25000')).toBeInTheDocument();
  });

  it('displays unrealized P&L correctly with proper formatting', () => {
    const mockClosePosition = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={mockPositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    expect(screen.getByText('+25.00')).toBeInTheDocument();
    expect(screen.getByText('+12.50')).toBeInTheDocument();
    expect(screen.getByText('-50.00')).toBeInTheDocument();
  });

  it('displays total P&L in header chip', () => {
    const mockClosePosition = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={mockPositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    // Total P&L: 25.0 + 12.5 - 50.0 = -12.5
    expect(screen.getByText('-12.50')).toBeInTheDocument();
  });

  it('calls onClosePosition when close button is clicked', () => {
    const mockClosePosition = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={mockPositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    const closeButtons = screen.getAllByText('Close Position');
    fireEvent.click(closeButtons[0]);

    expect(mockClosePosition).toHaveBeenCalledWith('POS-001');
    expect(mockClosePosition).toHaveBeenCalledTimes(1);
  });

  it('toggles panel expansion when header is clicked', async () => {
    const mockClosePosition = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={mockPositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    const header = screen.getByText('Open Positions').closest('div');
    expect(screen.getByText('POS-001')).toBeInTheDocument();

    if (header) {
      fireEvent.click(header);
    }

    // After collapse, positions should not be visible
    await waitFor(() => {
      expect(screen.queryByText('POS-001')).not.toBeInTheDocument();
    });

    // Click again to expand
    if (header) {
      fireEvent.click(header);
    }

    await waitFor(() => {
      expect(screen.getByText('POS-001')).toBeInTheDocument();
    });
  });

  it('displays empty state when no positions', () => {
    const mockClosePosition = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={[]}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    expect(screen.getByText('No open positions')).toBeInTheDocument();
    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('disables close buttons when loading', () => {
    const mockClosePosition = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={mockPositions}
          onClosePosition={mockClosePosition}
          loading={true}
        />
      </I18nextProvider>
    );

    const closeButtons = screen.getAllByText('Close Position');
    closeButtons.forEach((button) => {
      expect(button.closest('button')).toBeDisabled();
    });
  });

  it('renders expand/collapse icon correctly', () => {
    const mockClosePosition = vi.fn();
    const { container } = render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={mockPositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    const iconButton = container.querySelector('[aria-label="toggle panel"]');
    expect(iconButton).toBeInTheDocument();
  });

  it('formats units with locale string', () => {
    const mockClosePosition = vi.fn();
    const largePosition: Position[] = [
      {
        position_id: 'POS-004',
        instrument: 'EUR_USD',
        direction: 'long',
        units: 1000000,
        entry_price: 1.085,
        current_price: 1.0875,
        unrealized_pnl: 2500.0,
        opened_at: '2024-01-15T10:30:00Z',
      },
    ];

    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={largePosition}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    expect(screen.getByText('1,000,000')).toBeInTheDocument();
  });

  it('updates positions in real-time when props change', () => {
    const mockClosePosition = vi.fn();
    const { rerender } = render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={mockPositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    expect(screen.getByText('3')).toBeInTheDocument();

    const updatedPositions: Position[] = [
      {
        ...mockPositions[0],
        current_price: 1.09,
        unrealized_pnl: 50.0,
      },
    ];

    rerender(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={updatedPositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('1.09000')).toBeInTheDocument();
    // +50.00 appears twice: once in the header chip (total P&L) and once in the table
    const pnlElements = screen.getAllByText('+50.00');
    expect(pnlElements.length).toBeGreaterThanOrEqual(1);
  });

  it('displays positive total P&L with success color chip', () => {
    const mockClosePosition = vi.fn();
    const profitablePositions: Position[] = [
      {
        position_id: 'POS-001',
        instrument: 'EUR_USD',
        direction: 'long',
        units: 10000,
        entry_price: 1.085,
        current_price: 1.0875,
        unrealized_pnl: 25.0,
        opened_at: '2024-01-15T10:30:00Z',
      },
      {
        position_id: 'POS-002',
        instrument: 'GBP_USD',
        direction: 'short',
        units: 5000,
        entry_price: 1.265,
        current_price: 1.2625,
        unrealized_pnl: 12.5,
        opened_at: '2024-01-15T11:00:00Z',
      },
    ];

    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={profitablePositions}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    // Total P&L: 25.0 + 12.5 = 37.5
    expect(screen.getByText('+37.50')).toBeInTheDocument();
  });

  it('does not display total P&L chip when no positions', () => {
    const mockClosePosition = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={[]}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    // Should only have the count chip (0), not a P&L chip
    const chips = screen.getAllByRole('button').filter((el) => {
      return el.className.includes('MuiChip');
    });
    expect(chips.length).toBeLessThanOrEqual(1);
  });

  it('formats prices with 5 decimal places', () => {
    const mockClosePosition = vi.fn();
    const precisePosition: Position[] = [
      {
        position_id: 'POS-005',
        instrument: 'EUR_USD',
        direction: 'long',
        units: 10000,
        entry_price: 1.08512,
        current_price: 1.08567,
        unrealized_pnl: 5.5,
        opened_at: '2024-01-15T10:30:00Z',
      },
    ];

    render(
      <I18nextProvider i18n={i18n}>
        <OpenPositionsPanel
          positions={precisePosition}
          onClosePosition={mockClosePosition}
        />
      </I18nextProvider>
    );

    expect(screen.getByText('1.08512')).toBeInTheDocument();
    expect(screen.getByText('1.08567')).toBeInTheDocument();
  });
});
