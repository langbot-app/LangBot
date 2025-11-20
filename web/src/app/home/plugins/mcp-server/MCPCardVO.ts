import { MCPServer, MCPSessionStatus } from '@/app/infra/entities/api';

export class MCPCardVO {
  name: string;
  mode: 'stdio' | 'sse';
  enable: boolean;
  status: MCPSessionStatus;
  tools: number;
  error?: string;

  constructor(data: MCPServer) {
    this.name = data.name;
    this.mode = data.mode;
    this.enable = data.enable;

    // Determine status from runtime_info
    if (!data.runtime_info) {
      this.status = MCPSessionStatus.ERROR;
      this.tools = 0;
    } else if (data.runtime_info.status === MCPSessionStatus.CONNECTED) {
      this.status = data.runtime_info.status;
      this.tools = data.runtime_info.tool_count || 0;
    } else {
      this.status = data.runtime_info.status;
      this.tools = 0;
      this.error = data.runtime_info.error_message;
    }
  }
}
