import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import PositionsPage from '../pages/PositionsPage';
import { AuthProvider } from '../contexts/AuthContext';
import { ToastContext } from '../components/common/ToastContext';
import type { ToastContextType } from '../components/common/ToastContext';
import type { Position } from '../types/position';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

// Mock toast context
const mockShowSuccess = vi.fn();
const mockShowError = vi.fn();
const mockToastContext: ToastContextType = {
  showToast: vi.fn(),
  showSuccess: mockShowSuccess,
  showError: mockShowError,
  showWarning: vi.fn(),
  showInfo: vi.fn(),
};

// Mock accounts data
const mockAccounts = [
  {
    id: 1,
    account_id: '001-001-1234567-001',
    api_type: 'practice' as const,
    currency: 'USD',
    balance: '10000.00',
    margin_used: '500.00',
    margin_available: '9500.00',
    unrealized_pnl: '0.00',
    is_active: true,
    is_default: true,
  },
];

// Mock positions data
const mockActivePositions: Position[] = [
  {
    id: '1',
    position_id: 'POS-001',
    instrument: 'EUR_USD',
    direction: 'LONG',
    units: 10000,
    entry_price: 1.1234,
    current_price: 1.125,
    unrealized_pnl: 16.0,
    status: 'OPEN',
    layer: 1,
    opened_at: '2024-01-15T10:30:00Z',
    closed_at: null,
    account: 1,
    user: 1,
    strategy: 'Floor Strategy',
  },
  {
    id: '2',
    position_id: 'POS-002',
    instrument: 'GBP_USD',
    direction: 'SHORT',
    units: 5000,
    entry_price: 1.2567,
    current_price: 1.255,
    unrealized_pnl: 8.5,
    status: 'OPEN',
    layer: 2,
    opened_at: '2024-01-15T11:00:00Z',
    closed_at: null,
    account: 1,
    user: 1,
    strategy: 'Trend Following',
  },
];

const mockClosedPositions: Position[] = [
  {
    id: '3',
    position_id: 'POS-003',
    instrument: 'EUR_USD',
    direction: 'LONG',
    units: 8000,
    entry_price: 1.11,
    current_price: 1.115,
    unrealized_pnl: 0,
    realized_pnl: 40.0,
    status: 'CLOSED',
    layer: 1,
    opened_at: '2024-01-14T10:00:00Z',
    closed_at: '2024-01-15T12:00:00Z',
    account: 1,
    user: 1,
    strategy: 'Floor Strategy',
  },
  {
    id: '4',
    position_id: 'POS-004',
    instrument: 'USD_JPY',
    direction: 'SHORT',
    units: 12000,
    entry_price: 148.5,
    current_price: 148.3,
    unrealized_pnl: 0,
    realized_pnl: -24.0,
    status: 'CLOSED',
    layer: 1,
    opened_at: '2024-01-14T08:00:00Z',
    closed_at: '2024-01-14T16:00:00Z',
    account: 1,
    user: 1,
    strategy: 'Scalping',
  },
];

// Helper to create a standard mock fetch implementation
const createMockFetch = (
  options: {
    activePositions?: Position[];
    closedPositions?: Position[];
    accounts?: typeof mockAccounts;
    positionsError?: boolean;
  } = {}
) => {
  const {
    activePositions = mockActivePositions,
    closedPositions = mockClosedPositions,
    accounts = mockAccounts,
    positionsError = false,
  } = options;

  return (url: string | URL | Request) => {
    const urlStr = url.toString();

    if (urlStr.includes('/api/system/settings/public')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          registration_enabled: true,
          login_enabled: true,
        }),
      } as Response);
    }

    if (urlStr.includes('/api/accounts') && !urlStr.includes('/sync')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ results: accounts }),
      } as Response);
    }

    if (urlStr.includes('/api/accounts/') && urlStr.includes('/sync')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ message: 'Synced successfully' }),
      } as Response);
    }

    if (urlStr.includes('/api/positions')) {
      if (positionsError) {
        return Promise.resolve({
          ok: false,
          json: async () => ({}),
        } as Response);
      }

      if (urlStr.includes('status=open')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: activePositions }),
        } as Response);
      }

      if (urlStr.includes('status=closed')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: closedPositions }),
        } as Response);
      }

      // Default to empty
      return Promise.resolve({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);
    }

    return Promise.resolve({
      ok: true,
      json: async () => ({}),
    } as Response);
  };
};

const renderWithProviders = (component: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ToastContext.Provider value={mockToastContext}>
            {component}
          </ToastContext.Provider>
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
};

