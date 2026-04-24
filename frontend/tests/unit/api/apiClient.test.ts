import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockAxiosRequest, mockHandleAuthErrorStatus } = vi.hoisted(() => ({
  mockAxiosRequest: vi.fn(),
  mockHandleAuthErrorStatus: vi.fn(),
}));

vi.mock('axios', () => ({
  default: {
    request: mockAxiosRequest,
    isAxiosError: (error: unknown) =>
      Boolean(error && typeof error === 'object' && 'isAxiosError' in error),
  },
}));

vi.mock('../../../src/utils/authEvents', () => ({
  handleAuthErrorStatus: mockHandleAuthErrorStatus,
}));

import { api, ApiError } from '../../../src/api/apiClient';
import { clearAuthToken } from '../../../src/api/client';

describe('apiClient', () => {
  beforeEach(() => {
    clearAuthToken();
    vi.clearAllMocks();
  });

  it('notifies the auth layer when an HTTP response is rejected', async () => {
    mockAxiosRequest.mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        status: 401,
        statusText: 'Unauthorized',
        data: { error: 'Invalid or expired refresh token.' },
      },
    });

    await expect(
      api.post('/api/accounts/auth/refresh', {})
    ).rejects.toBeInstanceOf(ApiError);

    expect(mockHandleAuthErrorStatus).toHaveBeenCalledWith(401, {
      source: 'http',
      status: 401,
      url: '/api/accounts/auth/refresh',
      context: 'api_client',
    });
  });
});
