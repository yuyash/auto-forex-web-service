/**
 * TaskStatusWebSocket Service
 *
 * Manages WebSocket connections for real-time task status updates, progress tracking,
 * and execution log streaming. Implements automatic reconnection with exponential backoff.
 *
 * Features:
 * - Authentication token-based connection
 * - Message subscription and routing
 * - Automatic reconnection with exponential backoff (max 5 attempts)
 * - Clean disconnect and resource cleanup
 * - Type-safe message handling
 */

export interface TaskStatusMessage {
  type:
    | 'task_status_update'
    | 'task_progress_update'
    | 'backtest_intermediate_results'
    | 'execution_log';
  data: {
    task_id: number;
    task_type: string;
    status?: string;
    progress?: number;
    execution_id?: number;
    timestamp: string;
    error_message?: string;
    [key: string]: unknown;
  };
}

export type MessageCallback = (message: TaskStatusMessage) => void;

export class TaskStatusWebSocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts = 5;
  private reconnectDelay = 3000; // Initial delay: 3 seconds
  private reconnectTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private callbacks: Set<MessageCallback> = new Set();
  private token: string | null = null;
  private isManualDisconnect = false;
  private heartbeatIntervalId: ReturnType<typeof setInterval> | null = null;
  private readonly heartbeatInterval = 30000; // Send ping every 30 seconds

  /**
   * Connect to the WebSocket server with authentication token
   * @param token - JWT authentication token
   */
  connect(token: string): void {
    if (!token) {
      console.error(
        '[TaskStatusWebSocket] Cannot connect: No authentication token provided'
      );
      return;
    }

    this.token = token;
    this.isManualDisconnect = false;

    // Close existing connection if any
    if (this.ws) {
      this.ws.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/tasks/status/?token=${token}`;

    console.log('[TaskStatusWebSocket] Connecting to:', wsUrl);

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onerror = this.handleError.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
    } catch (error) {
      console.error('[TaskStatusWebSocket] Connection error:', error);
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect from the WebSocket server and cleanup resources
   */
  disconnect(): void {
    console.log('[TaskStatusWebSocket] Disconnecting...');

    this.isManualDisconnect = true;
    this.reconnectAttempts = 0;

    // Clear any pending reconnection attempts
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }

    // Stop heartbeat
    this.stopHeartbeat();

    // Close WebSocket connection
    if (this.ws) {
      this.ws.close(1000, 'Manual disconnect');
      this.ws = null;
    }

    // Clear all callbacks
    this.callbacks.clear();
  }

  /**
   * Subscribe to WebSocket messages
   * @param callback - Function to call when messages are received
   */
  subscribe(callback: MessageCallback): void {
    this.callbacks.add(callback);
  }

  /**
   * Unsubscribe from WebSocket messages
   * @param callback - Function to remove from subscribers
   */
  unsubscribe(callback: MessageCallback): void {
    this.callbacks.delete(callback);
  }

  /**
   * Get current connection state
   * @returns true if connected, false otherwise
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Get current reconnection attempt count
   * @returns number of reconnection attempts made
   */
  getReconnectAttempts(): number {
    return this.reconnectAttempts;
  }

  /**
   * Handle WebSocket open event
   */
  private handleOpen(): void {
    console.log('[TaskStatusWebSocket] Connected successfully');

    this.reconnectAttempts = 0;
    this.reconnectDelay = 3000; // Reset delay to initial value

    // Start heartbeat to keep connection alive
    this.startHeartbeat();
  }

  /**
   * Handle incoming WebSocket messages and route to subscribers
   * @param event - WebSocket message event
   */
  private handleMessage(event: MessageEvent): void {
    try {
      const message = JSON.parse(event.data) as TaskStatusMessage;

      // Ignore pong messages
      if (message.type === ('pong' as unknown as TaskStatusMessage['type'])) {
        return;
      }

      console.log(
        '[TaskStatusWebSocket] Message received:',
        message.type,
        message.data
      );

      // Notify all subscribers
      this.callbacks.forEach((callback) => {
        try {
          callback(message);
        } catch (error) {
          console.error(
            '[TaskStatusWebSocket] Error in message callback:',
            error
          );
        }
      });
    } catch (error) {
      console.error('[TaskStatusWebSocket] Failed to parse message:', error);
    }
  }

  /**
   * Handle WebSocket error event
   * @param error - WebSocket error event
   */
  private handleError(error: Event): void {
    console.error('[TaskStatusWebSocket] WebSocket error:', error);
  }

  /**
   * Handle WebSocket close event and attempt reconnection if needed
   * @param event - WebSocket close event
   */
  private handleClose(event: CloseEvent): void {
    console.log(
      '[TaskStatusWebSocket] Connection closed:',
      event.code,
      event.reason
    );

    this.ws = null;

    // Stop heartbeat
    this.stopHeartbeat();

    // Don't reconnect if it was a manual disconnect or normal closure
    if (this.isManualDisconnect || event.code === 1000) {
      console.log(
        '[TaskStatusWebSocket] Not reconnecting (manual disconnect or normal closure)'
      );
      return;
    }

    // Attempt reconnection if under max attempts
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.scheduleReconnect();
    } else {
      console.error(
        '[TaskStatusWebSocket] Max reconnection attempts reached. Please refresh the page or check your connection.'
      );
    }
  }

  /**
   * Schedule a reconnection attempt with exponential backoff
   */
  private scheduleReconnect(): void {
    if (this.isManualDisconnect) {
      return;
    }

    this.reconnectAttempts += 1;

    // Calculate exponential backoff delay
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      30000 // Max delay: 30 seconds
    );

    console.log(
      `[TaskStatusWebSocket] Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
    );

    this.reconnectTimeoutId = setTimeout(() => {
      this.reconnect();
    }, delay);
  }

  /**
   * Attempt to reconnect to the WebSocket server
   */
  private reconnect(): void {
    if (!this.token || this.isManualDisconnect) {
      console.log(
        '[TaskStatusWebSocket] Cannot reconnect: No token or manual disconnect'
      );
      return;
    }

    console.log('[TaskStatusWebSocket] Attempting to reconnect...');
    this.connect(this.token);
  }

  /**
   * Start sending periodic ping messages to keep connection alive
   */
  private startHeartbeat(): void {
    // Clear any existing heartbeat
    this.stopHeartbeat();

    // Send ping every 30 seconds
    this.heartbeatIntervalId = setInterval(() => {
      if (this.isConnected()) {
        try {
          this.ws?.send(JSON.stringify({ type: 'ping' }));
          console.log('[TaskStatusWebSocket] Heartbeat ping sent');
        } catch (error) {
          console.error(
            '[TaskStatusWebSocket] Failed to send heartbeat:',
            error
          );
        }
      }
    }, this.heartbeatInterval);
  }

  /**
   * Stop sending heartbeat messages
   */
  private stopHeartbeat(): void {
    if (this.heartbeatIntervalId) {
      clearInterval(this.heartbeatIntervalId);
      this.heartbeatIntervalId = null;
    }
  }
}
