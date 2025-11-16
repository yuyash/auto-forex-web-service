/**
 * useWebSocketConnection Hook
 *
 * Manages WebSocket connection state and provides connection status information.
 * Tracks connection state, reconnection attempts, and handles fallback to polling.
 *
 * Requirements: 3.5, 8.1, 8.2
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { TaskStatusWebSocket } from '../services/websocket/TaskStatusWebSocket';
import { ConnectionState } from '../components/common/WebSocketConnectionStatus';
import { useToast } from '../components/common';

interface UseWebSocketConnectionOptions {
  token: string | null;
  enabled?: boolean;
  onConnectionChange?: (state: ConnectionState) => void;
}

interface UseWebSocketConnectionReturn {
  connectionState: ConnectionState;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
}

/**
 * Hook to manage WebSocket connection state and lifecycle
 */
export const useWebSocketConnection = ({
  token,
  enabled = true,
  onConnectionChange,
}: UseWebSocketConnectionOptions): UseWebSocketConnectionReturn => {
  const [connectionState, setConnectionState] = useState<ConnectionState>(
    ConnectionState.OFFLINE
  );
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const wsRef = useRef<TaskStatusWebSocket | null>(null);
  const checkIntervalRef = useRef<number | null>(null);
  const maxReconnectAttempts = 5;
  const { showWarning } = useToast();
  const hasShownOfflineWarning = useRef(false);

  /**
   * Check WebSocket connection state periodically
   */
  const checkConnectionState = useCallback(() => {
    if (!wsRef.current) {
      setConnectionState(ConnectionState.OFFLINE);
      setReconnectAttempts(0);
      return;
    }

    const isConnected = wsRef.current.isConnected();
    const attempts = wsRef.current.getReconnectAttempts();

    setReconnectAttempts(attempts);

    if (isConnected) {
      setConnectionState(ConnectionState.CONNECTED);
      // Reset warning flag when connected
      hasShownOfflineWarning.current = false;
    } else if (attempts > 0 && attempts < maxReconnectAttempts) {
      setConnectionState(ConnectionState.RECONNECTING);
    } else if (attempts >= maxReconnectAttempts) {
      setConnectionState(ConnectionState.OFFLINE);

      // Show warning only once when going offline
      if (!hasShownOfflineWarning.current) {
        showWarning(
          'WebSocket connection failed. Using polling fallback for updates.'
        );
        hasShownOfflineWarning.current = true;
      }
    } else {
      // Initial state or disconnected without reconnection attempts
      setConnectionState(ConnectionState.OFFLINE);
    }
  }, [maxReconnectAttempts, showWarning]);

  /**
   * Initialize WebSocket connection
   */
  useEffect(() => {
    if (!enabled || !token) {
      // Clean up if disabled or no token
      if (wsRef.current) {
        wsRef.current.disconnect();
        wsRef.current = null;
      }
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setConnectionState(ConnectionState.OFFLINE);

      setReconnectAttempts(0);
      return;
    }

    // Create WebSocket instance
    if (!wsRef.current) {
      wsRef.current = new TaskStatusWebSocket();
    }

    // Connect to WebSocket
    wsRef.current.connect(token);

    // Start checking connection state periodically
    checkIntervalRef.current = window.setInterval(() => {
      checkConnectionState();
    }, 1000); // Check every second

    // Initial check
    checkConnectionState();

    // Cleanup on unmount
    return () => {
      if (checkIntervalRef.current) {
        clearInterval(checkIntervalRef.current);
        checkIntervalRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.disconnect();
        wsRef.current = null;
      }
    };
  }, [enabled, token, checkConnectionState]);

  /**
   * Notify parent component of connection state changes
   */
  useEffect(() => {
    if (onConnectionChange) {
      onConnectionChange(connectionState);
    }
  }, [connectionState, onConnectionChange]);

  return {
    connectionState,
    reconnectAttempts,
    maxReconnectAttempts,
  };
};

export default useWebSocketConnection;
