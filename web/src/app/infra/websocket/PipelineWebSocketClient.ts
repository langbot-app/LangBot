/**
 * Pipeline WebSocket Client
 *
 * Provides real-time bidirectional communication for pipeline debugging.
 * Supports person and group session isolation.
 */

import { Message } from '@/app/infra/entities/message';

export type SessionType = 'person' | 'group';

export interface WebSocketEventData {
  // Connected event
  connected?: {
    connection_id: string;
    session_type: SessionType;
    pipeline_uuid: string;
  };

  // History event
  history?: {
    messages: Message[];
    has_more: boolean;
  };

  // Message sent confirmation
  message_sent?: {
    client_message_id: string;
    server_message_id: number;
    timestamp: string;
  };

  // Message start
  message_start?: {
    message_id: number;
    role: 'assistant';
    timestamp: string;
    reply_to: number;
  };

  // Message chunk
  message_chunk?: {
    message_id: number;
    content: string;
    message_chain: object[];
    timestamp: string;
  };

  // Message complete
  message_complete?: {
    message_id: number;
    final_content: string;
    message_chain: object[];
    timestamp: string;
  };

  // Message error
  message_error?: {
    message_id: number;
    error: string;
    error_code?: string;
  };

  // Interrupted
  interrupted?: {
    message_id: number;
    partial_content: string;
  };

  // Plugin message
  plugin_message?: {
    message_id: number;
    role: 'assistant';
    content: string;
    message_chain: object[];
    timestamp: string;
    source: 'plugin';
  };

  // Error
  error?: {
    error: string;
    error_code: string;
    details?: object;
  };

  // Pong
  pong?: {
    timestamp: number;
  };
}

export class PipelineWebSocketClient {
  private ws: WebSocket | null = null;
  private pipelineId: string;
  private sessionType: SessionType;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private pingInterval: NodeJS.Timeout | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private isManualDisconnect = false;

  // Event callbacks
  public onConnected?: (data: WebSocketEventData['connected']) => void;
  public onHistory?: (data: WebSocketEventData['history']) => void;
  public onMessageSent?: (data: WebSocketEventData['message_sent']) => void;
  public onMessageStart?: (data: WebSocketEventData['message_start']) => void;
  public onMessageChunk?: (data: WebSocketEventData['message_chunk']) => void;
  public onMessageComplete?: (
    data: WebSocketEventData['message_complete'],
  ) => void;
  public onMessageError?: (data: WebSocketEventData['message_error']) => void;
  public onInterrupted?: (data: WebSocketEventData['interrupted']) => void;
  public onPluginMessage?: (data: WebSocketEventData['plugin_message']) => void;
  public onError?: (data: WebSocketEventData['error']) => void;
  public onDisconnected?: () => void;

  constructor(pipelineId: string, sessionType: SessionType) {
    this.pipelineId = pipelineId;
    this.sessionType = sessionType;
  }

  /**
   * Connect to WebSocket server
   */
  connect(token: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.isManualDisconnect = false;

      const wsUrl = this.buildWebSocketUrl();
      console.log(`[WebSocket] Connecting to ${wsUrl}...`);

      try {
        this.ws = new WebSocket(wsUrl);
      } catch (error) {
        console.error('[WebSocket] Failed to create WebSocket:', error);
        reject(error);
        return;
      }

      this.ws.onopen = () => {
        console.log('[WebSocket] Connection opened');

        // Send connect event with session type and token
        this.send('connect', {
          pipeline_uuid: this.pipelineId,
          session_type: this.sessionType,
          token,
        });

        // Start ping interval
        this.startPing();

        // Reset reconnect attempts on successful connection
        this.reconnectAttempts = 0;

        resolve();
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event);
      };

