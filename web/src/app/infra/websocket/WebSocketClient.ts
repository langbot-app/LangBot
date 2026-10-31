/**
 * WebSocket客户端类
 * 用于管理WebSocket连接和消息处理
 */
import { getActiveWorkspaceUuid } from '@/app/infra/http/workspaceContext';
import { backendWebSocketURL } from './url';
import type { MessageChainComponent } from '@/app/infra/entities/message';

export interface WebSocketMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  message_chain: MessageChainComponent[];
  timestamp: string;
  is_final?: boolean;
  connection_id?: string;
}

export interface WebSocketResponse {
  type:
    'connected' | 'response' | 'user_message' | 'pong' | 'broadcast' | 'error';
  connection_id?: string;
  pipeline_uuid?: string;
  session_type?: string;
  timestamp?: string;
  data?: WebSocketMessage;
  message?: string;
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private connectionId: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 3000; // 3秒重连间隔
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private heartbeatIntervalMs = 30000; // 30秒
  private isConnecting = false; // 防止重复连接
  private shouldReconnect = true;
  private disconnectedByUser = false;
  private workspaceUuid = getActiveWorkspaceUuid();
  private handshakeTimeout: ReturnType<typeof setTimeout> | null = null;
  private recoveryListenersAttached = false;
  private recover = () => {
    if (
      document.visibilityState === 'hidden' ||
      this.disconnectedByUser ||
      !this.shouldReconnect ||
      this.isConnecting ||
      this.isConnected()
    )
      return;
    if (getActiveWorkspaceUuid() !== this.workspaceUuid) return;
    void this.connect().catch(() => {});
  };
  private clearHandshakeTimeout() {
    if (this.handshakeTimeout) clearTimeout(this.handshakeTimeout);
    this.handshakeTimeout = null;
  }

  // 事件回调
  private onConnectedCallback?: (data: WebSocketResponse) => void;
  private onMessageCallback?: (data: WebSocketMessage) => void;
  private onErrorCallback?: (error: Error) => void;
  private onCloseCallback?: () => void;
  private onBroadcastCallback?: (message: string) => void;

  constructor(
    private pipelineId: string,
    private sessionType: 'person' | 'group' = 'person',
    private token?: string,
  ) {}

