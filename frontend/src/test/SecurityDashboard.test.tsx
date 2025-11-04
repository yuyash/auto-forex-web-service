import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import SecurityDashboard from '../components/admin/SecurityDashboard';
import { AuthProvider } from '../contexts/AuthContext';

// Mock the AuthContext
vi.mock('../contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  useAuth: () => ({
    token: 'mock-token',
    user: { id: 1, username: 'admin', is_staff: true },
  }),
}));

// Mock fetch
globalThis.fetch = vi.fn();

const mockSecurityData = {
  stats: {
    failed_login_count: 15,
    blocked_ip_count: 3,
    locked_account_count: 2,
    suspicious_activity_count: 8,
  },
  events: {
    results: [
      {
        id: 1,
        timestamp: '2024-01-15T10:30:00Z',
        event_type: 'failed_login',
        severity: 'warning',
        description: 'Failed login attempt from suspicious IP',
        ip_address: '192.168.1.100',
        username: 'testuser',
      },
    ],
  },
  blockedIPs: [
    {
      ip_address: '192.168.1.100',
      blocked_at: '2024-01-15T10:30:00Z',
      reason: 'Multiple failed login attempts',
      failed_attempts: 5,
    },
  ],
  lockedAccounts: [
    {
      username: 'testuser',
      email: 'test@example.com',
      locked_at: '2024-01-15T10:30:00Z',
      failed_attempts: 10,
    },
  ],
  httpPatterns: [
    {
      ip_address: '192.168.1.200',
      request_count: 150,
      endpoint: '/api/auth/login',
      last_access: '2024-01-15T10:30:00Z',
      status_codes: { '200': 100, '401': 50 },
    },
  ],
};

describe('SecurityDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url: string) => {
        if (url.includes('/api/admin/security/stats')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockSecurityData.stats),
          } as Response);
        }
        if (url.includes('/api/admin/security/events')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockSecurityData.events),
          } as Response);
        }
        if (url.includes('/api/admin/security/blocked-ips')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockSecurityData.blockedIPs),
          } as Response);
        }
        if (url.includes('/api/admin/security/locked-accounts')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockSecurityData.lockedAccounts),
          } as Response);
        }
        if (url.includes('/api/admin/security/http-patterns')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockSecurityData.httpPatterns),
          } as Response);
        }
        return Promise.resolve({
          ok: false,
          json: () => Promise.resolve({}),
        } as Response);
      }
    );
  });

  it('renders security dashboard with statistics', async () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <SecurityDashboard />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('15')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
    });
  });

  it('displays security events table', async () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <SecurityDashboard />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText('Failed login attempt from suspicious IP')
      ).toBeInTheDocument();
      const ipElements = screen.getAllByText('192.168.1.100');
      expect(ipElements.length).toBeGreaterThan(0);
    });
  });

  it('displays blocked IPs table', async () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <SecurityDashboard />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText('Multiple failed login attempts')
      ).toBeInTheDocument();
    });
  });

  it('displays locked accounts table', async () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <SecurityDashboard />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      const usernameElements = screen.getAllByText('testuser');
      expect(usernameElements.length).toBeGreaterThan(0);
      expect(screen.getByText('test@example.com')).toBeInTheDocument();
    });
  });

  it('displays HTTP access patterns table', async () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <SecurityDashboard />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('192.168.1.200')).toBeInTheDocument();
      expect(screen.getByText('/api/auth/login')).toBeInTheDocument();
    });
  });
});
