import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import NotificationCenter from '../components/admin/NotificationCenter';
import type { AdminNotification } from '../types/admin';

// Mock i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: { count?: number }) => {
      if (key === 'notifications.title') return 'Notifications';
      if (key === 'events.justNow') return 'Just now';
      if (key === 'events.minutesAgo') {
        return options?.count === 1
          ? '1 minute ago'
          : `${options?.count} minutes ago`;
      }
      if (key === 'events.hoursAgo') {
        return options?.count === 1
          ? '1 hour ago'
          : `${options?.count} hours ago`;
      }
      if (key === 'events.daysAgo') {
        return options?.count === 1
          ? '1 day ago'
          : `${options?.count} days ago`;
      }
      return key;
    },
  }),
}));

// Mock WebSocket
class MockWebSocket {
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: ((error: Event) => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(public url: string) {
    setTimeout(() => {
      if (this.onopen) this.onopen();
    }, 0);
  }

  close() {
    if (this.onclose) this.onclose();
  }

  send() {}
}

(globalThis as { WebSocket: typeof WebSocket }).WebSocket =
  MockWebSocket as unknown as typeof WebSocket;

// Mock useAuth hook
const mockUseAuth = vi.fn();
vi.mock('../contexts/AuthContext', async () => {
  const actual = await vi.importActual('../contexts/AuthContext');
  return {
    ...actual,
    useAuth: () => mockUseAuth(),
  };
});

describe('NotificationCenter', () => {
  const mockUser = {
    id: 1,
    username: 'admin',
    email: 'admin@example.com',
    is_staff: true,
  };

  const mockToken = 'mock-token';

  const mockNotifications: AdminNotification[] = [
    {
      id: 1,
      timestamp: new Date(Date.now() - 5 * 60000).toISOString(), // 5 minutes ago
      severity: 'warning',
      title: 'Margin Warning',
      message: 'Margin warning for account 123456',
      read: false,
    },
    {
      id: 2,
      timestamp: new Date(Date.now() - 60 * 60000).toISOString(), // 1 hour ago
      severity: 'error',
      title: 'Connection Failed',
      message: 'Connection failed for account 789012',
      read: false,
    },
    {
      id: 3,
      timestamp: new Date(Date.now() - 24 * 60 * 60000).toISOString(), // 1 day ago
      severity: 'info',
      title: 'System Update',
      message: 'System updated successfully',
      read: true,
    },
  ];

  const mockAuthContext = {
    user: mockUser,
    token: mockToken,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    refreshToken: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue(mockAuthContext);
    (globalThis as { fetch: typeof fetch }).fetch = vi.fn();
  });

  const renderComponent = () => {
    return render(
      <BrowserRouter>
        <NotificationCenter />
      </BrowserRouter>
    );
  };

  it('should not render for non-admin users', () => {
    mockUseAuth.mockReturnValue({
      ...mockAuthContext,
      user: { ...mockUser, is_staff: false },
    });

    const { container } = renderComponent();
    expect(container.firstChild).toBeNull();
  });

  it('should render notification bell with badge for admin users', () => {
    renderComponent();

    const notificationButton = screen.getByLabelText(
      /show \d+ new notifications/i
    );
    expect(notificationButton).toBeInTheDocument();
  });

  it('should display unread count in badge', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => mockNotifications,
    });
    (globalThis as { fetch: typeof fetch }).fetch = mockFetch;

    renderComponent();

    const notificationButton = screen.getByLabelText(
      /show \d+ new notifications/i
    );
    fireEvent.click(notificationButton);

    await waitFor(() => {
      expect(screen.getByText('Notifications')).toBeInTheDocument();
    });

