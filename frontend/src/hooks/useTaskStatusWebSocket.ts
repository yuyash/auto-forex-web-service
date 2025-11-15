import { useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { TaskStatus } from '../types/common';

interface TaskStatusUpdate {
  task_id: number;
  task_name: string;
  task_type: 'backtest' | 'trading';
  status: TaskStatus;
  execution_id?: number;
  error_message?: string;
  timestamp: string;
}

interface TaskProgressUpdate {
  task_id: number;
  task_type: string;
  execution_id: number;
  progress: number;
  timestamp: string;
}

interface BacktestIntermediateResults {
  task_id: number;
  task_type: string;
  execution_id: number;
  day_date: string;
  progress: number;
  days_processed: number;
  total_days: number;
  ticks_processed: number;
  balance: number;
  total_trades: number;
  metrics: {
    total_return?: number;
    total_pnl?: number;
    win_rate?: number;
    winning_trades?: number;
    losing_trades?: number;
    max_drawdown?: number;
    sharpe_ratio?: number;
    profit_factor?: number;
    average_win?: number;
    average_loss?: number;
    [key: string]: string | number | undefined;
  };
  recent_trades: Array<Record<string, unknown>>;
  equity_curve: Array<{ timestamp: string; balance: number }>;
  timestamp: string;
}

interface UseTaskStatusWebSocketOptions {
  onStatusUpdate?: (update: TaskStatusUpdate) => void;
  onProgressUpdate?: (update: TaskProgressUpdate) => void;
  onIntermediateResults?: (results: BacktestIntermediateResults) => void;
  onComplete?: (update: TaskStatusUpdate) => void;
  onFailed?: (update: TaskStatusUpdate) => void;
  onStopped?: (update: TaskStatusUpdate) => void;
}

/**
 * Hook to connect to task status WebSocket and receive real-time updates
 * when tasks complete, fail, or are stopped.
 */
export function useTaskStatusWebSocket(
  options: UseTaskStatusWebSocketOptions = {}
) {
  const { token, isAuthenticated } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000; // 3 seconds
  const connectRef = useRef<(() => void) | null>(null);

  const {
    onStatusUpdate,
    onProgressUpdate,
    onIntermediateResults,
    onComplete,
    onFailed,
    onStopped,
  } = options;

  const handleStatusUpdate = useCallback(
    (update: TaskStatusUpdate) => {
      // Call general status update handler
      onStatusUpdate?.(update);

      // Call specific status handlers
      switch (update.status) {
        case TaskStatus.COMPLETED:
          onComplete?.(update);
          break;
        case TaskStatus.FAILED:
          onFailed?.(update);
          break;
        case TaskStatus.STOPPED:
          onStopped?.(update);
          break;
      }
    },
    [onStatusUpdate, onComplete, onFailed, onStopped]
  );

  const connect = useCallback(() => {
    if (!isAuthenticated || !token) {
      return;
    }

    // Close existing connection if any
    if (wsRef.current) {
      wsRef.current.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/tasks/status/?token=${token}`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('[TaskStatus WS] Connected');
      reconnectAttemptsRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === 'task_status_update') {
          const update = message.data as TaskStatusUpdate;
          console.log('[TaskStatus WS] Status update:', update);
          handleStatusUpdate(update);
        } else if (message.type === 'task_progress_update') {
          const update = message.data as TaskProgressUpdate;
          console.log('[TaskStatus WS] Progress update:', update);
          onProgressUpdate?.(update);
        } else if (message.type === 'backtest_intermediate_results') {
          const results = message.data as BacktestIntermediateResults;
          console.log('[TaskStatus WS] Intermediate results:', results);
          onIntermediateResults?.(results);
        } else if (message.type === 'pong') {
          // Ignore pong responses
        } else {
          console.warn('[TaskStatus WS] Unknown message type:', message.type);
        }
      } catch (error) {
        console.error('[TaskStatus WS] Failed to parse message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('[TaskStatus WS] Error:', error);
    };

    ws.onclose = (event) => {
      console.log('[TaskStatus WS] Disconnected:', event.code, event.reason);
      wsRef.current = null;

      // Attempt to reconnect if not a normal closure and under max attempts
      if (
        event.code !== 1000 &&
        reconnectAttemptsRef.current < maxReconnectAttempts &&
        isAuthenticated
      ) {
        reconnectAttemptsRef.current += 1;
        console.log(
          `[TaskStatus WS] Reconnecting... (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`
        );

        reconnectTimeoutRef.current = setTimeout(() => {
          connectRef.current?.();
        }, reconnectDelay);
      }
    };

    wsRef.current = ws;
  }, [
    isAuthenticated,
    token,
    handleStatusUpdate,
    onProgressUpdate,
    onIntermediateResults,
  ]);

  useEffect(() => {
    // Store connect function in ref for use in onclose handler
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    connect();

    // Cleanup on unmount
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted');
      }
    };
  }, [connect]);

  // Send ping periodically to keep connection alive
  useEffect(() => {
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000); // Every 30 seconds

    return () => clearInterval(pingInterval);
  }, []);

  // Don't return connection status as it would cause re-renders
  return {};
}
