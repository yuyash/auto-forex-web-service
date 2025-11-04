import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import TradeLogTable from '../components/backtest/TradeLogTable';
import '../i18n/config';

interface MockColumn {
  id: string;
  label: string;
  render?: (row: Record<string, unknown>) => React.ReactNode;
}

interface MockDataTableProps {
  columns: MockColumn[];
  data: Record<string, unknown>[];
  emptyMessage: string;
}

// Mock the DataTable component
vi.mock('../components/common/DataTable', () => ({
  default: ({ columns, data, emptyMessage }: MockDataTableProps) => {
    if (data.length === 0) {
      return <div>{emptyMessage}</div>;
    }
    return (
      <table>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.id}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
            <tr key={idx}>
              {columns.map((col) => (
                <td key={col.id}>
                  {col.render ? col.render(row) : String(row[col.id] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    );
  },
}));

describe('TradeLogTable', () => {
  const mockTrades = [
    {
      timestamp: '2024-01-15T10:30:00Z',
      instrument: 'EUR_USD',
      direction: 'long',
      entry_price: 1.085,
      exit_price: 1.0875,
      units: 10000,
      pnl: 25.0,
      duration: 3600,
    },
    {
      timestamp: '2024-01-15T14:45:00Z',
      instrument: 'GBP_USD',
      direction: 'short',
      entry_price: 1.265,
      exit_price: 1.2625,
      units: 5000,
      pnl: 12.5,
      duration: 1800,
    },
    {
      timestamp: '2024-01-16T09:15:00Z',
      instrument: 'USD_JPY',
      direction: 'long',
      entry_price: 148.5,
      exit_price: 148.25,
      units: 8000,
      pnl: -20.0,
      duration: 7200,
    },
  ];

  it('renders trade log table with title', () => {
    render(<TradeLogTable trades={mockTrades} />);
    expect(screen.getByText('Trade Log')).toBeInTheDocument();
  });

  it('renders export CSV button', () => {
    render(<TradeLogTable trades={mockTrades} />);
    expect(screen.getByText('Export CSV')).toBeInTheDocument();
  });

  it('displays all column headers', () => {
    render(<TradeLogTable trades={mockTrades} />);
    expect(screen.getByText('Date')).toBeInTheDocument();
    expect(screen.getByText('Instrument')).toBeInTheDocument();
    expect(screen.getByText('Direction')).toBeInTheDocument();
    expect(screen.getByText('Entry Price')).toBeInTheDocument();
    expect(screen.getByText('Exit Price')).toBeInTheDocument();
    expect(screen.getByText('Units')).toBeInTheDocument();
    expect(screen.getByText('P&L')).toBeInTheDocument();
    expect(screen.getByText('Duration')).toBeInTheDocument();
  });

  it('displays trade data correctly', () => {
    render(<TradeLogTable trades={mockTrades} />);
    expect(screen.getByText('EUR_USD')).toBeInTheDocument();
    expect(screen.getByText('GBP_USD')).toBeInTheDocument();
    expect(screen.getByText('USD_JPY')).toBeInTheDocument();
  });

  it('shows empty message when no trades', () => {
    render(<TradeLogTable trades={[]} />);
    expect(
      screen.getByText(
        'No trades available. Run a backtest to see trade history.'
      )
    ).toBeInTheDocument();
  });

  it('disables export button when no trades', () => {
    render(<TradeLogTable trades={[]} />);
    const exportButton = screen.getByText('Export CSV').closest('button');
    expect(exportButton).toBeDisabled();
  });

  it('enables export button when trades exist', () => {
    render(<TradeLogTable trades={mockTrades} />);
    const exportButton = screen.getByText('Export CSV').closest('button');
    expect(exportButton).not.toBeDisabled();
  });

  it('exports trades to CSV when button clicked', () => {
    // Mock URL.createObjectURL
    const mockCreateObjectURL = vi.fn(() => 'blob:mock-url');
    (
      globalThis.URL as { createObjectURL: typeof URL.createObjectURL }
    ).createObjectURL = mockCreateObjectURL;

    // Mock document.createElement to return a proper link element
    const mockLink = document.createElement('a');
    const mockClick = vi.fn();
    mockLink.click = mockClick;

    const originalCreateElement = document.createElement.bind(document);
    document.createElement = vi.fn((tagName: string): HTMLElement => {
      if (tagName === 'a') {
        return mockLink;
      }
      return originalCreateElement(tagName);
    }) as typeof document.createElement;

    render(<TradeLogTable trades={mockTrades} />);
    const exportButton = screen.getByText('Export CSV');
    fireEvent.click(exportButton);

    expect(mockCreateObjectURL).toHaveBeenCalled();
    expect(mockClick).toHaveBeenCalled();
  });

  it('formats positive P&L with plus sign', () => {
    const { container } = render(<TradeLogTable trades={mockTrades} />);
    // The component should render +25.00 for positive P&L
    expect(container.textContent).toContain('+25.00');
    expect(container.textContent).toContain('+12.50');
  });

  it('formats negative P&L without plus sign', () => {
    const { container } = render(<TradeLogTable trades={mockTrades} />);
    // The component should render -20.00 for negative P&L
    expect(container.textContent).toContain('-20.00');
  });

  it('formats duration correctly for seconds', () => {
    const trades = [
      {
        timestamp: '2024-01-15T10:30:00Z',
        instrument: 'EUR_USD',
        direction: 'long',
        entry_price: 1.085,
        exit_price: 1.0875,
        units: 10000,
        pnl: 25.0,
        duration: 45,
      },
    ];
    const { container } = render(<TradeLogTable trades={trades} />);
    expect(container.textContent).toContain('45s');
  });

  it('formats duration correctly for minutes', () => {
    const trades = [
      {
        timestamp: '2024-01-15T10:30:00Z',
        instrument: 'EUR_USD',
        direction: 'long',
        entry_price: 1.085,
        exit_price: 1.0875,
        units: 10000,
        pnl: 25.0,
        duration: 150,
      },
    ];
    const { container } = render(<TradeLogTable trades={trades} />);
    expect(container.textContent).toContain('2m 30s');
  });

  it('formats duration correctly for hours', () => {
    const trades = [
      {
        timestamp: '2024-01-15T10:30:00Z',
        instrument: 'EUR_USD',
        direction: 'long',
        entry_price: 1.085,
        exit_price: 1.0875,
        units: 10000,
        pnl: 25.0,
        duration: 7200,
      },
    ];
    const { container } = render(<TradeLogTable trades={trades} />);
    expect(container.textContent).toContain('2h');
  });

  it('formats duration correctly for days', () => {
    const trades = [
      {
        timestamp: '2024-01-15T10:30:00Z',
        instrument: 'EUR_USD',
        direction: 'long',
        entry_price: 1.085,
        exit_price: 1.0875,
        units: 10000,
        pnl: 25.0,
        duration: 172800,
      },
    ];
    const { container } = render(<TradeLogTable trades={trades} />);
    expect(container.textContent).toContain('2d');
  });
});
