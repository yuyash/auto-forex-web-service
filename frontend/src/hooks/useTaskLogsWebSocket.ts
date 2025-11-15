import { useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';

interface ExecutionLog {
  timestamp: string;
  level: string;
  message: string;
}

interface TaskLogUpdate {
  execution_id: number;
  task_id: number;
  task_type: string;
  execution_number: number;
  log: ExecutionLog;
}

interface UseTaskLogsWebSocketOptions {
  taskType: 'backtest' | 'trading';
  taskId: number;
  onLog?: (update: TaskLogUpdate) => void;
  enabled?: boolean;
}

/**
 * Hook to connect to task logs WebSocket and receive real-time log updates
 * as they are generated during task execution.
 */
export function useTaskLogsWebSocket(options: UseTaskLogsWebSocketOptions) {
  const { taskType, taskId, onLog, enabled = true } = options;
  const { token, isAuthenticated } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000; // 3 seconds
  const connectRef = useRef<(() => void) | null>(null);

  const connect = useCallback(() => {
    if (!isAuthenticated || !token || !enabled) {
      return;
    }

    // Close existing connection if any
    if (wsRef.current) {
      wsRef.current.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/tasks/${taskType}/${taskId}/logs/?token=${token}`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`[TaskLogs WS] Connected to ${taskType} task ${taskId}`);
      reconnectAttemptsRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === 'execution_log') {
          const update = message.data as TaskLogUpdate;
          console.log('[TaskLogs WS] Log update:', update.log.message);
          onLog?.(update);
        } else if (message.type === 'pong') {
          // Ignore pong responses
        } else {
          console.warn('[TaskLogs WS] Unknown message type:', message.type);
        }
      } catch (error) {
        console.error('[TaskLogs WS] Failed to parse message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('[TaskLogs WS] Error:', error);
    };

    ws.onclose = (event) => {
      console.log('[TaskLogs WS] Disconnected:', event.code, event.reason);
      wsRef.current = null;

      // Attempt to reconnect if not a normal closure and under max attempts
      if (
        event.code !== 1000 &&
        reconnectAttemptsRef.current < maxReconnectAttempts &&
        isAuthenticated &&
        enabled
      ) {
        reconnectAttemptsRef.current += 1;
        console.log(
          `[TaskLogs WS] Reconnecting... (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`
        );

        reconnectTimeoutRef.current = setTimeout(() => {
          connectRef.current?.();
        }, reconnectDelay);
      }
    };

    wsRef.current = ws;
  }, [isAuthenticated, token, taskType, taskId, onLog, enabled]);

  useEffect(() => {
    // Store connect function in ref for use in onclose handler
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    if (enabled) {
      connect();
    }

    // Cleanup on unmount or when disabled
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted or disabled');
      }
    };
  }, [connect, enabled]);

  // Send ping periodically to keep connection alive
  useEffect(() => {
    if (!enabled) return;

    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000); // Every 30 seconds

    return () => clearInterval(pingInterval);
  }, [enabled]);

  return {};
}
