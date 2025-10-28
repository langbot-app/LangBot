import { MCPServer, MCPServerConfig } from '@/app/infra/entities/api';

export class MCPCardVO {
  name: string;
  mode: 'stdio' | 'sse';
  enable: boolean;
  status: 'connected' | 'disconnected' | 'error' | 'disabled';
  tools: number;
  error?: string;
  config: MCPServerConfig;

  constructor(data: MCPServer) {
    this.name = data.name;
    this.mode = data.mode;
    this.enable = data.enable;
    // 将后端返回的 "enabled" 状态映射为 "connected"
    this.status = (data.status as string) === 'enabled'
      ? 'connected'
      : data.status;
    // tools可能是数组或数字
    this.tools = Array.isArray(data.tools)
      ? data.tools.length
      : data.tools || 0;
    this.error = data.error;
    this.config = data.config;
  }

  getStatusColor(): string {
    switch (this.status) {
      case 'connected':
        return 'text-green-600';
      case 'disconnected':
        return 'text-gray-500';
      case 'error':
        return 'text-red-600';
      case 'disabled':
        return 'text-gray-400';
      default:
        return 'text-gray-500';
    }
  }

  getStatusIcon(): string {
    switch (this.status) {
      case 'connected':
        return 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z';
      case 'disconnected':
        return 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z';
      case 'error':
        return 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z';
      case 'disabled':
        return 'M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636';
      default:
        return 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z';
    }
  }
}
