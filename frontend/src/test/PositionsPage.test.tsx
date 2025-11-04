import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import PositionsPage from '../pages/PositionsPage';
import { AuthProvider } from '../contexts/AuthContext';
import type { Position } from '../types/position';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

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

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <AuthProvider>{component}</AuthProvider>
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

    // Mock system settings API call
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        registration_enabled: true,
        login_enabled: true,
      }),
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
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
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [] }),
      });

    renderWithProviders(<PositionsPage />);

    expect(screen.getByText('Positions')).toBeInTheDocument();
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
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [] }),
      });

    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Start Date/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/End Date/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Instrument/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Layer/i)).toBeInTheDocument();
    });
  });

  it('displays tabs for active and closed positions', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [] }),
      });

    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      expect(screen.getByText('Active Positions')).toBeInTheDocument();
      expect(screen.getByText('Closed Positions')).toBeInTheDocument();
    });
  });

  it('fetches and displays active positions', async () => {
    mockFetch.mockImplementation((url) => {
      if (url.toString().includes('/api/system/settings/public')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        } as Response);
      }
      if (
        url.toString().includes('/api/positions') &&
        url.toString().includes('status=OPEN')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockActivePositions }),
        } as Response);
      }
      if (
        url.toString().includes('/api/positions') &&
        url.toString().includes('status=CLOSED')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: [] }),
        } as Response);
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      expect(screen.getByText('POS-001')).toBeInTheDocument();
      expect(screen.getByText('POS-002')).toBeInTheDocument();
      const table = screen.getByRole('table');
      expect(table).toHaveTextContent('EUR_USD');
      expect(table).toHaveTextContent('GBP_USD');
    });
  });

  it('displays active position details correctly', async () => {
    mockFetch.mockImplementation((url) => {
      if (url.toString().includes('/api/system/settings/public')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        } as Response);
      }
      if (
        url.toString().includes('/api/positions') &&
        url.toString().includes('status=OPEN')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockActivePositions }),
        } as Response);
      }
      if (
        url.toString().includes('/api/positions') &&
        url.toString().includes('status=CLOSED')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: [] }),
        } as Response);
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      const table = screen.getByRole('table');
      expect(table).toHaveTextContent('10000');
      expect(table).toHaveTextContent('5000');
      expect(table).toHaveTextContent('1.12340');
      expect(table).toHaveTextContent('1.25670');
      expect(table).toHaveTextContent('+16.00');
      expect(table).toHaveTextContent('+8.50');
    });
  });

  it('switches to closed positions tab and displays closed positions', async () => {
    const user = userEvent.setup();

    mockFetch.mockImplementation((url) => {
      if (url.toString().includes('/api/system/settings/public')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        } as Response);
      }
      if (
        url.toString().includes('/api/positions') &&
        url.toString().includes('status=OPEN')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockActivePositions }),
        } as Response);
      }
      if (
        url.toString().includes('/api/positions') &&
        url.toString().includes('status=CLOSED')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockClosedPositions }),
        } as Response);
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      expect(screen.getByText('POS-001')).toBeInTheDocument();
    });

    // Click on Closed Positions tab
    const closedTab = screen.getByText('Closed Positions');
    await user.click(closedTab);

    await waitFor(() => {
      expect(screen.getByText('POS-003')).toBeInTheDocument();
      expect(screen.getByText('POS-004')).toBeInTheDocument();
      const table = screen.getByRole('table');
      expect(table).toHaveTextContent('+40.00');
      expect(table).toHaveTextContent('-24.00');
    });
  });

  it('filters positions by instrument', async () => {
    const user = userEvent.setup();
    let filterApplied = false;

    mockFetch.mockImplementation((url) => {
      if (url.toString().includes('/api/system/settings/public')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        } as Response);
      }
      if (url.toString().includes('/api/positions')) {
        if (url.toString().includes('instrument=EUR_USD')) {
          filterApplied = true;
          if (url.toString().includes('status=OPEN')) {
            return Promise.resolve({
              ok: true,
              json: async () => ({
                results: mockActivePositions.filter(
                  (p) => p.instrument === 'EUR_USD'
                ),
              }),
            } as Response);
          } else {
            return Promise.resolve({
              ok: true,
              json: async () => ({
                results: mockClosedPositions.filter(
                  (p) => p.instrument === 'EUR_USD'
                ),
              }),
            } as Response);
          }
        }
        if (url.toString().includes('status=OPEN')) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ results: mockActivePositions }),
          } as Response);
        } else {
          return Promise.resolve({
            ok: true,
            json: async () => ({ results: mockClosedPositions }),
          } as Response);
        }
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      expect(screen.getByText('POS-001')).toBeInTheDocument();
    });

    // Open instrument dropdown and select EUR_USD
    const instrumentSelect = screen.getByLabelText(/Instrument/i);
    await user.click(instrumentSelect);

    const eurUsdOptions = await screen.findAllByText('EUR_USD');
    await user.click(eurUsdOptions[eurUsdOptions.length - 1]); // Click the dropdown option

    // Click apply filters
    const applyButton = screen.getByRole('button', { name: /Apply Filters/i });
    await user.click(applyButton);

    await waitFor(() => {
      expect(filterApplied).toBe(true);
    });
  });

  it('filters positions by layer', async () => {
    const user = userEvent.setup();
    let filterApplied = false;

    mockFetch.mockImplementation((url) => {
      if (url.toString().includes('/api/system/settings/public')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        } as Response);
      }
      if (url.toString().includes('/api/positions')) {
        if (url.toString().includes('layer=1')) {
          filterApplied = true;
          if (url.toString().includes('status=OPEN')) {
            return Promise.resolve({
              ok: true,
              json: async () => ({
                results: mockActivePositions.filter((p) => p.layer === 1),
              }),
            } as Response);
          } else {
            return Promise.resolve({
              ok: true,
              json: async () => ({
                results: mockClosedPositions.filter((p) => p.layer === 1),
              }),
            } as Response);
          }
        }
        if (url.toString().includes('status=OPEN')) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ results: mockActivePositions }),
          } as Response);
        } else {
          return Promise.resolve({
            ok: true,
            json: async () => ({ results: mockClosedPositions }),
          } as Response);
        }
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      expect(screen.getByText('POS-001')).toBeInTheDocument();
    });

    // Open layer dropdown and select layer 1
    const layerSelect = screen.getByLabelText(/Layer/i);
    await user.click(layerSelect);

    const layer1Options = await screen.findAllByText('1');
    await user.click(layer1Options[layer1Options.length - 1]); // Click the dropdown option

    // Click apply filters
    const applyButton = screen.getByRole('button', { name: /Apply Filters/i });
    await user.click(applyButton);

    await waitFor(() => {
      expect(filterApplied).toBe(true);
    });
  });

  it('clears all filters', async () => {
    const user = userEvent.setup();

    mockFetch.mockImplementation((url) => {
      if (url.toString().includes('/api/system/settings/public')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        } as Response);
      }
      if (
        url.toString().includes('/api/positions') &&
        url.toString().includes('status=OPEN')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockActivePositions }),
        } as Response);
      }
      if (
        url.toString().includes('/api/positions') &&
        url.toString().includes('status=CLOSED')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockClosedPositions }),
        } as Response);
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      expect(screen.getByText('POS-001')).toBeInTheDocument();
    });

    // Set a filter
    const instrumentSelect = screen.getByLabelText(/Instrument/i);
    await user.click(instrumentSelect);
    const eurUsdOptions = await screen.findAllByText('EUR_USD');
    await user.click(eurUsdOptions[eurUsdOptions.length - 1]);

    // Verify filter was set
    await waitFor(() => {
      expect(instrumentSelect).toHaveTextContent('EUR_USD');
    });

    // Click clear filters
    const clearButton = screen.getByRole('button', { name: /Clear Filters/i });
    await user.click(clearButton);

    // Verify filter is cleared by checking that the data is refetched without filters
    await waitFor(() => {
      // After clearing, the fetch should be called without instrument filter
      const calls = mockFetch.mock.calls;
      const lastCall = calls[calls.length - 1];
      if (lastCall && lastCall[0]) {
        const url = lastCall[0].toString();
        expect(url).not.toContain('instrument=EUR_USD');
      }
    });
  });

  it('exports active positions to CSV', async () => {
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
      if (url.toString().includes('/api/system/settings/public')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        } as Response);
      }
      if (
        url.toString().includes('/api/positions') &&
        url.toString().includes('status=OPEN')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockActivePositions }),
        } as Response);
      }
      if (
        url.toString().includes('/api/positions') &&
        url.toString().includes('status=CLOSED')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: [] }),
        } as Response);
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      expect(screen.getByText('POS-001')).toBeInTheDocument();
    });

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
      expect.stringContaining('active_positions_')
    );

    // Restore original methods
    globalThis.URL.createObjectURL = originalCreateObjectURL;
    createElementSpy.mockRestore();
  });

  it('exports closed positions to CSV', async () => {
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
      if (url.toString().includes('/api/system/settings/public')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        } as Response);
      }
      if (
        url.toString().includes('/api/positions') &&
        url.toString().includes('status=OPEN')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: [] }),
        } as Response);
      }
      if (
        url.toString().includes('/api/positions') &&
        url.toString().includes('status=CLOSED')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: mockClosedPositions }),
        } as Response);
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      const closedTab = screen.getByText('Closed Positions');
      return closedTab;
    });

    // Switch to closed positions tab
    const closedTab = screen.getByText('Closed Positions');
    await user.click(closedTab);

    await waitFor(() => {
      expect(screen.getByText('POS-003')).toBeInTheDocument();
    });

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
      expect.stringContaining('closed_positions_')
    );

    // Restore original methods
    globalThis.URL.createObjectURL = originalCreateObjectURL;
    createElementSpy.mockRestore();
  });

  it('displays error message when fetch fails', async () => {
    mockFetch.mockImplementation((url) => {
      if (url.toString().includes('/api/system/settings/public')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        } as Response);
      }
      if (url.toString().includes('/api/positions')) {
        return Promise.resolve({
          ok: false,
          json: async () => ({}),
        } as Response);
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load positions/i)).toBeInTheDocument();
    });
  });

  it('displays empty message when no active positions', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [] }),
      });

    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      expect(screen.getByText('No active positions')).toBeInTheDocument();
    });
  });

  it('displays empty message when no closed positions', async () => {
    const user = userEvent.setup();

    mockFetch.mockImplementation((url) => {
      if (url.toString().includes('/api/system/settings/public')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        } as Response);
      }
      if (url.toString().includes('/api/positions')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ results: [] }),
        } as Response);
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderWithProviders(<PositionsPage />);

    await waitFor(() => {
      const closedTab = screen.getByText('Closed Positions');
      return closedTab;
    });

    // Switch to closed positions tab
    const closedTab = screen.getByText('Closed Positions');
    await user.click(closedTab);

    await waitFor(() => {
      expect(screen.getByText('No closed positions')).toBeInTheDocument();
    });
  });

  it('disables export button when no positions', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ registration_enabled: true, login_enabled: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [] }),
      });

    renderWithProviders(<PositionsPage />);

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
                json: async () => ({ results: mockActivePositions }),
              } as Response);
            }, 100);
          })
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            setTimeout(() => {
              resolve({
                ok: true,
                json: async () => ({ results: mockClosedPositions }),
              } as Response);
            }, 100);
          })
      );

    renderWithProviders(<PositionsPage />);

    // Should show loading spinner
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });
});
