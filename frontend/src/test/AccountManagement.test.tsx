import { describe, it, expect, vi, beforeEach, afterAll } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import AccountManagement from '../components/settings/AccountManagement';
import { AuthProvider } from '../contexts/AuthContext';
import { ToastContext } from '../components/common/ToastContext';
import type { ToastContextType } from '../components/common/ToastContext';
import '../i18n/config';

// Mock fetch
const originalFetch = globalThis.fetch;
const mockFetch = vi.fn();

type FetchMatcher = {
  method?: string;
  url: string | RegExp;
};

type MockFetchResponse = {
  ok: boolean;
  status?: number;
  json: () => Promise<unknown>;
};

type PendingFetch = {
  matcher: FetchMatcher;
  resolver: () => Promise<MockFetchResponse>;
};

let pendingFetches: PendingFetch[] = [];

const toMethod = (method?: string) => (method ? method.toUpperCase() : 'GET');

const normalizeUrl = (input: RequestInfo | URL): string => {
  if (typeof input === 'string') {
    return input;
  }
  if (input instanceof URL) {
    return input.toString();
  }
  return input.url;
};

const matchesRequest = (matcher: FetchMatcher, method: string, url: string) => {
  const methodMatches = !matcher.method || toMethod(matcher.method) === method;
  if (!methodMatches) {
    return false;
  }
  if (typeof matcher.url === 'string') {
    return matcher.url === url;
  }
  return matcher.url.test(url);
};

const enqueueFetch = (
  matcher: FetchMatcher,
  resolver: PendingFetch['resolver']
) => {
  pendingFetches.push({
    matcher: {
      method: matcher.method ? toMethod(matcher.method) : undefined,
      url: matcher.url,
    },
    resolver,
  });
};

const jsonResponse = (
  data: unknown,
  { ok = true, status }: { ok?: boolean; status?: number } = {}
): MockFetchResponse => ({
  ok,
  status: status ?? (ok ? 200 : 400),
  json: async () => data,
});

const queueJsonResponse = (
  matcher: FetchMatcher,
  data: unknown,
  options?: { ok?: boolean; status?: number }
) => {
  enqueueFetch(matcher, async () => jsonResponse(data, options));
};

const queueNetworkError = (matcher: FetchMatcher, error: Error) => {
  enqueueFetch(matcher, () => Promise.reject(error));
};

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

const mockSystemSettings = {
  timezone: 'UTC',
  feature_flags: {},
};

const LONG_TEST_TIMEOUT = 30000;

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
  {
    id: 2,
    account_id: '001-001-7654321-002',
    api_type: 'live' as const,
    currency: 'USD',
    balance: 5000.0,
    margin_used: 200.0,
    margin_available: 4800.0,
    is_active: false,
  },
];

const queueAccountsResponse = (accounts: typeof mockAccounts | []) => {
  queueJsonResponse({ method: 'GET', url: '/api/accounts/' }, accounts);
};

const queuePositionSettingsResponse = (
  accountId: number,
  settings: Record<string, unknown>
) => {
  queueJsonResponse(
    { method: 'GET', url: `/api/accounts/${accountId}/position-diff/` },
    settings
  );
};

const renderComponent = () => {
  return render(
    <BrowserRouter>
      <AuthProvider>
        <ToastContext.Provider value={mockToastContext}>
          <AccountManagement />
        </ToastContext.Provider>
      </AuthProvider>
    </BrowserRouter>
  );
};

