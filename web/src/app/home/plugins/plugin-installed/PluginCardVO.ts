import { PluginComponent } from '@/app/infra/entities/plugin';

export interface IPluginCardVO {
  author: string;
  label: string;
  name: string;
  description: string;
  version: string;
  enabled: boolean;
  priority: number;
  install_source: string;
  install_info: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  status: string;
  components: PluginComponent[];
  debug: boolean;
}

export class PluginCardVO implements IPluginCardVO {
  author: string;
  label: string;
  name: string;
  description: string;
  version: string;
  enabled: boolean;
  priority: number;
  debug: boolean;
  install_source: string;
  install_info: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  status: string;
  components: PluginComponent[];

  constructor(prop: IPluginCardVO) {
    this.author = prop.author;
    this.label = prop.label;
    this.description = prop.description;
    this.enabled = prop.enabled;
    this.components = prop.components;
    this.name = prop.name;
    this.priority = prop.priority;
    this.status = prop.status;
    this.version = prop.version;
    this.debug = prop.debug;
    this.install_source = prop.install_source;
    this.install_info = prop.install_info;
  }
}
