export interface IPluginCardVO {
  author: string;
  name: string;
  description: string;
  version: string;
  enabled: boolean;
  priority: number;
  status: string;
  tools: object[];
  event_handlers: object;
  repository: string;
}

export class PluginCardVO implements IPluginCardVO {
  author: string;
  name: string;
  description: string;
  version: string;
  enabled: boolean;
  priority: number;
  status: string;
  tools: object[];
  event_handlers: object;
  repository: string;

  constructor(prop: IPluginCardVO) {
    this.author = prop.author;
    this.description = prop.description;
    this.enabled = prop.enabled;
    this.event_handlers = prop.event_handlers;
    this.name = prop.name;
    this.priority = prop.priority;
    this.repository = prop.repository;
    this.status = prop.status;
    this.tools = prop.tools;
    this.version = prop.version;
  }
}
