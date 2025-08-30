import { ComponentManifest, I18nObject } from '@/app/infra/entities/common';

export interface Plugin {
  status: 'intialized' | 'mounted' | 'unmounted';
  priority: number;
  plugin_config: object;
  manifest: {
    manifest: ComponentManifest;
  };
  debug: boolean;
  enabled: boolean;
  install_source: string;
  install_info: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  components: PluginComponent[];
}

export interface PluginComponent {
  component_config: object;
  manifest: {
    manifest: ComponentManifest;
  };
}

// marketplace plugin v4
export enum PluginV4Status {
  Any = 'any',
  Live = 'live',
  Deleted = 'deleted',
}

export interface PluginV4 {
  id: number;
  plugin_id: string;
  author: string;
  name: string;
  label: I18nObject;
  description: I18nObject;
  icon: string;
  repository: string;
  tags: string[];
  install_count: number;
  latest_version: string;
  status: PluginV4Status;
  created_at: string;
  updated_at: string;
}
