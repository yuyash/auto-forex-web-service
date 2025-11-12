import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import OrderHistoryPage from '../pages/OrderHistoryPage';
import { AuthProvider } from '../contexts/AuthContext';
import { ToastContext } from '../components/common/ToastContext';
import type { ToastContextType } from '../components/common/ToastContext';
import type { Order } from '../types/order';

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
    balance: 10000.0,
    margin_used: 500.0,
    margin_available: 9500.0,
    is_active: true,
  },
];

// Mock orders data
const mockOrders: Order[] = [
  {
    id: '1',
    order_id: 'ORD-001',
    instrument: 'EUR_USD',
    order_type: 'MARKET',
    direction: 'BUY',
    units: 10000,
    price: 1.1234,
    status: 'FILLED',
    created_at: '2024-01-15T10:30:00Z',
    filled_at: '2024-01-15T10:30:01Z',
    account: 1,
    user: 1,
  },
  {
    id: '2',
    order_id: 'ORD-002',
    instrument: 'GBP_USD',
    order_type: 'LIMIT',
    direction: 'SELL',
    units: 5000,
    price: 1.2567,
    status: 'PENDING',
    created_at: '2024-01-15T11:00:00Z',
    filled_at: null,
    account: 1,
    user: 1,
  },
  {
    id: '3',
    order_id: 'ORD-003',
    instrument: 'EUR_USD',
    order_type: 'STOP',
    direction: 'BUY',
    units: 8000,
    price: 1.11,
    status: 'CANCELLED',
    created_at: '2024-01-15T12:00:00Z',
    filled_at: null,
    account: 1,
    user: 1,
  },
];

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

