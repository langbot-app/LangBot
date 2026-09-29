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

/** Editable plugin metadata for the "upload to LangBot Space" page. */
export interface PluginManifestOverrides {
  /** A single string applies to all locales; an object targets specific ones. */
  label?: string | I18nObject;
  description?: string | I18nObject;
  version?: string;
  repository?: string;
  /** Archive-relative icon path (e.g. assets/icon.png). */
  icon?: string;
  /** A data URL of an uploaded replacement icon. */
  icon_base64?: string;
}

/** Connection state + pre-fill data for the upload page. */
export interface PluginSpaceUploadConfig {
  debug: boolean;
  metadata: {
    author: string;
    name: string;
    label?: I18nObject | string;
    description?: I18nObject | string;
    version?: string;
    repository?: string;
  };
  space_connected: boolean;
  cloud_service_url: string;
}

export interface PluginGithubSyncPayload {
  repo_url?: string;
  token?: string;
  branch?: string;
  commit_message?: string;
  manifest_overrides?: PluginManifestOverrides;
}

export interface PluginGithubSyncResult {
  committed: boolean;
  pushed: boolean;
  branch: string;
  remote_url: string;
  commit_sha: string;
  message: string;
  warnings: string[];
}

export interface PluginSpaceUploadPayload extends PluginGithubSyncPayload {
  sync_github?: boolean;
  changelog?: string;
}

export interface PluginSpaceUploadResult {
  submission: Record<string, unknown>;
  git: PluginGithubSyncResult | null;
  filename: string;
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
