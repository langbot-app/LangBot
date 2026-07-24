export interface IPluginMarketCardVO {
  pluginId: string;
  author: string;
  pluginName: string;
  label: string;
  description: string;
  installCount: number;
  likeCount?: number;
  iconURL: string;
  githubURL: string;
  version: string;
  components?: Record<string, number>;
  tags?: string[];
  type?: 'plugin' | 'mcp' | 'skill';
}

export class PluginMarketCardVO implements IPluginMarketCardVO {
  pluginId: string;
  description: string;
  label: string;
  author: string;
  pluginName: string;
  iconURL: string;
  githubURL: string;
  installCount: number;
  likeCount: number;
  version: string;
  components?: Record<string, number>;
  tags?: string[];
  type?: 'plugin' | 'mcp' | 'skill';

  constructor(prop: IPluginMarketCardVO) {
    this.description = prop.description;
    this.label = prop.label;
    this.author = prop.author;
    this.pluginName = prop.pluginName;
    this.iconURL = prop.iconURL;
    this.githubURL = prop.githubURL;
    this.installCount = prop.installCount;
    this.likeCount = prop.likeCount ?? 0;
    this.pluginId = prop.pluginId;
    this.version = prop.version;
    this.components = prop.components;
    this.tags = prop.tags;
    this.type = prop.type;
  }
}