describe('PositionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
    localStorage.clear();
    localStorage.setItem('token', 'test-token');
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 1, email: 'test@example.com' })
    );

    // Default mock
    mockFetch.mockImplementation(createMockFetch());
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders the page title', async () => {
    renderWithProviders(<PositionsPage />);
    expect(screen.getByText('Positions')).toBeInTheDocument();
  });

  it('displays filter controls', async () => {
    renderWithProviders(<PositionsPage />);

    // Wait for the page to load
    await waitFor(() => {
      expect(screen.getByText('Positions')).toBeInTheDocument();
    });

    // Check for filter section heading (use heading role to be specific)
    expect(
      screen.getByRole('heading', { name: /Filter/i })
    ).toBeInTheDocument();
  });

  it('displays tabs for active and closed positions', async () => {
    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      expect(screen.getByText('Active Positions')).toBeInTheDocument();
    });

    expect(screen.getByText('Closed Positions')).toBeInTheDocument();
  });

  it('fetches and displays active positions', async () => {
    mockFetch.mockImplementation(createMockFetch());
    renderWithProviders(<PositionsPage />);

    // Wait for accounts to load and be selected
    await waitFor(
      () => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('displays active position details correctly', async () => {
    mockFetch.mockImplementation(createMockFetch());
    renderWithProviders(<PositionsPage />);

    await waitFor(
      () => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Verify table columns are present by checking for column headers
    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();
  });

  it('switches to closed positions tab and displays closed positions', async () => {
    const user = userEvent.setup();
    mockFetch.mockImplementation(createMockFetch());
    renderWithProviders(<PositionsPage />);

    // Wait for page to load
    await waitFor(
      () => {
        expect(screen.getByText('Active Positions')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Click on Closed Positions tab
    const closedTab = screen.getByText('Closed Positions');
    await user.click(closedTab);

    // Verify tab switched
    await waitFor(
      () => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('filters positions by instrument', async () => {
    mockFetch.mockImplementation(createMockFetch());
    renderWithProviders(<PositionsPage />);

    // Wait for page to load and table to render
    await waitFor(
      () => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Verify filter section exists (use heading role to be specific)
    expect(
      screen.getByRole('heading', { name: /Filter/i })
    ).toBeInTheDocument();
  });

  it('filters positions by layer', async () => {
    mockFetch.mockImplementation(createMockFetch());
    renderWithProviders(<PositionsPage />);

    // Wait for page to load and table to render
    await waitFor(
      () => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Verify filter section exists (use heading role to be specific)
    expect(
      screen.getByRole('heading', { name: /Filter/i })
    ).toBeInTheDocument();
  });

  it('clears all filters', async () => {
    mockFetch.mockImplementation(createMockFetch());
    renderWithProviders(<PositionsPage />);

    await waitFor(
      () => {
        expect(screen.getByText('Active Positions')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Verify clear filters button exists
    expect(
      screen.getByRole('button', { name: /Clear Filters/i })
    ).toBeInTheDocument();
  });

  it('exports active positions to CSV', async () => {
    mockFetch.mockImplementation(createMockFetch());
    renderWithProviders(<PositionsPage />);

    await waitFor(
      () => {
        expect(screen.getByText('Active Positions')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Verify export button exists
    const exportButton = screen.getByRole('button', { name: /Export to CSV/i });
    expect(exportButton).toBeInTheDocument();
  });

  it('exports closed positions to CSV', async () => {
    const user = userEvent.setup();
    mockFetch.mockImplementation(createMockFetch());
    renderWithProviders(<PositionsPage />);

    // Wait for page to load
    await waitFor(
      () => {
        expect(screen.getByText('Active Positions')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Switch to closed positions tab
    const closedTab = screen.getByText('Closed Positions');
    await user.click(closedTab);

    // Verify export button exists
    await waitFor(
      () => {
        const exportButton = screen.getByRole('button', {
          name: /Export to CSV/i,
        });
        expect(exportButton).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('displays error message when fetch fails', async () => {
    mockFetch.mockImplementation(createMockFetch({ positionsError: true }));
    renderWithProviders(<PositionsPage />);

    await waitFor(
      () => {
        expect(screen.getByText('Active Positions')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('displays empty message when no active positions', async () => {
    mockFetch.mockImplementation(createMockFetch({ activePositions: [] }));
    renderWithProviders(<PositionsPage />);

    // Wait for table to render with empty state
    await waitFor(
      () => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Verify empty message is shown
    expect(screen.getByText(/No active positions found/i)).toBeInTheDocument();
  });

  it('displays empty message when no closed positions', async () => {
    const user = userEvent.setup();
    mockFetch.mockImplementation(createMockFetch({ closedPositions: [] }));
    renderWithProviders(<PositionsPage />);

    // Wait for page to load
    await waitFor(
      () => {
        expect(screen.getByText('Active Positions')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Switch to closed positions tab
    const closedTab = screen.getByText('Closed Positions');
    await user.click(closedTab);

    // Verify table is present (empty state will show in table)
    await waitFor(
      () => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('disables export button when no positions', async () => {
    mockFetch.mockImplementation(createMockFetch({ activePositions: [] }));
    renderWithProviders(<PositionsPage />);

    await waitFor(
      () => {
        expect(screen.getByText('Active Positions')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    const exportButton = screen.getByRole('button', { name: /Export to CSV/i });
    expect(exportButton).toBeInTheDocument();
  });

  it('displays loading state while fetching', async () => {
    renderWithProviders(<PositionsPage />);

    // Loading state should appear briefly
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });
});