describe('AccountManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pendingFetches = [];
    mockFetch.mockReset();
    globalThis.fetch = mockFetch as unknown as typeof fetch;
    mockFetch.mockImplementation(
      (input: RequestInfo | URL, init?: RequestInit) => {
        const url = normalizeUrl(input);
        const method = toMethod(init?.method);
        const index = pendingFetches.findIndex(({ matcher }) =>
          matchesRequest(matcher, method, url)
        );

        if (index === -1) {
          // Fail fast for unmocked requests instead of hanging
          console.error(`No mock handler for ${method} ${url}`);
          return Promise.reject(
            new Error(`No mock handler for ${method} ${url}`)
          );
        }

        const [entry] = pendingFetches.splice(index, 1);
        return entry.resolver();
      }
    );
    queueJsonResponse(
      { method: 'GET', url: '/api/system/settings/public' },
      mockSystemSettings
    );
    localStorage.setItem('token', 'test-token');
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 1, email: 'test@example.com' })
    );
  });

  afterAll(() => {
    if (originalFetch) {
      globalThis.fetch = originalFetch;
    } else {
      Reflect.deleteProperty(globalThis as { fetch?: typeof fetch }, 'fetch');
    }
  });

  it('renders loading state initially', () => {
    mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves
    renderComponent();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('fetches and displays accounts', async () => {
    queueAccountsResponse(mockAccounts);

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('001-001-1234567-001')).toBeInTheDocument();
      expect(screen.getByText('001-001-7654321-002')).toBeInTheDocument();
    });

    // Check practice account
    const practiceCard = screen
      .getByText('001-001-1234567-001')
      .closest('.MuiCard-root') as HTMLElement;
    expect(practiceCard).toBeInTheDocument();
    if (practiceCard) {
      expect(within(practiceCard).getByText('Practice')).toBeInTheDocument();
      expect(within(practiceCard).getByText('$10,000.00')).toBeInTheDocument();
      expect(within(practiceCard).getByText('Active')).toBeInTheDocument();
    }

    // Check live account
    const liveCard = screen
      .getByText('001-001-7654321-002')
      .closest('.MuiCard-root') as HTMLElement;
    expect(liveCard).toBeInTheDocument();
    if (liveCard) {
      expect(within(liveCard).getByText('Live')).toBeInTheDocument();
      expect(within(liveCard).getByText('$5,000.00')).toBeInTheDocument();
      expect(within(liveCard).getByText('Inactive')).toBeInTheDocument();
    }
  });

  it('displays no data message when no accounts exist', async () => {
    queueAccountsResponse([]);

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/No accounts found/i)).toBeInTheDocument();
    });
  });

  it('opens add account dialog when Add Account button is clicked', async () => {
    queueAccountsResponse(mockAccounts);

    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('001-001-1234567-001')).toBeInTheDocument();
    });

    const addButton = screen.getByRole('button', { name: /Add Account/i });
    await user.click(addButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByLabelText(/Account ID/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/API Token/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/API Type/i)).toBeInTheDocument();
    });
  });

  it(
    'submits new account form successfully',
    async () => {
      const newAccount = {
        id: 3,
        account_id: '001-001-9999999-003',
        api_type: 'practice' as const,
        currency: 'USD',
        balance: 0,
        margin_used: 0,
        margin_available: 0,
        is_active: true,
      } satisfies (typeof mockAccounts)[number];

      queueAccountsResponse(mockAccounts);
      queueJsonResponse({ method: 'POST', url: '/api/accounts/' }, newAccount);
      queueAccountsResponse([...mockAccounts, newAccount]);

      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('001-001-1234567-001')).toBeInTheDocument();
      });

      // Open dialog
      const addButton = screen.getByRole('button', { name: /Add Account/i });
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Fill form
      const accountIdInput = screen.getByLabelText(/Account ID/i);
      const apiTokenInput = screen.getByLabelText(/API Token/i);

      await user.clear(accountIdInput);
      await user.type(accountIdInput, '001-001-9999999-003');
      await user.clear(apiTokenInput);
      await user.type(apiTokenInput, 'test-api-token-123');

      // Submit
      const submitButton = screen.getByRole('button', { name: /^Add$/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockShowSuccess).toHaveBeenCalled();
      });

      // Check that the POST request was made with correct data
      const postCalls = mockFetch.mock.calls.filter(
        (call) => call[0] === '/api/accounts/' && call[1]?.method === 'POST'
      );
      expect(postCalls.length).toBeGreaterThan(0);

      const postCall = postCalls[0];
      expect(postCall[1]).toMatchObject({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          Authorization: 'Bearer test-token',
        }),
      });

      const body = JSON.parse(postCall[1].body);
      expect(body).toMatchObject({
        account_id: '001-001-9999999-003',
        api_token: 'test-api-token-123',
        api_type: 'practice',
      });
    },
    LONG_TEST_TIMEOUT
  );

  it('opens edit dialog when edit button is clicked', async () => {
    queueAccountsResponse(mockAccounts);

    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('001-001-1234567-001')).toBeInTheDocument();
    });

    // Find and click edit button for first account
    const editButtons = screen.getAllByLabelText(/Edit Account/i);
    await user.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      const accountIdInput = screen.getByLabelText(
        /Account ID/i
      ) as HTMLInputElement;
      expect(accountIdInput.value).toBe('001-001-1234567-001');
    });
  });

  it('opens delete confirmation when delete button is clicked', async () => {
    queueAccountsResponse(mockAccounts);

    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('001-001-1234567-001')).toBeInTheDocument();
    });

    // Find and click delete button for first account
    const deleteButtons = screen.getAllByLabelText(/Delete Account/i);
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(
        screen.getByText(/Are you sure you want to delete this account/i)
      ).toBeInTheDocument();
    });
  });

  it('deletes account successfully', async () => {
    queueAccountsResponse(mockAccounts);
    queueJsonResponse({ method: 'DELETE', url: '/api/accounts/1/' }, {});
    queueAccountsResponse([mockAccounts[1]]);

    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('001-001-1234567-001')).toBeInTheDocument();
    });

    // Click delete button
    const deleteButtons = screen.getAllByLabelText(/Delete Account/i);
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(
        screen.getByText(/Are you sure you want to delete this account/i)
      ).toBeInTheDocument();
    });

    // Confirm delete
    const confirmButton = screen.getByRole('button', { name: /Delete/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(mockShowSuccess).toHaveBeenCalled();
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/accounts/1/',
        expect.objectContaining({
          method: 'DELETE',
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });
  });

  it('shows error when fetch fails', async () => {
    queueNetworkError(
      { method: 'GET', url: '/api/accounts/' },
      new Error('Network error')
    );

    renderComponent();

    await waitFor(() => {
      expect(mockShowError).toHaveBeenCalled();
    });
  });

  it('validates required fields in add form', async () => {
    queueAccountsResponse(mockAccounts);

    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('001-001-1234567-001')).toBeInTheDocument();
    });

    // Open dialog
    const addButton = screen.getByRole('button', { name: /Add Account/i });
    await user.click(addButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    // Try to submit without filling fields
    const submitButton = screen.getByRole('button', { name: /^Add$/i });
    await user.click(submitButton);

    // Should show validation errors
    await waitFor(() => {
      const errors = screen.getAllByText(/This field is required/i);
      expect(errors.length).toBeGreaterThan(0);
    });
  });

  it('displays position differentiation button for each account', async () => {
    queueAccountsResponse(mockAccounts);

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('001-001-1234567-001')).toBeInTheDocument();
    });

    const positionDiffButtons = screen.getAllByLabelText(
      /Position Differentiation/i
    );
    expect(positionDiffButtons).toHaveLength(2);
  });

  it('opens position differentiation dialog when settings button is clicked', async () => {
    queueAccountsResponse(mockAccounts);

    const user = userEvent.setup();
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('001-001-1234567-001')).toBeInTheDocument();
    });

    queuePositionSettingsResponse(1, {
      enable_position_differentiation: false,
      position_diff_increment: 1,
      position_diff_pattern: 'increment',
    });

    // Find and click position differentiation button for first account
    const positionDiffButtons = screen.getAllByLabelText(
      /Position Differentiation/i
    );
    await user.click(positionDiffButtons[0]);

    // Wait for dialog to open - just check the title appears
    await waitFor(
      () => {
        expect(
          screen.getByText('Position Differentiation')
        ).toBeInTheDocument();
      },
      { timeout: 5000 }
    );
  });
});
