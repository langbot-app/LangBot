export type ExtensionType = 'plugin' | 'mcp' | 'skill';

export interface IExtensionCardVO {
  permission_status?: {
    compatibility_mode: boolean;
    pending_confirmation: boolean;
  };
  id: string;
  author: string;
  label: string;
  name: string;
  description: string;
  version: string;
  enabled: boolean;
  type: ExtensionType;
  iconURL?: string;
  install_source?: string;
  install_info?: Record<string, unknown>;
  status?: string;
  debug?: boolean;
  hasUpdate?: boolean;
  runtimeStatus?: 'connecting' | 'connected' | 'error' | 'disabled';
  tools?: number;
  mode?: 'stdio' | 'sse' | 'http' | 'remote';
}

export class ExtensionCardVO implements IExtensionCardVO {
  permission_status?: {
    compatibility_mode: boolean;
    pending_confirmation: boolean;
  };
  id: string;
  author: string;
  label: string;
  name: string;
  description: string;
  version: string;
  enabled: boolean;
  type: ExtensionType;
  iconURL?: string;
  install_source?: string;
  install_info?: Record<string, unknown>;
  status?: string;
  debug?: boolean;
  hasUpdate?: boolean;
  runtimeStatus?: 'connecting' | 'connected' | 'error' | 'disabled';
  tools?: number;
  mode?: 'stdio' | 'sse' | 'http' | 'remote';

  constructor(prop: IExtensionCardVO) {
    this.permission_status = prop.permission_status;
    this.id = prop.id;
    this.author = prop.author;
    this.label = prop.label;
    this.name = prop.name;
    this.description = prop.description;
    this.version = prop.version;
    this.enabled = prop.enabled;
    this.type = prop.type;
    this.iconURL = prop.iconURL;
    this.install_source = prop.install_source;
    this.install_info = prop.install_info;
    this.status = prop.status;
    this.debug = prop.debug;
    this.hasUpdate = prop.hasUpdate;
    this.runtimeStatus = prop.runtimeStatus;
    this.tools = prop.tools;
    this.mode = prop.mode;
  }
}
