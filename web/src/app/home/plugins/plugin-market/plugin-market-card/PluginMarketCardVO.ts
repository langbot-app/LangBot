export interface IPluginMarketCardVO {
  pluginId: string;
  author: string;
  pluginName: string;
  label: string;
  description: string;
  installCount: number;
  iconURL: string;
  githubURL: string;
  version: string;
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
  version: string;

  constructor(prop: IPluginMarketCardVO) {
    this.description = prop.description;
    this.label = prop.label;
    this.author = prop.author;
    this.pluginName = prop.pluginName;
    this.iconURL = prop.iconURL;
    this.githubURL = prop.githubURL;
    this.installCount = prop.installCount;
    this.pluginId = prop.pluginId;
    this.version = prop.version;
  }
}