    // Check that unread notifications are displayed
    await waitFor(() => {
      expect(screen.getByText('Margin Warning')).toBeInTheDocument();
      expect(screen.getByText('Connection Failed')).toBeInTheDocument();
    });
  });

  it('should fetch notifications when popover is opened', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => mockNotifications,
    });
    (globalThis as { fetch: typeof fetch }).fetch = mockFetch;

    renderComponent();

    const notificationButton = screen.getByLabelText(
      /show \d+ new notifications/i
    );
    fireEvent.click(notificationButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/admin/notifications', {
        headers: {
          Authorization: `Bearer ${mockToken}`,
        },
      });
    });
  });

  it('should display notifications with correct severity colors', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => mockNotifications,
    });
    (globalThis as { fetch: typeof fetch }).fetch = mockFetch;

    renderComponent();

    const notificationButton = screen.getByLabelText(
      /show \d+ new notifications/i
    );
    fireEvent.click(notificationButton);

    await waitFor(() => {
      expect(screen.getByText('warning')).toBeInTheDocument();
      expect(screen.getByText('error')).toBeInTheDocument();
      expect(screen.getByText('info')).toBeInTheDocument();
    });
  });

  it('should mark notification as read when clicked', async () => {
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockNotifications,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });
    (globalThis as { fetch: typeof fetch }).fetch = mockFetch;

    renderComponent();

    const notificationButton = screen.getByLabelText(
      /show \d+ new notifications/i
    );
    fireEvent.click(notificationButton);

    await waitFor(() => {
      expect(screen.getByText('Margin Warning')).toBeInTheDocument();
    });

    const unreadNotification = screen.getByText('Margin Warning').closest('li');
    if (unreadNotification) {
      fireEvent.click(unreadNotification);
    }

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/admin/notifications/1/read',
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${mockToken}`,
            'Content-Type': 'application/json',
          },
        }
      );
    });
  });

  it('should mark all notifications as read', async () => {
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockNotifications,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });
    (globalThis as { fetch: typeof fetch }).fetch = mockFetch;

    renderComponent();

    const notificationButton = screen.getByLabelText(
      /show \d+ new notifications/i
    );
    fireEvent.click(notificationButton);

    await waitFor(() => {
      expect(screen.getByText('Mark all as read')).toBeInTheDocument();
    });

    const markAllButton = screen.getByText('Mark all as read');
    fireEvent.click(markAllButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/admin/notifications/read-all',
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${mockToken}`,
            'Content-Type': 'application/json',
          },
        }
      );
    });
  });

  it('should display loading state while fetching notifications', async () => {
    const mockFetch = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(() => {
            resolve({
              ok: true,
              json: async () => mockNotifications,
            });
          }, 100);
        })
    );
    (globalThis as { fetch: typeof fetch }).fetch = mockFetch;

    renderComponent();

    const notificationButton = screen.getByLabelText(
      /show \d+ new notifications/i
    );
    fireEvent.click(notificationButton);

    await waitFor(() => {
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });

  it('should display error message when fetch fails', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 500,
    });
    (globalThis as { fetch: typeof fetch }).fetch = mockFetch;

    renderComponent();

    const notificationButton = screen.getByLabelText(
      /show \d+ new notifications/i
    );
    fireEvent.click(notificationButton);

    await waitFor(() => {
      expect(
        screen.getByText(/Failed to fetch notifications/i)
      ).toBeInTheDocument();
    });
  });

  it('should display empty state when no notifications', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });
    (globalThis as { fetch: typeof fetch }).fetch = mockFetch;

    renderComponent();

    const notificationButton = screen.getByLabelText(
      /show \d+ new notifications/i
    );
    fireEvent.click(notificationButton);

    await waitFor(() => {
      expect(screen.getByText('No notifications')).toBeInTheDocument();
    });
  });

  it('should format timestamps correctly', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => mockNotifications,
    });
    (globalThis as { fetch: typeof fetch }).fetch = mockFetch;

    renderComponent();

    const notificationButton = screen.getByLabelText(
      /show \d+ new notifications/i
    );
    fireEvent.click(notificationButton);

    await waitFor(() => {
      expect(screen.getByText('5 minutes ago')).toBeInTheDocument();
      expect(screen.getByText('1 hour ago')).toBeInTheDocument();
      expect(screen.getByText('1 day ago')).toBeInTheDocument();
    });
  });

  it('should close popover when close button is clicked', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => mockNotifications,
    });
    (globalThis as { fetch: typeof fetch }).fetch = mockFetch;

    renderComponent();

    const notificationButton = screen.getByLabelText(
      /show \d+ new notifications/i
    );
    fireEvent.click(notificationButton);

    await waitFor(() => {
      expect(screen.getByText('Notifications')).toBeInTheDocument();
    });

    const closeButton = screen.getByRole('button', { name: '' });
    fireEvent.click(closeButton);

    await waitFor(() => {
      expect(screen.queryByText('Notifications')).not.toBeInTheDocument();
    });
  });
});
