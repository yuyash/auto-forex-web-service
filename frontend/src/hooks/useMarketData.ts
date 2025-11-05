import { useEffect, useRef, useState, useCallback } from 'react';
import type { TickData } from '../types/chart';

interface UseMarketDataOptions {
  accountId?: string;
  instrument?: string;
  throttleMs?: number;
  onError?: (error: Error) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

interface UseMarketDataReturn {
  tickData: TickData | null;
  isConnected: boolean;
  error: Error | null;
  reconnect: () => void;
}

/**
 * Custom hook to connect to market data WebSocket and receive real-time tick updates
 * with throttling to prevent excessive updates
 *
 * @param options - Configuration options for the WebSocket connection
 * @returns Object containing tick data, connection status, error state, and reconnect function
 */
const useMarketData = ({
  accountId,
  instrument,
  throttleMs = 100,
  onError,
  onConnect,
  onDisconnect,
}: UseMarketDataOptions): UseMarketDataReturn => {
  const [tickData, setTickData] = useState<TickData | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const lastUpdateTimeRef = useRef<number>(0);
  const pendingTickRef = useRef<TickData | null>(null);
  const throttleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const maxReconnectAttempts = 5;
  const reconnectDelayMs = 2000;

  // Throttled update function
  const updateTickData = useCallback(
    (newTick: TickData) => {
      const now = Date.now();
      const timeSinceLastUpdate = now - lastUpdateTimeRef.current;

      if (timeSinceLastUpdate >= throttleMs) {
        // Update immediately if enough time has passed
        setTickData(newTick);
        lastUpdateTimeRef.current = now;
        pendingTickRef.current = null;

        // Clear any pending throttle timer
        if (throttleTimerRef.current) {
          clearTimeout(throttleTimerRef.current);
          throttleTimerRef.current = null;
        }
      } else {
        // Store the pending tick and schedule an update
        pendingTickRef.current = newTick;

        if (!throttleTimerRef.current) {
          const remainingTime = throttleMs - timeSinceLastUpdate;
          throttleTimerRef.current = setTimeout(() => {
            if (pendingTickRef.current) {
              setTickData(pendingTickRef.current);
              lastUpdateTimeRef.current = Date.now();
              pendingTickRef.current = null;
            }
            throttleTimerRef.current = null;
          }, remainingTime);
        }
      }
    },
    [throttleMs]
  );

  // Connect to WebSocket
  const connectRef = useRef<(() => void) | null>(null);

  const connect = useCallback(() => {
    try {
      // Don't connect if accountId or instrument is not provided
      if (!accountId || !instrument) {
        return;
      }

      // Close existing connection if any
      if (wsRef.current) {
        wsRef.current.close();
      }

      // Get JWT token from localStorage
      const token = localStorage.getItem('token');

      // Determine protocol (ws or wss based on current page protocol)
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

      // Add token to WebSocket URL as query parameter
      const wsUrl = token
        ? `${protocol}//${window.location.host}/ws/market-data/${accountId}/${instrument}/?token=${token}`
        : `${protocol}//${window.location.host}/ws/market-data/${accountId}/${instrument}/`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
        if (onConnect) {
          onConnect();
        }
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          // Handle different message types from the backend
          if (message.type === 'tick' && message.data) {
            // Single tick update
            updateTickData(message.data as TickData);
          } else if (message.type === 'tick_batch' && message.data) {
            // Batch of ticks - use the last one
            const ticks = message.data as TickData[];
            if (ticks.length > 0) {
              updateTickData(ticks[ticks.length - 1]);
            }
          } else if (message.type === 'pong') {
            // Pong response to ping - ignore
          } else if (message.type === 'error') {
            // Error message from backend
            const errorMsg =
              message.data?.message || 'Unknown error from server';
            const wsError = new Error(errorMsg);
            setError(wsError);
            if (onError) {
              onError(wsError);
            }
          } else {
            // Try to parse as direct TickData for backward compatibility
            if (
              message.instrument &&
              message.time &&
              message.bid &&
              message.ask
            ) {
              updateTickData(message as TickData);
            }
          }
        } catch (err) {
          const parseError = new Error(
            `Failed to parse WebSocket message: ${err instanceof Error ? err.message : 'Unknown error'}`
          );
          setError(parseError);
          if (onError) {
            onError(parseError);
          }
        }
      };

      ws.onerror = (event) => {
        const wsError = new Error(
          `WebSocket error: ${event instanceof ErrorEvent ? event.message : 'Connection error'}`
        );
        setError(wsError);
        if (onError) {
          onError(wsError);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        if (onDisconnect) {
          onDisconnect();
        }

        // Attempt to reconnect if not at max attempts
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current += 1;
          setTimeout(() => {
            if (connectRef.current) {
              connectRef.current();
            }
          }, reconnectDelayMs);
        } else {
          const maxAttemptsError = new Error(
            'Maximum reconnection attempts reached'
          );
          setError(maxAttemptsError);
          if (onError) {
            onError(maxAttemptsError);
          }
        }
      };
    } catch (err) {
      const connectionError = new Error(
        `Failed to establish WebSocket connection: ${err instanceof Error ? err.message : 'Unknown error'}`
      );
      setError(connectionError);
      if (onError) {
        onError(connectionError);
      }
    }
  }, [accountId, instrument, updateTickData, onConnect, onDisconnect, onError]);

  // Store connect function in ref for use in onclose handler
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  // Manual reconnect function
  const reconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    if (connectRef.current) {
      connectRef.current();
    }
  }, []);

  // Initialize WebSocket connection
  useEffect(() => {
    // Only connect if accountId and instrument are provided
    if (!accountId || !instrument) {
      return;
    }

    // eslint-disable-next-line react-hooks/set-state-in-effect
    connect();

    // Cleanup on unmount
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (throttleTimerRef.current) {
        clearTimeout(throttleTimerRef.current);
        throttleTimerRef.current = null;
      }
    };
  }, [connect, accountId, instrument]);

  return {
    tickData,
    isConnected,
    error,
    reconnect,
  };
};

export default useMarketData;
