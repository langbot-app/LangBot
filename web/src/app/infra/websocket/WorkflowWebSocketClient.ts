/**
 * Workflow WebSocket客户端类
 * 用于管理工作流调试的WebSocket连接和消息处理
 */
export interface WorkflowWebSocketMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  message_chain: Array<{ type: string; text?: string; target?: string }>;
  timestamp: string;
  is_final?: boolean;
  connection_id?: string;
}

export interface WorkflowWebSocketResponse {
  type:
    | 'connected'
    | 'response'
    | 'user_message'
    | 'pong'
    | 'broadcast'
    | 'error';
  connection_id?: string;
  workflow_uuid?: string;
  session_type?: string;
  timestamp?: string;
  data?: WorkflowWebSocketMessage;
  message?: string;
}

export class WorkflowWebSocketClient {
  private ws: WebSocket | null = null;
  private connectionId: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 3000;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private heartbeatIntervalMs = 30000;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private isConnecting = false;
  private shouldReconnect = true;
  private manualDisconnect = false;
  private activeConnectPromise: Promise<string> | null = null;

  private onConnectedCallback?: (data: WorkflowWebSocketResponse) => void;
  private onMessageCallback?: (data: WorkflowWebSocketMessage) => void;
  private onErrorCallback?: (error: Error) => void;
  private onCloseCallback?: () => void;
  private onBroadcastCallback?: (message: string) => void;

  constructor(
    private workflowId: string,
    private sessionType: 'person' | 'group' = 'person',
    private token?: string,
  ) {}

  public connect(): Promise<string> {
    if (this.activeConnectPromise) {
      console.warn('WebSocket连接请求进行中，复用当前连接请求');
      return this.activeConnectPromise;
    }

    const connectPromise = new Promise<string>((resolve, reject) => {
      try {
        if (
          this.isConnecting ||
          (this.ws && this.ws.readyState === WebSocket.CONNECTING)
        ) {
          console.warn('WebSocket正在连接中，忽略重复连接请求');
          reject(new Error('Connection already in progress'));
          return;
        }

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          console.warn('WebSocket已连接，忽略重复连接请求');
          resolve(this.connectionId || '');
          return;
        }

        this.isConnecting = true;
        this.shouldReconnect = true;
        this.manualDisconnect = false;
        this.clearReconnectTimer();

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host =
          import.meta.env.VITE_API_BASE_URL?.split('://')[1] ||
          window.location.host;
        const url = `${protocol}//${host}/api/v1/workflows/${this.workflowId}/ws/connect?session_type=${this.sessionType}`;

        console.debug('[WorkflowWebSocket] connect:start', {
          workflowId: this.workflowId,
          sessionType: this.sessionType,
          url,
          reconnectAttempts: this.reconnectAttempts,
          maxReconnectAttempts: this.maxReconnectAttempts,
          readyState: this.ws?.readyState ?? null,
          locationHost: window.location.host,
          envBaseUrl: import.meta.env.VITE_API_BASE_URL,
        });

        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
          console.debug('[WorkflowWebSocket] connect:open', {
            workflowId: this.workflowId,
            sessionType: this.sessionType,
            url,
            reconnectAttempts: this.reconnectAttempts,
            readyState: this.ws?.readyState ?? null,
          });
          this.reconnectAttempts = 0;
          this.isConnecting = false;
          this.clearReconnectTimer();
          this.startHeartbeat();
        };

        this.ws.onmessage = (event) => {
          try {
            const data: WorkflowWebSocketResponse = JSON.parse(event.data);
            this.handleMessage(data);

            if (data.type === 'connected' && data.connection_id) {
              this.connectionId = data.connection_id;
              resolve(data.connection_id);
            }
          } catch (error) {
            console.error('解析WebSocket消息失败:', error);
            this.onErrorCallback?.(error as Error);
          }
        };

        this.ws.onclose = (event) => {
          const wasManualClose =
            this.manualDisconnect || event.reason === 'client-disconnect';

          console.warn('[WorkflowWebSocket] connect:close', {
            workflowId: this.workflowId,
            sessionType: this.sessionType,
            url,
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
            reconnectAttempts: this.reconnectAttempts,
            maxReconnectAttempts: this.maxReconnectAttempts,
            wasManualClose,
          });
          this.isConnecting = false;
          this.stopHeartbeat();
          this.ws = null;
          this.connectionId = null;
          this.onCloseCallback?.();

          if (wasManualClose) {
            this.manualDisconnect = false;
            return;
          }

          if (
            this.shouldReconnect &&
            this.reconnectAttempts < this.maxReconnectAttempts
          ) {
            this.reconnectAttempts++;
            console.debug('[WorkflowWebSocket] connect:retry-scheduled', {
              workflowId: this.workflowId,
              sessionType: this.sessionType,
              url,
              reconnectAttempts: this.reconnectAttempts,
              delayMs: this.reconnectDelay * this.reconnectAttempts,
            });
            this.reconnectTimer = setTimeout(() => {
              this.connect().catch(console.error);
            }, this.reconnectDelay * this.reconnectAttempts);
          }
        };

        this.ws.onerror = (event) => {
          console.error('[WorkflowWebSocket] connect:error', {
            workflowId: this.workflowId,
            sessionType: this.sessionType,
            url,
            reconnectAttempts: this.reconnectAttempts,
            readyState: this.ws?.readyState ?? null,
            event,
          });
          this.isConnecting = false;
          const error = new Error('WebSocket连接失败');
          this.onErrorCallback?.(error);
          reject(error);
        };
      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });

