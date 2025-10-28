export interface IMCPMarketCardVO {
  serverId: string;
  author: string;
  name: string;
  description: string;
  starCount: number;
  githubURL: string;
  version: string;
}

export class MCPMarketCardVO implements IMCPMarketCardVO {
  serverId: string;
  description: string;
  name: string;
  author: string;
  githubURL: string;
  starCount: number;
  version: string;

  constructor(prop: IMCPMarketCardVO) {
    this.description = prop.description;
    this.name = prop.name;
    this.author = prop.author;
    this.githubURL = prop.githubURL;
    this.starCount = prop.starCount;
    this.serverId = prop.serverId;
    this.version = prop.version;
  }
}
