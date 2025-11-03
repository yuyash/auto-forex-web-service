import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import useMarketData from '../hooks/useMarketData';
import type { TickData } from '../types/chart';

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  readyState: number = WebSocket.CONNECTING;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    // Simulate connection opening after a short delay
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 10);
  }

  send(data: string): void {
    console.log('Mock WebSocket send:', data);
  }

  close(): void {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  static reset(): void {
    MockWebSocket.instances = [];
  }
}

describe('useMarketData', () => {
  beforeEach(() => {
    // Replace global WebSocket with mock
    vi.stubGlobal('WebSocket', MockWebSocket);
    MockWebSocket.reset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllTimers();
  });

  it('should initialize with null tick data and disconnected state', () => {
    const { result } = renderHook(() =>
      useMarketData({
        accountId: 'test-account',
        instrument: 'EUR_USD',
      })
    );

    expect(result.current.tickData).toBeNull();
    expect(result.current.isConnected).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('should connect to WebSocket with correct URL', async () => {
    renderHook(() =>
      useMarketData({
        accountId: 'test-account',
        instrument: 'EUR_USD',
      })
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
      expect(MockWebSocket.instances[0].url).toContain(
        '/ws/market-data/test-account/EUR_USD/'
      );
    });
  });

  it('should update connection status when WebSocket opens', async () => {
    const { result } = renderHook(() =>
      useMarketData({
        accountId: 'test-account',
        instrument: 'EUR_USD',
      })
    );

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });
  });

  it('should receive and update tick data', async () => {
    const { result } = renderHook(() =>
      useMarketData({
        accountId: 'test-account',
        instrument: 'EUR_USD',
      })
    );

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const mockTick: TickData = {
      instrument: 'EUR_USD',
      time: '2024-01-01T12:00:00Z',
      bid: 1.1,
      ask: 1.11,
      mid: 1.105,
      spread: 0.01,
    };

    // Simulate receiving a message
    const ws = MockWebSocket.instances[0];
    if (ws.onmessage) {
      ws.onmessage(
        new MessageEvent('message', {
          data: JSON.stringify(mockTick),
        })
      );
    }

    await waitFor(() => {
      expect(result.current.tickData).toEqual(mockTick);
    });
  });

  it('should throttle updates to max once per 100ms', async () => {
    const { result } = renderHook(() =>
      useMarketData({
        accountId: 'test-account',
        instrument: 'EUR_USD',
        throttleMs: 100,
      })
    );

    // Wait for connection
    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const ws = MockWebSocket.instances[0];

    // Send first tick
    const tick1: TickData = {
      instrument: 'EUR_USD',
      time: '2024-01-01T12:00:00Z',
      bid: 1.1,
      ask: 1.11,
      mid: 1.105,
      spread: 0.01,
    };

    if (ws.onmessage) {
      ws.onmessage(
        new MessageEvent('message', { data: JSON.stringify(tick1) })
      );
    }

    // First tick should be applied immediately
    await waitFor(() => {
      expect(result.current.tickData?.mid).toBe(1.105);
    });

    // Send multiple ticks rapidly
    const tick2: TickData = {
      ...tick1,
      mid: 1.106,
    };

    const tick3: TickData = {
      ...tick1,
      mid: 1.107,
    };

    if (ws.onmessage) {
      ws.onmessage(
        new MessageEvent('message', { data: JSON.stringify(tick2) })
      );
      ws.onmessage(
        new MessageEvent('message', { data: JSON.stringify(tick3) })
      );
    }

    // Wait for throttle period to pass
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Last tick should be applied after throttle period
    await waitFor(() => {
      expect(result.current.tickData?.mid).toBe(1.107);
    });
  });

  it('should handle WebSocket errors', async () => {
    const onError = vi.fn();

    const { result } = renderHook(() =>
      useMarketData({
        accountId: 'test-account',
        instrument: 'EUR_USD',
        onError,
      })
    );

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const ws = MockWebSocket.instances[0];
    if (ws.onerror) {
      ws.onerror(new ErrorEvent('error', { message: 'Connection failed' }));
    }

    await waitFor(
      () => {
        expect(result.current.error).not.toBeNull();
        expect(onError).toHaveBeenCalled();
      },
      { timeout: 1000 }
    );
  });

  it('should call onConnect callback when connection opens', async () => {
    const onConnect = vi.fn();

    renderHook(() =>
      useMarketData({
        accountId: 'test-account',
        instrument: 'EUR_USD',
        onConnect,
      })
    );

    await waitFor(
      () => {
        expect(onConnect).toHaveBeenCalled();
      },
      { timeout: 1000 }
    );
  });

  it('should call onDisconnect callback when connection closes', async () => {
    const onDisconnect = vi.fn();

    const { result } = renderHook(() =>
      useMarketData({
        accountId: 'test-account',
        instrument: 'EUR_USD',
        onDisconnect,
      })
    );

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const ws = MockWebSocket.instances[0];
    ws.close();

    await waitFor(
      () => {
        expect(onDisconnect).toHaveBeenCalled();
      },
      { timeout: 1000 }
    );
  });

  it('should provide reconnect function', async () => {
    const { result } = renderHook(() =>
      useMarketData({
        accountId: 'test-account',
        instrument: 'EUR_USD',
      })
    );

    await waitFor(
      () => {
        expect(result.current.isConnected).toBe(true);
      },
      { timeout: 1000 }
    );

    expect(typeof result.current.reconnect).toBe('function');
  });

  it('should clean up WebSocket on unmount', async () => {
    const { unmount } = renderHook(() =>
      useMarketData({
        accountId: 'test-account',
        instrument: 'EUR_USD',
      })
    );

    await waitFor(
      () => {
        expect(MockWebSocket.instances.length).toBe(1);
      },
      { timeout: 1000 }
    );

    const ws = MockWebSocket.instances[0];
    const closeSpy = vi.spyOn(ws, 'close');

    unmount();

    expect(closeSpy).toHaveBeenCalled();
  });

  it('should handle invalid JSON in WebSocket messages', async () => {
    const onError = vi.fn();

    const { result } = renderHook(() =>
      useMarketData({
        accountId: 'test-account',
        instrument: 'EUR_USD',
        onError,
      })
    );

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const ws = MockWebSocket.instances[0];
    if (ws.onmessage) {
      ws.onmessage(
        new MessageEvent('message', {
          data: 'invalid json',
        })
      );
    }

    await waitFor(
      () => {
        expect(result.current.error).not.toBeNull();
        expect(onError).toHaveBeenCalled();
      },
      { timeout: 1000 }
    );
  });
});
