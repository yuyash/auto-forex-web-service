import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import OrderHistoryPage from '../pages/OrderHistoryPage';
import { AuthProvider } from '../contexts/AuthContext';
import type { Order } from '../types/order';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

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
  return render(
    <BrowserRouter>
      <AuthProvider>{component}</AuthProvider>
    </BrowserRouter>
  );
};

describe('OrderHistoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('token', 'test-token');
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 1, email: 'test@example.com' })
    );

    // Mock system settings API call
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        registration_enabled: true,
        login_enabled: true,
      }),
    });
  });

  it('renders the page title', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [] }),
      });

    renderWithProviders(<OrderHistoryPage />);

    expect(screen.getByText('Orders History')).toBeInTheDocument();
  });

  it('displays filter controls', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [] }),
      });

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
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: mockOrders }),
      });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('ORD-001')).toBeInTheDocument();
      expect(screen.getByText('ORD-002')).toBeInTheDocument();
      expect(screen.getByText('ORD-003')).toBeInTheDocument();
    });
  });

  it('displays order details correctly', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: mockOrders }),
      });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('EUR_USD')).toBeInTheDocument();
      expect(screen.getByText('GBP_USD')).toBeInTheDocument();
      expect(screen.getByText('10000')).toBeInTheDocument();
      expect(screen.getByText('5000')).toBeInTheDocument();
    });
  });

  it('filters orders by instrument', async () => {
    const user = userEvent.setup();

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: mockOrders }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          results: mockOrders.filter((o) => o.instrument === 'EUR_USD'),
        }),
      });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('ORD-001')).toBeInTheDocument();
    });

    // Open instrument dropdown and select EUR_USD
    const instrumentSelect = screen.getByLabelText(/Instrument/i);
    await user.click(instrumentSelect);

    const eurUsdOption = await screen.findByText('EUR_USD');
    await user.click(eurUsdOption);

    // Click apply filters
    const applyButton = screen.getByRole('button', { name: /Apply Filters/i });
    await user.click(applyButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('instrument=EUR_USD'),
        expect.any(Object)
      );
    });
  });

  it('filters orders by status', async () => {
    const user = userEvent.setup();

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: mockOrders }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          results: mockOrders.filter((o) => o.status === 'FILLED'),
        }),
      });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('ORD-001')).toBeInTheDocument();
    });

    // Open status dropdown and select FILLED
    const statusSelect = screen.getByLabelText(/Status/i);
    await user.click(statusSelect);

    const filledOption = await screen.findByText('Filled');
    await user.click(filledOption);

    // Click apply filters
    const applyButton = screen.getByRole('button', { name: /Apply Filters/i });
    await user.click(applyButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('status=FILLED'),
        expect.any(Object)
      );
    });
  });

  it('searches orders by order ID', async () => {
    const user = userEvent.setup();

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: mockOrders }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          results: mockOrders.filter((o) => o.order_id === 'ORD-001'),
        }),
      });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('ORD-001')).toBeInTheDocument();
    });

    // Enter order ID in search field
    const searchInput = screen.getByPlaceholderText(/e.g., 12345/i);
    await user.type(searchInput, 'ORD-001');

    // Click apply filters
    const applyButton = screen.getByRole('button', { name: /Apply Filters/i });
    await user.click(applyButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('order_id=ORD-001'),
        expect.any(Object)
      );
    });
  });

  it('clears all filters', async () => {
    const user = userEvent.setup();

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: mockOrders }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: mockOrders }),
      });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('ORD-001')).toBeInTheDocument();
    });

    // Set some filters
    const searchInput = screen.getByPlaceholderText(/e.g., 12345/i);
    await user.type(searchInput, 'ORD-001');

    // Click clear filters
    const clearButton = screen.getByRole('button', { name: /Clear Filters/i });
    await user.click(clearButton);

    // Verify search input is cleared
    expect(searchInput).toHaveValue('');
  });

  it('exports orders to CSV', async () => {
    const user = userEvent.setup();

    // Mock URL.createObjectURL
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock-url');

    // Mock document.createElement to track link creation
    const mockLink = {
      setAttribute: vi.fn(),
      click: vi.fn(),
      style: { visibility: '' },
    };
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tagName) => {
      if (tagName === 'a') {
        return mockLink as unknown as HTMLAnchorElement;
      }
      return originalCreateElement(tagName);
    });

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: mockOrders }),
      });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('ORD-001')).toBeInTheDocument();
    });

    // Click export button
    const exportButton = screen.getByRole('button', { name: /Export to CSV/i });
    await user.click(exportButton);

    // Verify link was created and clicked
    expect(mockLink.click).toHaveBeenCalled();
    expect(mockLink.setAttribute).toHaveBeenCalledWith('href', 'blob:mock-url');
    expect(mockLink.setAttribute).toHaveBeenCalledWith(
      'download',
      expect.stringContaining('orders_')
    );
  });

  it('displays error message when fetch fails', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({}),
      });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load orders/i)).toBeInTheDocument();
    });
  });

  it('displays empty message when no orders', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [] }),
      });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('No orders found')).toBeInTheDocument();
    });
  });

  it('disables export button when no orders', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [] }),
      });

    renderWithProviders(<OrderHistoryPage />);

    await waitFor(() => {
      const exportButton = screen.getByRole('button', {
        name: /Export to CSV/i,
      });
      expect(exportButton).toBeDisabled();
    });
  });

  it('displays loading state while fetching', () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            setTimeout(() => {
              resolve({
                ok: true,
                json: async () => ({ results: mockOrders }),
              } as Response);
            }, 100);
          })
      );

    renderWithProviders(<OrderHistoryPage />);

    // Should show loading spinner
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });
});