describe('OrderHistoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
    localStorage.clear();
    localStorage.setItem('token', 'test-token');
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 1, email: 'test@example.com' })
    );

    // Default mock for accounts API
    mockFetch.mockImplementation((url) => {
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
      if (urlStr.includes('/api/accounts')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockAccounts }),
        } as Response);
      }
      if (urlStr.includes('/api/orders')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: [] }),
        } as Response);
      }
      if (urlStr.includes('/api/accounts/1/sync')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ message: 'Synced successfully' }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      } as Response);
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders the page title', async () => {
    renderWithProviders(<OrderHistoryPage />);

    expect(screen.getByText('Orders History')).toBeInTheDocument();
  });

  it('displays filter controls', async () => {
    renderWithProviders(<OrderHistoryPage />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Start Date/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/End Date/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Instrument/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Status/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/e.g., 12345/i)).toBeInTheDocument();
    });
  });

  it('fetches and displays orders', async () => {
    mockFetch.mockImplementation((url) => {
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
      if (urlStr.includes('/api/accounts')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockAccounts }),
        } as Response);
      }
      if (urlStr.includes('/api/orders')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockOrders }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);
    });

    renderWithProviders(<OrderHistoryPage />);

    // Wait for account auto-selection and data to load
    await waitFor(
      () => {
        expect(screen.getByText('ORD-001')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    expect(screen.getByText('ORD-002')).toBeInTheDocument();
    expect(screen.getByText('ORD-003')).toBeInTheDocument();
  });

  it('displays order details correctly', async () => {
    mockFetch.mockImplementation((url) => {
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
      if (urlStr.includes('/api/accounts')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockAccounts }),
        } as Response);
      }
      if (urlStr.includes('/api/orders')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockOrders }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);
    });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(
      () => {
        const table = screen.getByRole('table');
        expect(table).toHaveTextContent('EUR_USD');
      },
      { timeout: 3000 }
    );

    const table = screen.getByRole('table');
    expect(table).toHaveTextContent('GBP_USD');
    expect(table).toHaveTextContent('10000');
    expect(table).toHaveTextContent('5000');
  });

  it('filters orders by instrument', async () => {
    const user = userEvent.setup();
    let filterApplied = false;

    mockFetch.mockImplementation((url) => {
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
      if (urlStr.includes('/api/accounts')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockAccounts }),
        } as Response);
      }
      if (urlStr.includes('/api/orders')) {
        if (urlStr.includes('instrument=EUR_USD')) {
          filterApplied = true;
          return Promise.resolve({
            ok: true,
            json: async () => ({
              results: mockOrders.filter((o) => o.instrument === 'EUR_USD'),
            }),
          } as Response);
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockOrders }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);
    });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(
      () => {
        expect(screen.getByText('ORD-001')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Open instrument dropdown and select EUR_USD
    const instrumentSelect = screen.getByLabelText(/Instrument/i);
    await user.click(instrumentSelect);

    const eurUsdOptions = await screen.findAllByText('EUR_USD');
    await user.click(eurUsdOptions[eurUsdOptions.length - 1]); // Click the dropdown option

    // Click apply filters
    const applyButton = screen.getByRole('button', { name: /Apply Filters/i });
    await user.click(applyButton);

    await waitFor(
      () => {
        expect(filterApplied).toBe(true);
      },
      { timeout: 3000 }
    );
  });

  it('filters orders by status', async () => {
    const user = userEvent.setup();
    let filterApplied = false;

    mockFetch.mockImplementation((url) => {
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
      if (urlStr.includes('/api/accounts')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockAccounts }),
        } as Response);
      }
      if (urlStr.includes('/api/orders')) {
        if (urlStr.includes('status=FILLED')) {
          filterApplied = true;
          return Promise.resolve({
            ok: true,
            json: async () => ({
              results: mockOrders.filter((o) => o.status === 'FILLED'),
            }),
          } as Response);
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockOrders }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);
    });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(
      () => {
        expect(screen.getByText('ORD-001')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Open status dropdown and select FILLED
    const statusSelect = screen.getByLabelText(/Status/i);
    await user.click(statusSelect);

    const filledOptions = await screen.findAllByText('Filled');
    await user.click(filledOptions[filledOptions.length - 1]); // Click the dropdown option

    // Click apply filters
    const applyButton = screen.getByRole('button', { name: /Apply Filters/i });
    await user.click(applyButton);

    await waitFor(
      () => {
        expect(filterApplied).toBe(true);
      },
      { timeout: 3000 }
    );
  });

  it('searches orders by order ID', async () => {
    const user = userEvent.setup();
    let filterApplied = false;

    mockFetch.mockImplementation((url) => {
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
      if (urlStr.includes('/api/accounts')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockAccounts }),
        } as Response);
      }
      if (urlStr.includes('/api/orders')) {
        if (urlStr.includes('order_id=ORD-001')) {
          filterApplied = true;
          return Promise.resolve({
            ok: true,
            json: async () => ({
              results: mockOrders.filter((o) => o.order_id === 'ORD-001'),
            }),
          } as Response);
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockOrders }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);
    });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(
      () => {
        expect(screen.getByText('ORD-001')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Enter order ID in search field
    const searchInput = screen.getByPlaceholderText(/e.g., 12345/i);
    await user.type(searchInput, 'ORD-001');

    // Click apply filters
    const applyButton = screen.getByRole('button', { name: /Apply Filters/i });
    await user.click(applyButton);

    await waitFor(
      () => {
        expect(filterApplied).toBe(true);
      },
      { timeout: 3000 }
    );
  });

  it('clears all filters', async () => {
    const user = userEvent.setup();

    mockFetch.mockImplementation((url) => {
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
      if (urlStr.includes('/api/accounts')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockAccounts }),
        } as Response);
      }
      if (urlStr.includes('/api/orders')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockOrders }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);
    });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(
      () => {
        expect(screen.getByText('ORD-001')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Set some filters
    const searchInput = screen.getByPlaceholderText(/e.g., 12345/i);
    await user.type(searchInput, 'ORD-001');

    // Click clear filters
    const clearButton = screen.getByRole('button', { name: /Clear Filters/i });
    await user.click(clearButton);

    // Verify search input is cleared
    await waitFor(() => {
      expect(searchInput).toHaveValue('');
    });
  });

  it('exports orders to CSV', async () => {
    const user = userEvent.setup();

    // Mock URL.createObjectURL
    const mockCreateObjectURL = vi.fn(() => 'blob:mock-url');
    const originalCreateObjectURL = globalThis.URL.createObjectURL;
    globalThis.URL.createObjectURL = mockCreateObjectURL;

    // Store original createElement
    const originalCreateElement = document.createElement.bind(document);

    // Mock document.createElement to track link creation
    const mockLink = originalCreateElement('a');
    const clickSpy = vi.spyOn(mockLink, 'click');
    const setAttributeSpy = vi.spyOn(mockLink, 'setAttribute');
    const createElementSpy = vi
      .spyOn(document, 'createElement')
      .mockImplementation((tagName) => {
        if (tagName === 'a') {
          return mockLink;
        }
        return originalCreateElement(tagName);
      });

    mockFetch.mockImplementation((url) => {
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
      if (urlStr.includes('/api/accounts')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockAccounts }),
        } as Response);
      }
      if (urlStr.includes('/api/orders')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockOrders }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);
    });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(
      () => {
        expect(screen.getByText('ORD-001')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Click export button
    const exportButton = screen.getByRole('button', { name: /Export to CSV/i });
    await user.click(exportButton);

    // Verify link was created and clicked
    await waitFor(() => {
      expect(clickSpy).toHaveBeenCalled();
    });
    expect(setAttributeSpy).toHaveBeenCalledWith('href', 'blob:mock-url');
    expect(setAttributeSpy).toHaveBeenCalledWith(
      'download',
      expect.stringContaining('orders_')
    );

    // Restore original methods
    globalThis.URL.createObjectURL = originalCreateObjectURL;
    createElementSpy.mockRestore();
  });

  it('displays error message when fetch fails', async () => {
    mockFetch.mockImplementation((url) => {
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
      if (urlStr.includes('/api/accounts')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockAccounts }),
        } as Response);
      }
      if (urlStr.includes('/api/orders')) {
        return Promise.resolve({
          ok: false,
          json: async () => ({}),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);
    });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(
      () => {
        expect(screen.getByText(/Failed to fetch orders/i)).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('displays empty message when no orders', async () => {
    mockFetch.mockImplementation((url) => {
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
      if (urlStr.includes('/api/accounts')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockAccounts }),
        } as Response);
      }
      if (urlStr.includes('/api/orders')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: [] }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);
    });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(
      () => {
        expect(
          screen.getByText(/No orders found for this account/i)
        ).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('disables export button when no orders', async () => {
    mockFetch.mockImplementation((url) => {
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
      if (urlStr.includes('/api/accounts')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockAccounts }),
        } as Response);
      }
      if (urlStr.includes('/api/orders')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: [] }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);
    });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(
      () => {
        const exportButton = screen.getByRole('button', {
          name: /Export to CSV/i,
        });
        expect(exportButton).toBeDisabled();
      },
      { timeout: 3000 }
    );
  });

  it('displays loading state while fetching', async () => {
    let resolveOrders: ((value: Response) => void) | null = null;

    mockFetch.mockImplementation((url) => {
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
      if (urlStr.includes('/api/accounts')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockAccounts }),
        } as Response);
      }
      if (urlStr.includes('/api/orders')) {
        return new Promise<Response>((resolve) => {
          resolveOrders = resolve;
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ results: [] }),
      } as Response);
    });

    renderWithProviders(<OrderHistoryPage />);

    // Wait for loading spinner to appear
    await waitFor(
      () => {
        expect(screen.getByRole('progressbar')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Resolve the orders fetch
    if (resolveOrders) {
      resolveOrders({
        ok: true,
        json: async () => ({ results: mockOrders }),
      } as Response);
    }
  });
});
