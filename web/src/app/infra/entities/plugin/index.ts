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
  install_info: Record<string, any>;
  components: PluginComponent[];
}

export interface PluginComponent {
  component_config: object;
  manifest: {
    manifest: ComponentManifest;
  };
}

// A single log line captured from a running plugin's stderr.
export interface PluginLogEntry {
  ts: number;
  level: string;
  text: string;
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
  mcp_id?: string;
  skill_id?: string;
  author: string;
  name: string;
  label: I18nObject;
  description: I18nObject;
  icon: string;
  repository: string;
  tags: string[];
  install_count: number;
  like_count?: number;
  hot_score?: number;
  latest_version: string;
  components: Record<string, number>;
  runner_usages?: RunnerUsage[];
  status: PluginV4Status;
  type?: 'plugin' | 'mcp' | 'skill';
  created_at: string;
  updated_at: string;
}

export type RunnerUsage = 'agent' | 'event';

/** Unknown usage metadata must not become an install recommendation. */
export function supportsRunnerUsage(
  plugin: PluginV4,
  usage: RunnerUsage,
): boolean {
  return Boolean(
    plugin.components?.Runner &&
    Array.isArray(plugin.runner_usages) &&
    plugin.runner_usages.includes(usage),
  );
}