    this.activeConnectPromise = connectPromise;
    connectPromise.finally(() => {
      if (this.activeConnectPromise === connectPromise) {
        this.activeConnectPromise = null;
      }
    });

    return connectPromise;
  }

  private handleMessage(data: WorkflowWebSocketResponse) {
    switch (data.type) {
      case 'connected':
        this.onConnectedCallback?.(data);
        break;

      case 'response':
        if (!data.session_type || data.session_type !== this.sessionType) {
          console.debug(
            `忽略不匹配的消息: 当前session=${this.sessionType}, 消息session=${data.session_type}`,
          );
          break;
        }
        if (data.data) {
          this.onMessageCallback?.(data.data);
        }
        break;

      case 'user_message':
        if (!data.session_type || data.session_type !== this.sessionType) {
          console.debug(
            `忽略不匹配的用户消息: 当前session=${this.sessionType}, 消息session=${data.session_type}`,
          );
          break;
        }
        if (data.data) {
          this.onMessageCallback?.(data.data);
        }
        break;

      case 'pong':
        break;

      case 'broadcast':
        if (data.message) {
          this.onBroadcastCallback?.(data.message);
        }
        break;

      case 'error':
        this.shouldReconnect = false;
        this.clearReconnectTimer();
        this.stopHeartbeat();
        const error = new Error(data.message || '未知错误');
        this.onErrorCallback?.(error);
        this.ws?.close(1000, 'workflow-error');
        break;

      default:
        console.warn('未知消息类型:', data);
    }
  }

  public sendMessage(
    messageChain: Array<{ type: string; text?: string; target?: string }>,
    stream: boolean = true,
  ) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket未连接');
    }

    const message = {
      type: 'message',
      message: messageChain,
      stream: stream,
    };

    this.ws.send(JSON.stringify(message));
  }

  private sendHeartbeat() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }
    this.ws.send(JSON.stringify({ type: 'ping' }));
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      this.sendHeartbeat();
    }, this.heartbeatIntervalMs);
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private clearReconnectTimer() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  public disconnect() {
    this.manualDisconnect = true;
    this.shouldReconnect = false;
    this.clearReconnectTimer();
    this.stopHeartbeat();
    this.reconnectAttempts = this.maxReconnectAttempts;
    this.isConnecting = false;
    this.connectionId = null;

    if (this.ws) {
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'disconnect' }));
      }

      if (
        this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING
      ) {
        this.ws.close(1000, 'client-disconnect');
      }

      this.ws = null;
    }
  }

  public getConnectionId(): string | null {
    return this.connectionId;
  }

  public isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  public onConnected(callback: (data: WorkflowWebSocketResponse) => void) {
    this.onConnectedCallback = callback;
    return this;
  }

  public onMessage(callback: (data: WorkflowWebSocketMessage) => void) {
    this.onMessageCallback = callback;
    return this;
  }

  public onError(callback: (error: Error) => void) {
    this.onErrorCallback = callback;
    return this;
  }

  public onClose(callback: () => void) {
    this.onCloseCallback = callback;
    return this;
  }

  public onBroadcast(callback: (message: string) => void) {
    this.onBroadcastCallback = callback;
    return this;
  }
}
