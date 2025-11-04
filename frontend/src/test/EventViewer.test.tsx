import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  render,
  screen,
  waitFor,
  fireEvent,
  cleanup,
} from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import EventViewer from '../components/admin/EventViewer';
import type { User, SystemSettings } from '../types/auth';

// Mock the date picker components
vi.mock('@mui/x-date-pickers/DatePicker', () => ({
  DatePicker: ({
    label,
    onChange,
  }: {
    label: string;
    onChange: (date: Date | null) => void;
  }) => (
    <div data-testid={`date-picker-${label}`}>
      <input
        type="date"
        aria-label={label}
        onChange={(e) =>
          onChange(e.target.value ? new Date(e.target.value) : null)
        }
      />
    </div>
  ),
}));

vi.mock('@mui/x-date-pickers/LocalizationProvider', () => ({
  LocalizationProvider: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

vi.mock('@mui/x-date-pickers/AdapterDateFns', () => ({
  AdapterDateFns: vi.fn(),
}));

const mockUser: User = {
  id: 1,
  username: 'admin',
  email: 'admin@test.com',
  is_staff: true,
  timezone: 'UTC',
  language: 'en',
};

const mockSystemSettings: SystemSettings = {
  login_enabled: true,
  registration_enabled: true,
};

// Mock AuthProvider
vi.mock('../contexts/AuthContext', async () => {
  const actual = await vi.importActual('../contexts/AuthContext');
  return {
    ...actual,
    useAuth: () => ({
      user: mockUser,
      token: 'mock-token',
      isAuthenticated: true,
      systemSettings: mockSystemSettings,
      systemSettingsLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      register: vi.fn(),
    }),
  };
});

const mockEvents = [
  {
    id: 1,
    timestamp: '2024-01-01T10:00:00Z',
    category: 'trading',
    event_type: 'order_placed',
    severity: 'info' as const,
    description: 'Order placed successfully',
    user: 'testuser',
    ip_address: '192.168.1.1',
  },
  {
    id: 2,
    timestamp: '2024-01-01T11:00:00Z',
    category: 'system',
    event_type: 'connection_failed',
    severity: 'error' as const,
    description: 'Connection to OANDA API failed',
    user: 'admin',
    ip_address: '192.168.1.2',
  },
];

describe('EventViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn() as unknown as typeof fetch;
  });

  afterEach(() => {
    cleanup();
  });

  const renderComponent = () => {
    return render(
      <BrowserRouter>
        <EventViewer />
      </BrowserRouter>
    );
  };

  it('renders event viewer with title', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ results: mockEvents, count: 2 }),
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/Recent Events/i)).toBeInTheDocument();
    });
  });

  it('fetches and displays events', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ results: mockEvents, count: 2 }),
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Order placed successfully')).toBeInTheDocument();
      expect(
        screen.getByText('Connection to OANDA API failed')
      ).toBeInTheDocument();
    });
  });

  it('displays loading state', () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );

    renderComponent();

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('displays error message on fetch failure', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('Failed to fetch events')
    );

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/Failed to fetch events/i)).toBeInTheDocument();
    });
  });

  it('filters events by category', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ results: mockEvents, count: 2 }),
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Order placed successfully')).toBeInTheDocument();
    });

    const categorySelect = screen.getByLabelText(/Category/i);
    fireEvent.mouseDown(categorySelect);

    await waitFor(() => {
      const options = screen.getAllByRole('option');
      const tradingOption = options.find(
        (opt) => opt.textContent === 'Trading'
      );
      if (tradingOption) {
        fireEvent.click(tradingOption);
      }
    });

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('category=trading'),
        expect.any(Object)
      );
    });
  });

  it('filters events by severity', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ results: mockEvents, count: 2 }),
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Order placed successfully')).toBeInTheDocument();
    });

    const severitySelect = screen.getByLabelText(/Severity/i);
    fireEvent.mouseDown(severitySelect);

    await waitFor(() => {
      const options = screen.getAllByRole('option');
      const errorOption = options.find((opt) => opt.textContent === 'Error');
      if (errorOption) {
        fireEvent.click(errorOption);
      }
    });

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('severity=error'),
        expect.any(Object)
      );
    });
  });

  it('filters events by username', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ results: mockEvents, count: 2 }),
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Order placed successfully')).toBeInTheDocument();
    });

    const usernameInput = screen.getByPlaceholderText(/Filter by username/i);
    fireEvent.change(usernameInput, { target: { value: 'testuser' } });

    const applyButton = screen.getByText(/Apply Filters/i);
    fireEvent.click(applyButton);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('username=testuser'),
        expect.any(Object)
      );
    });
  });

  it('performs full-text search', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ results: mockEvents, count: 2 }),
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Order placed successfully')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search description/i);
    fireEvent.change(searchInput, { target: { value: 'order' } });

    const applyButton = screen.getByText(/Apply Filters/i);
    fireEvent.click(applyButton);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('search=order'),
        expect.any(Object)
      );
    });
  });

  it('clears all filters', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ results: mockEvents, count: 2 }),
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Order placed successfully')).toBeInTheDocument();
    });

    // Set some filters
    const usernameInput = screen.getByPlaceholderText(/Filter by username/i);
    fireEvent.change(usernameInput, { target: { value: 'testuser' } });

    // Clear filters
    const clearButton = screen.getByText(/Clear Filters/i);
    fireEvent.click(clearButton);

    expect(usernameInput).toHaveValue('');
  });

  it('calls export API when export button is clicked', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: mockEvents, count: 2 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        blob: async () => new Blob(['csv data'], { type: 'text/csv' }),
      });

    // Mock URL methods
    const createObjectURLSpy = vi
      .spyOn(globalThis.URL, 'createObjectURL')
      .mockReturnValue('blob:mock-url');
    const revokeObjectURLSpy = vi
      .spyOn(globalThis.URL, 'revokeObjectURL')
      .mockImplementation(() => {});

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Order placed successfully')).toBeInTheDocument();
    });

    const exportButton = screen.getByText(/Export CSV/i);
    fireEvent.click(exportButton);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/events/export'),
        expect.any(Object)
      );
    });

    createObjectURLSpy.mockRestore();
    revokeObjectURLSpy.mockRestore();
  });

  it('displays pagination when there are many events', async () => {
    const manyEvents = Array.from({ length: 100 }, (_, i) => ({
      ...mockEvents[0],
      id: i + 1,
      description: `Event ${i + 1}`,
    }));

    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ results: manyEvents.slice(0, 50), count: 100 }),
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/Page 1 of 2/i)).toBeInTheDocument();
    });
  });

  it('fetches next page when next button is clicked', async () => {
    const manyEvents = Array.from({ length: 100 }, (_, i) => ({
      ...mockEvents[0],
      id: i + 1,
      description: `Event ${i + 1}`,
    }));

    (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: manyEvents.slice(0, 50), count: 100 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: manyEvents.slice(50, 100), count: 100 }),
      });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Event 1')).toBeInTheDocument();
    });

    const nextButton = screen.getByText(/Next/i);
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('page=2'),
        expect.any(Object)
      );
    });
  });

  it('shows empty state when no events are returned', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ results: [], count: 0 }),
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/No recent events/i)).toBeInTheDocument();
    });
  });

  it('renders severity chips for events', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ results: mockEvents, count: 2 }),
    });

    renderComponent();

    await waitFor(() => {
      const infoChips = screen.getAllByText('Info');
      const errorChips = screen.getAllByText('Error');
      expect(infoChips.length).toBeGreaterThan(0);
      expect(errorChips.length).toBeGreaterThan(0);
    });
  });

  it('renders category chips for events', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ results: mockEvents, count: 2 }),
    });

    renderComponent();

    await waitFor(() => {
      const tradingChips = screen.getAllByText('Trading');
      const systemChips = screen.getAllByText('System');
      expect(tradingChips.length).toBeGreaterThan(0);
      expect(systemChips.length).toBeGreaterThan(0);
    });
  });
});