      this.ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        reject(error);
      };

      this.ws.onclose = (event) => {
        console.log(
          `[WebSocket] Connection closed: code=${event.code}, reason=${event.reason}`,
        );
        this.handleDisconnect();
      };
    });
  }

  /**
   * Handle incoming WebSocket message
   */
  private handleMessage(event: MessageEvent) {
    try {
      const message = JSON.parse(event.data);
      const { type, data } = message;

      console.log(`[WebSocket] Received: ${type}`, data);

      switch (type) {
        case 'connected':
          this.onConnected?.(data);
          break;
        case 'history':
          this.onHistory?.(data);
          break;
        case 'message_sent':
          this.onMessageSent?.(data);
          break;
        case 'message_start':
          this.onMessageStart?.(data);
          break;
        case 'message_chunk':
          this.onMessageChunk?.(data);
          break;
        case 'message_complete':
          this.onMessageComplete?.(data);
          break;
        case 'message_error':
          this.onMessageError?.(data);
          break;
        case 'interrupted':
          this.onInterrupted?.(data);
          break;
        case 'plugin_message':
          this.onPluginMessage?.(data);
          break;
        case 'error':
          this.onError?.(data);
          break;
        case 'pong':
          // Heartbeat response, no action needed
          break;
        default:
          console.warn(`[WebSocket] Unknown message type: ${type}`);
      }
    } catch (error) {
      console.error('[WebSocket] Failed to parse message:', error);
    }
  }

  /**
   * Send message to server
   */
  sendMessage(messageChain: object[]): string {
    const clientMessageId = this.generateMessageId();
    this.send('send_message', {
      message_chain: messageChain,
      client_message_id: clientMessageId,
    });
    return clientMessageId;
  }

  /**
   * Load history messages
   */
  loadHistory(beforeMessageId?: number, limit?: number) {
    this.send('load_history', {
      before_message_id: beforeMessageId,
      limit,
    });
  }

  /**
   * Interrupt streaming message
   */
  interrupt(messageId: number) {
    this.send('interrupt', { message_id: messageId });
  }

  /**
   * Send event to server
   */
  private send(type: string, data: object) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({ type, data });
      console.log(`[WebSocket] Sending: ${type}`, data);
      this.ws.send(message);
    } else {
      console.warn(
        `[WebSocket] Cannot send message, connection not open (state: ${this.ws?.readyState})`,
      );
    }
  }

  /**
   * Start ping interval (heartbeat)
   */
  private startPing() {
    this.stopPing();
    this.pingInterval = setInterval(() => {
      this.send('ping', { timestamp: Date.now() });
    }, 30000); // Ping every 30 seconds
  }

  /**
   * Stop ping interval
   */
  private stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  /**
   * Handle disconnection
   */
  private handleDisconnect() {
    this.stopPing();
    this.onDisconnected?.();

    // Auto reconnect if not manual disconnect
    if (
      !this.isManualDisconnect &&
      this.reconnectAttempts < this.maxReconnectAttempts
    ) {
      const delay = Math.min(2000 * Math.pow(2, this.reconnectAttempts), 30000);
      console.log(
        `[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`,
      );

      this.reconnectTimeout = setTimeout(() => {
        this.reconnectAttempts++;
        // Note: Need to get token again, should be handled by caller
        console.warn(
          '[WebSocket] Auto-reconnect requires token, please reconnect manually',
        );
      }, delay);
    } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error(
        '[WebSocket] Max reconnect attempts reached, giving up',
      );
    }
  }

  /**
   * Disconnect from server
   */
  disconnect() {
    this.isManualDisconnect = true;
    this.stopPing();

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    console.log('[WebSocket] Disconnected');
  }

  /**
   * Build WebSocket URL
   */
  private buildWebSocketUrl(): string {
    // Get current base URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;

    return `${protocol}//${host}/api/v1/pipelines/${this.pipelineId}/chat/ws`;
  }

  /**
   * Generate unique client message ID
   */
  private generateMessageId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Get connection state
   */
  getState():
    | 'CONNECTING'
    | 'OPEN'
    | 'CLOSING'
    | 'CLOSED'
    | 'DISCONNECTED' {
    if (!this.ws) return 'DISCONNECTED';

    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'CONNECTING';
      case WebSocket.OPEN:
        return 'OPEN';
      case WebSocket.CLOSING:
        return 'CLOSING';
      case WebSocket.CLOSED:
        return 'CLOSED';
      default:
        return 'DISCONNECTED';
    }
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