  /**
   * 连接到WebSocket服务器
   */
  public connect(): Promise<string> {
    return new Promise((resolve, reject) => {
      try {
        this.disconnectedByUser = false;
        this.shouldReconnect = true;
        if (this.reconnectTimeout) {
          clearTimeout(this.reconnectTimeout);
          this.reconnectTimeout = null;
        }

        // 防止重复连接
        if (
          this.isConnecting ||
          (this.ws && this.ws.readyState === WebSocket.CONNECTING)
        ) {
          console.warn('WebSocket正在连接中，忽略重复连接请求');
          reject(new Error('Connection already in progress'));
          return;
        }

        // 如果已经连接，直接返回
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          console.warn('WebSocket已连接，忽略重复连接请求');
          resolve(this.connectionId || '');
          return;
        }

        this.isConnecting = true;

        if (getActiveWorkspaceUuid() !== this.workspaceUuid) {
          this.isConnecting = false;
          this.shouldReconnect = false;
          reject(new Error('Workspace changed'));
          return;
        }
        const url = backendWebSocketURL(
          import.meta.env.VITE_API_BASE_URL,
          window.location.href,
          `api/v1/pipelines/${encodeURIComponent(this.pipelineId)}/ws/connect`,
        );
        url.searchParams.set('session_type', this.sessionType);
        const socket = new WebSocket(url.toString());
        this.ws = socket;
        if (!this.recoveryListenersAttached) {
          window.addEventListener('online', this.recover);
          window.addEventListener('focus', this.recover);
          document.addEventListener('visibilitychange', this.recover);
          this.recoveryListenersAttached = true;
        }
        this.clearHandshakeTimeout();
        this.handshakeTimeout = setTimeout(() => {
          if (this.ws !== socket || this.connectionId) return;
          reject(new Error('WebSocket authentication timed out'));
          socket.close();
        }, 15000);

        // 连接打开
        socket.onopen = () => {
          if (this.disconnectedByUser || this.ws !== socket) {
            socket.close();
            return;
          }
          const token = this.token || localStorage.getItem('token');
          const workspaceUuid = this.workspaceUuid;
          if (!token || !workspaceUuid) {
            const error = new Error('WebSocket认证信息缺失');
            this.shouldReconnect = false;
            this.onErrorCallback?.(error);
            socket.close();
            reject(error);
            return;
          }
          socket.send(
            JSON.stringify({
              type: 'authenticate',
              token,
              workspace_uuid: workspaceUuid,
            }),
          );
        };

        // 接收消息
        socket.onmessage = (event) => {
          if (this.disconnectedByUser || this.ws !== socket) return;
          try {
            const data: WebSocketResponse = JSON.parse(event.data);
            this.handleMessage(data);

            if (data.type === 'error' && !this.connectionId) {
              reject(new Error(data.message || 'WebSocket连接失败'));
              return;
            }

            // 第一次连接成功
            if (data.type === 'connected' && data.connection_id) {
              // Only a fully authenticated runtime connection should reset
              // the retry budget. Resetting on TCP open makes server-side
              // errors (for example a pipeline still loading) retry forever.
              this.clearHandshakeTimeout();
              this.isConnecting = false;
              this.reconnectAttempts = 0;
              this.connectionId = data.connection_id;
              this.startHeartbeat();
              resolve(data.connection_id);
            }
          } catch (error) {
            console.error('解析WebSocket消息失败:', error);
            this.onErrorCallback?.(error as Error);
          }
        };

        // 连接关闭
        socket.onclose = () => {
          reject(new Error('WebSocket connection closed'));
          if (this.ws !== socket) return;
          this.clearHandshakeTimeout();
          if (this.ws === socket) {
            this.ws = null;
            this.connectionId = null;
          }
          this.isConnecting = false;
          this.stopHeartbeat();
          if (this.disconnectedByUser) return;
          this.onCloseCallback?.();

          // 自动重连
          if (
            this.shouldReconnect &&
            getActiveWorkspaceUuid() === this.workspaceUuid
          ) {
            this.reconnectAttempts = Math.min(
              this.reconnectAttempts + 1,
              this.maxReconnectAttempts,
            );
            this.reconnectTimeout = setTimeout(() => {
              this.reconnectTimeout = null;
              if (!this.shouldReconnect || this.disconnectedByUser) return;
              this.connect().catch(console.error);
            }, this.reconnectDelay * this.reconnectAttempts);
          }
        };

        // 连接错误
        socket.onerror = (event) => {
          if (this.disconnectedByUser || this.ws !== socket) {
            reject(new Error('WebSocket连接已取消'));
            return;
          }
          console.error('WebSocket错误:', event);
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
  }

  /**
   * 处理接收到的消息
   */
  private handleMessage(data: WebSocketResponse) {
    switch (data.type) {
      case 'connected':
        this.onConnectedCallback?.(data);
        break;

      case 'response':
        // 检查 session_type 是否匹配 - 如果消息没有 session_type 或者不匹配当前session，都忽略
        if (!data.session_type || data.session_type !== this.sessionType) {
          // 忽略不匹配的 session_type 消息
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
        // 检查 session_type 是否匹配 - 如果消息没有 session_type 或者不匹配当前session，都忽略
        if (!data.session_type || data.session_type !== this.sessionType) {
          // 忽略不匹配的 session_type 消息
          console.debug(
            `忽略不匹配的用户消息: 当前session=${this.sessionType}, 消息session=${data.session_type}`,
          );
          break;
        }
        // 用户消息广播（包括自己发送的消息）
        if (data.data) {
          this.onMessageCallback?.(data.data);
        }
        break;

      case 'pong':
        // 心跳响应
        break;

      case 'broadcast':
        if (data.message) {
          this.onBroadcastCallback?.(data.message);
        }
        break;

      case 'error':
        const error = new Error(data.message || '未知错误');
        this.onErrorCallback?.(error);
        // Authentication/resource errors happen before the `connected`
        // handshake. Retrying them cannot recover and would leak error toasts
        // after the user leaves the Pipeline page.
        if (!this.connectionId) {
          this.shouldReconnect = false;
          this.ws?.close();
        }
        break;

      default:
        console.warn('未知消息类型:', data);
    }
  }

  /**
   * 发送消息
   */
  public sendMessage(
    messageChain: MessageChainComponent[],
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

  /**
   * 发送心跳
   */
  private sendHeartbeat() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    this.ws.send(JSON.stringify({ type: 'ping' }));
  }

  /**
   * 启动心跳
   */
  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      this.sendHeartbeat();
    }, this.heartbeatIntervalMs);
  }

  /**
   * 停止心跳
   */
  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  /**
   * 断开连接
   */
  public disconnect() {
    this.disconnectedByUser = true;
    this.clearHandshakeTimeout();
    window.removeEventListener('online', this.recover);
    window.removeEventListener('focus', this.recover);
    document.removeEventListener('visibilitychange', this.recover);
    this.recoveryListenersAttached = false;
    this.shouldReconnect = false;
    this.reconnectAttempts = this.maxReconnectAttempts;
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.stopHeartbeat();
      const socket = this.ws;

      // 发送断开消息
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'disconnect' }));
      }

      this.ws = null;
      this.connectionId = null;
      this.isConnecting = false;
      socket.close();
    }
  }

  /**
   * 获取连接ID
   */
  public getConnectionId(): string | null {
    return this.connectionId;
  }

  /**
   * 获取连接状态
   */
  public isConnected(): boolean {
    return (
      this.ws !== null &&
      this.ws.readyState === WebSocket.OPEN &&
      this.connectionId !== null
    );
  }

  // ===== 事件回调设置 =====

  public onConnected(callback: (data: WebSocketResponse) => void) {
    this.onConnectedCallback = callback;
    return this;
  }

  public onMessage(callback: (data: WebSocketMessage) => void) {
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
