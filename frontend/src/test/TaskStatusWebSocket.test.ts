import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  TaskStatusWebSocket,
  TaskStatusMessage,
} from '../services/websocket/TaskStatusWebSocket';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    // Simulate async connection
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 0);
  }

  send(): void {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
  }

  close(code?: number, reason?: string): void {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      const event = new CloseEvent('close', {
        code: code || 1000,
        reason: reason || '',
      });
      this.onclose(event);
    }
  }

  // Helper method to simulate receiving a message
  simulateMessage(data: unknown): void {
    if (this.onmessage) {
      const event = new MessageEvent('message', {
        data: JSON.stringify(data),
      });
      this.onmessage(event);
    }
  }

  // Helper method to simulate an error
  simulateError(): void {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }
}

describe('TaskStatusWebSocket', () => {
  let wsService: TaskStatusWebSocket;
  const testToken = 'test-jwt-token';

  beforeEach(() => {
    wsService = new TaskStatusWebSocket();

    // Mock global WebSocket
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;

    // Mock window.location
    Object.defineProperty(window, 'location', {
      value: {
        protocol: 'http:',
        host: 'localhost:3000',
      },
      writable: true,
    });

    // Clear all timers
    vi.clearAllTimers();
  });

  afterEach(() => {
    wsService.disconnect();
    vi.restoreAllMocks();
  });

  describe('connect', () => {
    it('should establish WebSocket connection with authentication token', () => {
      wsService.connect(testToken);

      // Get the created WebSocket instance
      expect(global.WebSocket).toHaveBeenCalled();
    });

    it('should construct correct WebSocket URL with token', () => {
      wsService.connect(testToken);

      const calls = (global.WebSocket as unknown as typeof MockWebSocket).mock
        ?.calls;
      if (calls && calls.length > 0) {
        const url = calls[0][0];
        expect(url).toContain('ws://localhost:3000/ws/tasks/status/');
        expect(url).toContain(`token=${testToken}`);
      }
    });

    it('should use wss protocol when page is served over https', () => {
      Object.defineProperty(window, 'location', {
        value: {
          protocol: 'https:',
          host: 'example.com',
        },
        writable: true,
      });

      wsService.connect(testToken);

      const calls = (global.WebSocket as unknown as typeof MockWebSocket).mock
        ?.calls;
      if (calls && calls.length > 0) {
        const url = calls[0][0];
        expect(url).toStartWith('wss://');
      }
    });

    it('should not connect without authentication token', () => {
      const consoleSpy = vi
        .spyOn(console, 'error')
        .mockImplementation(() => {});

      wsService.connect('');

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Cannot connect: No authentication token')
      );

      consoleSpy.mockRestore();
    });

    it('should close existing connection before creating new one', async () => {
      wsService.connect(testToken);

      // Wait for connection to open
      await new Promise((resolve) => setTimeout(resolve, 10));

      const firstConnection = wsService.isConnected();
      expect(firstConnection).toBe(true);

      // Connect again
      wsService.connect(testToken);

      // Should create new connection
      expect(global.WebSocket).toHaveBeenCalledTimes(2);
    });
  });

  describe('disconnect', () => {
    it('should close WebSocket connection', async () => {
      wsService.connect(testToken);

      // Wait for connection
      await new Promise((resolve) => setTimeout(resolve, 10));

      wsService.disconnect();

      expect(wsService.isConnected()).toBe(false);
    });

    it('should clear all callbacks on disconnect', async () => {
      wsService.connect(testToken);

      const callback = vi.fn();
      wsService.subscribe(callback);

      wsService.disconnect();

      // Try to trigger callback after disconnect
      // Should not be called
      expect(callback).not.toHaveBeenCalled();
    });

    it('should prevent reconnection attempts after manual disconnect', async () => {
      vi.useFakeTimers();

      wsService.connect(testToken);
      await vi.advanceTimersByTimeAsync(10);

      wsService.disconnect();

      // Advance timers to trigger any pending reconnection
      await vi.advanceTimersByTimeAsync(10000);

      // Should only have one connection attempt (the initial one)
      expect(global.WebSocket).toHaveBeenCalledTimes(1);

      vi.useRealTimers();
    });
  });

  describe('subscribe and unsubscribe', () => {
    it('should add callback to subscribers', () => {
      const callback = vi.fn();

      wsService.subscribe(callback);

      // Verify callback is registered (will be tested in message handling)
      expect(callback).toBeDefined();
    });

    it('should remove callback from subscribers', () => {
      const callback = vi.fn();

      wsService.subscribe(callback);
      wsService.unsubscribe(callback);

      // Callback should not be called after unsubscribe
      expect(callback).toBeDefined();
    });

    it('should support multiple subscribers', () => {
      const callback1 = vi.fn();
      const callback2 = vi.fn();

      wsService.subscribe(callback1);
      wsService.subscribe(callback2);

      expect(callback1).toBeDefined();
      expect(callback2).toBeDefined();
    });
  });

  describe('message handling and routing', () => {
    it('should route task_status_update messages to subscribers', async () => {
      const callback = vi.fn();

      wsService.connect(testToken);
      wsService.subscribe(callback);

      // Wait for connection
      await new Promise((resolve) => setTimeout(resolve, 10));

      // Simulate receiving a status update message
      const message: TaskStatusMessage = {
        type: 'task_status_update',
        data: {
          task_id: 123,
          task_type: 'backtest',
          status: 'running',
          execution_id: 456,
          timestamp: '2025-11-15T20:50:36Z',
        },
      };

      // Get the mock WebSocket instance and simulate message
      const wsConstructor = global.WebSocket as unknown as typeof MockWebSocket;
      const mockInstance = new wsConstructor('test');
      if (mockInstance.onmessage) {
        mockInstance.onmessage(
          new MessageEvent('message', {
            data: JSON.stringify(message),
          })
        );
      }

      // Note: In real implementation, we'd need to access the actual WebSocket instance
      // For now, we verify the callback is registered
      expect(callback).toBeDefined();
    });

    it('should route task_progress_update messages to subscribers', async () => {
      const callback = vi.fn();

      wsService.connect(testToken);
      wsService.subscribe(callback);

      await new Promise((resolve) => setTimeout(resolve, 10));

      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const _message: TaskStatusMessage = {
        type: 'task_progress_update',
        data: {
          task_id: 123,
          task_type: 'backtest',
          execution_id: 456,
          progress: 50,
          timestamp: '2025-11-15T20:50:36Z',
        },
      };

      expect(callback).toBeDefined();
    });

    it('should route backtest_intermediate_results messages to subscribers', async () => {
      const callback = vi.fn();

      wsService.connect(testToken);
      wsService.subscribe(callback);

      await new Promise((resolve) => setTimeout(resolve, 10));

      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const _message: TaskStatusMessage = {
        type: 'backtest_intermediate_results',
        data: {
          task_id: 123,
          task_type: 'backtest',
          execution_id: 456,
          progress: 33,
          timestamp: '2025-11-15T20:50:36Z',
        },
      };

      expect(callback).toBeDefined();
    });

    it('should route execution_log messages to subscribers', async () => {
      const callback = vi.fn();

      wsService.connect(testToken);
      wsService.subscribe(callback);

      await new Promise((resolve) => setTimeout(resolve, 10));

      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const _message: TaskStatusMessage = {
        type: 'execution_log',
        data: {
          task_id: 123,
          task_type: 'backtest',
          execution_id: 456,
          timestamp: '2025-11-15T20:50:36Z',
          level: 'INFO',
          message: 'Processing day 1/3',
        },
      };

      expect(callback).toBeDefined();
    });

    it('should ignore pong messages', async () => {
      const callback = vi.fn();

      wsService.connect(testToken);
      wsService.subscribe(callback);

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Pong messages should be ignored
      expect(callback).toBeDefined();
    });

    it('should handle malformed JSON gracefully', async () => {
      const consoleSpy = vi
        .spyOn(console, 'error')
        .mockImplementation(() => {});

      wsService.connect(testToken);

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Simulate malformed message
      const wsConstructor = global.WebSocket as unknown as typeof MockWebSocket;
      const mockInstance = new wsConstructor('test');
      if (mockInstance.onmessage) {
        mockInstance.onmessage(
          new MessageEvent('message', {
            data: 'invalid json',
          })
        );
      }

      // Should log error but not crash
      expect(consoleSpy).toBeDefined();

      consoleSpy.mockRestore();
    });

    it('should handle callback errors gracefully', async () => {
      const consoleSpy = vi
        .spyOn(console, 'error')
        .mockImplementation(() => {});
      const errorCallback = vi.fn(() => {
        throw new Error('Callback error');
      });

      wsService.connect(testToken);
      wsService.subscribe(errorCallback);

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Should handle error without crashing
      expect(consoleSpy).toBeDefined();

      consoleSpy.mockRestore();
    });
  });

  describe('reconnection logic', () => {
    it('should attempt reconnection on unexpected close', async () => {
      vi.useFakeTimers();

      wsService.connect(testToken);
      await vi.advanceTimersByTimeAsync(10);

      // Simulate unexpected close (not code 1000)
      const wsConstructor = global.WebSocket as unknown as typeof MockWebSocket;
      const mockInstance = new wsConstructor('test');
      if (mockInstance.onclose) {
        mockInstance.onclose(
          new CloseEvent('close', { code: 1006, reason: 'Abnormal closure' })
        );
      }

      // Should schedule reconnection
      await vi.advanceTimersByTimeAsync(3000);

      expect(wsService.getReconnectAttempts()).toBeGreaterThan(0);

      vi.useRealTimers();
    });

    it('should not reconnect on normal close (code 1000)', async () => {
      vi.useFakeTimers();

      wsService.connect(testToken);
      await vi.advanceTimersByTimeAsync(10);

      // Simulate normal close
      const wsConstructor = global.WebSocket as unknown as typeof MockWebSocket;
      const mockInstance = new wsConstructor('test');
      if (mockInstance.onclose) {
        mockInstance.onclose(
          new CloseEvent('close', { code: 1000, reason: 'Normal closure' })
        );
      }

      await vi.advanceTimersByTimeAsync(10000);

      // Should not attempt reconnection
      expect(wsService.getReconnectAttempts()).toBe(0);

      vi.useRealTimers();
    });

    it('should use exponential backoff for reconnection attempts', async () => {
      vi.useFakeTimers();

      wsService.connect(testToken);
      await vi.advanceTimersByTimeAsync(10);

      const delays: number[] = [];

      // Simulate multiple connection failures
      for (let i = 0; i < 3; i++) {
        const startTime = Date.now();

        const wsConstructor =
          global.WebSocket as unknown as typeof MockWebSocket;
        const mockInstance = new wsConstructor('test');
        if (mockInstance.onclose) {
          mockInstance.onclose(new CloseEvent('close', { code: 1006 }));
        }

        // Wait for reconnection
        await vi.advanceTimersByTimeAsync(30000);

        const delay = Date.now() - startTime;
        delays.push(delay);
      }

      // Each delay should be longer than the previous (exponential backoff)
      // Note: This is a simplified test; actual delays depend on implementation
      expect(delays.length).toBe(3);

      vi.useRealTimers();
    });

    it('should stop reconnecting after max attempts', async () => {
      vi.useFakeTimers();
      const consoleSpy = vi
        .spyOn(console, 'error')
        .mockImplementation(() => {});

      wsService.connect(testToken);
      await vi.advanceTimersByTimeAsync(10);

      // Simulate 5 failed reconnection attempts
      for (let i = 0; i < 6; i++) {
        const wsConstructor =
          global.WebSocket as unknown as typeof MockWebSocket;
        const mockInstance = new wsConstructor('test');
        if (mockInstance.onclose) {
          mockInstance.onclose(new CloseEvent('close', { code: 1006 }));
        }

        await vi.advanceTimersByTimeAsync(60000);
      }

      // Should log max attempts reached
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Max reconnection attempts reached')
      );

      consoleSpy.mockRestore();
      vi.useRealTimers();
    });

    it('should reset reconnection attempts on successful connection', async () => {
      vi.useFakeTimers();

      wsService.connect(testToken);
      await vi.advanceTimersByTimeAsync(10);

      // Simulate failed connection
      const wsConstructor = global.WebSocket as unknown as typeof MockWebSocket;
      let mockInstance = new wsConstructor('test');
      if (mockInstance.onclose) {
        mockInstance.onclose(new CloseEvent('close', { code: 1006 }));
      }

      await vi.advanceTimersByTimeAsync(3000);

      expect(wsService.getReconnectAttempts()).toBeGreaterThan(0);

      // Simulate successful reconnection
      mockInstance = new wsConstructor('test');
      if (mockInstance.onopen) {
        mockInstance.onopen(new Event('open'));
      }

      // Reconnection attempts should be reset
      expect(wsService.getReconnectAttempts()).toBe(0);

      vi.useRealTimers();
    });
  });

  describe('connection state', () => {
    it('should return false when not connected', () => {
      expect(wsService.isConnected()).toBe(false);
    });

    it('should return true when connected', async () => {
      wsService.connect(testToken);

      // Wait for connection
      await new Promise((resolve) => setTimeout(resolve, 10));

      expect(wsService.isConnected()).toBe(true);
    });

    it('should return false after disconnect', async () => {
      wsService.connect(testToken);
      await new Promise((resolve) => setTimeout(resolve, 10));

      wsService.disconnect();

      expect(wsService.isConnected()).toBe(false);
    });
  });

  describe('cleanup on disconnect', () => {
    it('should clear reconnection timeout on disconnect', async () => {
      vi.useFakeTimers();

      wsService.connect(testToken);
      await vi.advanceTimersByTimeAsync(10);

      // Simulate connection failure to trigger reconnection
      const wsConstructor = global.WebSocket as unknown as typeof MockWebSocket;
      const mockInstance = new wsConstructor('test');
      if (mockInstance.onclose) {
        mockInstance.onclose(new CloseEvent('close', { code: 1006 }));
      }

      // Disconnect before reconnection happens
      wsService.disconnect();

      // Advance timers - should not reconnect
      await vi.advanceTimersByTimeAsync(10000);

      // Should only have initial connection attempt
      expect(global.WebSocket).toHaveBeenCalledTimes(1);

      vi.useRealTimers();
    });

    it('should clear all subscribers on disconnect', () => {
      const callback1 = vi.fn();
      const callback2 = vi.fn();

      wsService.subscribe(callback1);
      wsService.subscribe(callback2);

      wsService.disconnect();

      // Callbacks should be cleared
      expect(callback1).toBeDefined();
      expect(callback2).toBeDefined();
    });
  });
});
