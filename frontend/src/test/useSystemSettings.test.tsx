import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useSystemSettings } from '../hooks/useSystemSettings';

describe('useSystemSettings', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should fetch system settings successfully', async () => {
    const mockSettings = {
      registration_enabled: true,
      login_enabled: true,
    };

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => mockSettings,
    } as Response);

    const { result } = renderHook(() => useSystemSettings());

    expect(result.current.loading).toBe(true);
    expect(result.current.settings).toBe(null);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.settings).toEqual(mockSettings);
    expect(result.current.error).toBe(null);
    expect(fetchMock).toHaveBeenCalledWith('/api/system/settings/public');
  });

  it('should handle fetch error', async () => {
    fetchMock.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useSystemSettings());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.settings).toBe(null);
    expect(result.current.error).toBe('Network error');
  });

  it('should handle non-ok response', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
    } as Response);

    const { result } = renderHook(() => useSystemSettings());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.settings).toBe(null);
    expect(result.current.error).toBe('Failed to fetch system settings');
  });

  it('should refetch settings when refetch is called', async () => {
    const mockSettings = {
      registration_enabled: false,
      login_enabled: true,
    };

    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => mockSettings,
    } as Response);

    const { result } = renderHook(() => useSystemSettings());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Call refetch
    await result.current.refetch();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
