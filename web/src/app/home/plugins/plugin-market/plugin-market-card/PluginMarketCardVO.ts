export interface IPluginMarketCardVO {
  pluginId: string;
  author: string;
  name: string;
  description: string;
  starCount: number;
  githubURL: string;
  version: string;
}

export class PluginMarketCardVO implements IPluginMarketCardVO {
  pluginId: string;
  description: string;
  name: string;
  author: string;
  githubURL: string;
  starCount: number;
  version: string;

  constructor(prop: IPluginMarketCardVO) {
    this.description = prop.description;
    this.name = prop.name;
    this.author = prop.author;
    this.githubURL = prop.githubURL;
    this.starCount = prop.starCount;
    this.pluginId = prop.pluginId;
    this.version = prop.version;
  }
}
