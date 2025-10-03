import { MCPServer, MCPServerConfig } from '@/app/infra/entities/api';

export class MCPCardVO {
  name: string;
  mode: 'stdio' | 'sse';
  enable: boolean;
  status: 'connected' | 'disconnected' | 'error';
  tools: number;
  error?: string;
  config: MCPServerConfig;

  constructor(data: MCPServer) {
    this.name = data.name;
    this.mode = data.mode;
    this.enable = data.enable;
    this.status = data.status;
    this.tools = data.tools.length;
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
      default:
        return 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z';
    }
  }
}
