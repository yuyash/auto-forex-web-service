/**
 * Tests for useWebSocketConnection Hook
 *
 * Tests:
 * - Connection state management
 * - Reconnection attempt tracking
 * - State transitions
 * - Cleanup on unmount
 *
 * Requirements: 3.5
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useWebSocketConnection } from '../hooks/useWebSocketConnection';
import { ConnectionState } from '../components/common/WebSocketConnectionStatus';
import { TaskStatusWebSocket } from '../services/websocket/TaskStatusWebSocket';

// Type for mock WebSocket instance
type MockWebSocketInstance = {
  connect: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
  isConnected: ReturnType<typeof vi.fn>;
  getReconnectAttempts: ReturnType<typeof vi.fn>;
};

// Mock the TaskStatusWebSocket
vi.mock('../services/websocket/TaskStatusWebSocket', () => {
  const TaskStatusWebSocket = vi.fn(function (this: MockWebSocketInstance) {
    this.connect = vi.fn();
    this.disconnect = vi.fn();
    this.isConnected = vi.fn().mockReturnValue(false);
    this.getReconnectAttempts = vi.fn().mockReturnValue(0);
  });

  return {
    TaskStatusWebSocket,
  };
});

describe('useWebSocketConnection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Initial State', () => {
    it('should start with offline state when no token provided', () => {
      const { result } = renderHook(() =>
        useWebSocketConnection({
          token: null,
          enabled: true,
        })
      );

      expect(result.current.connectionState).toBe(ConnectionState.OFFLINE);
      expect(result.current.reconnectAttempts).toBe(0);
      expect(result.current.ws).toBeNull();
    });

    it('should start with offline state when disabled', () => {
      const { result } = renderHook(() =>
        useWebSocketConnection({
          token: 'test-token',
          enabled: false,
        })
      );

      expect(result.current.connectionState).toBe(ConnectionState.OFFLINE);
      expect(result.current.reconnectAttempts).toBe(0);
      expect(result.current.ws).toBeNull();
    });

    it('should initialize WebSocket when token provided and enabled', () => {
      const { result } = renderHook(() =>
        useWebSocketConnection({
          token: 'test-token',
          enabled: true,
        })
      );

      expect(TaskStatusWebSocket).toHaveBeenCalled();
      expect(result.current.ws).not.toBeNull();
    });
  });

  describe('Connection State Tracking', () => {
    it('should transition to connected state when WebSocket is connected', async () => {
      vi.mocked(TaskStatusWebSocket).mockImplementation(function (
        this: MockWebSocketInstance
      ) {
        this.connect = vi.fn();
        this.disconnect = vi.fn();
        this.isConnected = vi.fn().mockReturnValue(true);
        this.getReconnectAttempts = vi.fn().mockReturnValue(0);
      } as unknown as typeof TaskStatusWebSocket);

      const { result } = renderHook(() =>
        useWebSocketConnection({
          token: 'test-token',
          enabled: true,
        })
      );

      // Advance timers to trigger connection check
      vi.advanceTimersByTime(1000);

      await waitFor(() => {
        expect(result.current.connectionState).toBe(ConnectionState.CONNECTED);
      });
    });

    it('should transition to reconnecting state when reconnection attempts are in progress', async () => {
      vi.mocked(TaskStatusWebSocket).mockImplementation(function (
        this: MockWebSocketInstance
      ) {
        this.connect = vi.fn();
        this.disconnect = vi.fn();
        this.isConnected = vi.fn().mockReturnValue(false);
        this.getReconnectAttempts = vi.fn().mockReturnValue(2);
      } as unknown as typeof TaskStatusWebSocket);

      const { result } = renderHook(() =>
        useWebSocketConnection({
          token: 'test-token',
          enabled: true,
        })
      );

      // Advance timers to trigger connection check
      vi.advanceTimersByTime(1000);

      await waitFor(() => {
        expect(result.current.connectionState).toBe(
          ConnectionState.RECONNECTING
        );
        expect(result.current.reconnectAttempts).toBe(2);
      });
    });

    it('should transition to offline state when max reconnection attempts reached', async () => {
      vi.mocked(TaskStatusWebSocket).mockImplementation(function (
        this: MockWebSocketInstance
      ) {
        this.connect = vi.fn();
        this.disconnect = vi.fn();
        this.isConnected = vi.fn().mockReturnValue(false);
        this.getReconnectAttempts = vi.fn().mockReturnValue(5);
      } as unknown as typeof TaskStatusWebSocket);

      const { result } = renderHook(() =>
        useWebSocketConnection({
          token: 'test-token',
          enabled: true,
        })
      );

      // Advance timers to trigger connection check
      vi.advanceTimersByTime(1000);

      await waitFor(() => {
        expect(result.current.connectionState).toBe(ConnectionState.OFFLINE);
        expect(result.current.reconnectAttempts).toBe(5);
      });
    });
  });

  describe('Connection State Changes', () => {
    it('should update state when connection is established', async () => {
      const isConnectedMock = vi.fn().mockReturnValue(false);

      vi.mocked(TaskStatusWebSocket).mockImplementation(function (
        this: MockWebSocketInstance
      ) {
        this.connect = vi.fn();
        this.disconnect = vi.fn();
        this.isConnected = isConnectedMock;
        this.getReconnectAttempts = vi.fn().mockReturnValue(0);
      } as unknown as typeof TaskStatusWebSocket);

      const { result } = renderHook(() =>
        useWebSocketConnection({
          token: 'test-token',
          enabled: true,
        })
      );

      // Initially offline
      vi.advanceTimersByTime(1000);
      await waitFor(() => {
        expect(result.current.connectionState).toBe(ConnectionState.OFFLINE);
      });

      // Simulate connection established
      isConnectedMock.mockReturnValue(true);
      vi.advanceTimersByTime(1000);

      await waitFor(() => {
        expect(result.current.connectionState).toBe(ConnectionState.CONNECTED);
      });
    });

    it('should update state when connection is lost', async () => {
      const isConnectedMock = vi.fn().mockReturnValue(true);
      const getReconnectAttemptsMock = vi.fn().mockReturnValue(0);

      vi.mocked(TaskStatusWebSocket).mockImplementation(function (
        this: MockWebSocketInstance
      ) {
        this.connect = vi.fn();
        this.disconnect = vi.fn();
        this.isConnected = isConnectedMock;
        this.getReconnectAttempts = getReconnectAttemptsMock;
      } as unknown as typeof TaskStatusWebSocket);

      const { result } = renderHook(() =>
        useWebSocketConnection({
          token: 'test-token',
          enabled: true,
        })
      );

      // Initially connected
      vi.advanceTimersByTime(1000);
      await waitFor(() => {
        expect(result.current.connectionState).toBe(ConnectionState.CONNECTED);
      });

      // Simulate connection lost and reconnecting
      isConnectedMock.mockReturnValue(false);
      getReconnectAttemptsMock.mockReturnValue(1);
      vi.advanceTimersByTime(1000);

      await waitFor(() => {
        expect(result.current.connectionState).toBe(
          ConnectionState.RECONNECTING
        );
      });
    });
  });

  describe('Cleanup', () => {
    it('should disconnect WebSocket on unmount', () => {
      const disconnectMock = vi.fn();

      vi.mocked(TaskStatusWebSocket).mockImplementation(function (
        this: MockWebSocketInstance
      ) {
        this.connect = vi.fn();
        this.disconnect = disconnectMock;
        this.isConnected = vi.fn().mockReturnValue(false);
        this.getReconnectAttempts = vi.fn().mockReturnValue(0);
      } as unknown as typeof TaskStatusWebSocket);

      const { unmount } = renderHook(() =>
        useWebSocketConnection({
          token: 'test-token',
          enabled: true,
        })
      );

      unmount();

      expect(disconnectMock).toHaveBeenCalled();
    });

    it('should clear interval on unmount', () => {
      const clearIntervalSpy = vi.spyOn(window, 'clearInterval');

      const { unmount } = renderHook(() =>
        useWebSocketConnection({
          token: 'test-token',
          enabled: true,
        })
      );

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
    });

    it('should disconnect when disabled', async () => {
      const disconnectMock = vi.fn();

      vi.mocked(TaskStatusWebSocket).mockImplementation(function (
        this: MockWebSocketInstance
      ) {
        this.connect = vi.fn();
        this.disconnect = disconnectMock;
        this.isConnected = vi.fn().mockReturnValue(true);
        this.getReconnectAttempts = vi.fn().mockReturnValue(0);
      } as unknown as typeof TaskStatusWebSocket);

      const { rerender } = renderHook(
        ({ enabled }) =>
          useWebSocketConnection({
            token: 'test-token',
            enabled,
          }),
        {
          initialProps: { enabled: true },
        }
      );

      // Disable connection
      rerender({ enabled: false });

      await waitFor(() => {
        expect(disconnectMock).toHaveBeenCalled();
      });
    });
  });

  describe('Connection Change Callback', () => {
    it('should call onConnectionChange when state changes', async () => {
      const onConnectionChange = vi.fn();
      const isConnectedMock = vi.fn().mockReturnValue(false);

      vi.mocked(TaskStatusWebSocket).mockImplementation(function (
        this: MockWebSocketInstance
      ) {
        this.connect = vi.fn();
        this.disconnect = vi.fn();
        this.isConnected = isConnectedMock;
        this.getReconnectAttempts = vi.fn().mockReturnValue(0);
      } as unknown as typeof TaskStatusWebSocket);

      renderHook(() =>
        useWebSocketConnection({
          token: 'test-token',
          enabled: true,
          onConnectionChange,
        })
      );

      // Initial state
      await waitFor(() => {
        expect(onConnectionChange).toHaveBeenCalledWith(
          ConnectionState.OFFLINE
        );
      });

      // Simulate connection
      isConnectedMock.mockReturnValue(true);
      vi.advanceTimersByTime(1000);

      await waitFor(() => {
        expect(onConnectionChange).toHaveBeenCalledWith(
          ConnectionState.CONNECTED
        );
      });
    });
  });

  describe('Max Reconnect Attempts', () => {
    it('should return correct maxReconnectAttempts value', () => {
      const { result } = renderHook(() =>
        useWebSocketConnection({
          token: 'test-token',
          enabled: true,
        })
      );

      expect(result.current.maxReconnectAttempts).toBe(5);
    });
  });
});
