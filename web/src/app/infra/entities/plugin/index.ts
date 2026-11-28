import { ComponentManifest, I18nObject } from '@/app/infra/entities/common';

export interface Plugin {
  permission_status?: {
    compatibility_mode: boolean;
    pending_confirmation: boolean;
  };
  // The runtime moves unmounted → mounted → initialized; initialized is ready.
  status: 'initialized' | 'mounted' | 'unmounted';
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
  /** Declared LangBot range vs. this Core; informational only. */
  compatibility?: PluginCompatibility;
}

export interface PluginComponent {
  component_config: object;
  manifest: {
    manifest: ComponentManifest;
  };
}

/** One public URL exposed by a plugin's Webhook component. */
export interface PluginWebhook {
  name: string;
  label: I18nObject;
  description: I18nObject;
  webhook_url: string;
  webhook_full_url: string;
  extra_webhook_full_url: string;
  enabled: boolean;
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
  /** Reassigns the published plugin author (publishes under a new identity). */
  author?: string;
  /** SPDX license identifier (e.g. MIT, Apache-2.0). */
  license?: string;
  /** Archive-relative icon path (e.g. assets/icon.png). */
  icon?: string;
  /** A data URL of an uploaded replacement icon. */
  icon_base64?: string;
}

/** Connection state + pre-fill data for the upload page. */
export interface PluginSpaceUploadConfig {
  /** 'debug' or the installation source ('local' | 'github' | 'marketplace'). */
  source?: string;
  /** Whether this plugin can be shared (debug, local or GitHub installs). */
  shareable?: boolean;
  debug: boolean;
  metadata: {
    author: string;
    name: string;
    label?: I18nObject | string;
    description?: I18nObject | string;
    version?: string;
    repository?: string;
    license?: string;
  };
  space_connected: boolean;
  has_creator_profile: boolean;
  creator_slug?: string | null;
  author_matches: boolean;
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
  certification_status?: string;
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
  /**
   * Newest release compatible with this Core (Space LANG-696). `null` when no
   * release is compatible; absent on Space deployments that predate it.
   */
  compatible_version?: string | null;
  components: Record<string, number>;
  runner_usages?: RunnerUsage[];
  status: PluginV4Status;
  type?: 'plugin' | 'mcp' | 'skill';
  created_at: string;
  updated_at: string;
}

export type RunnerUsage = 'agent' | 'event';

/** One entry of a marketplace plugin's version history. */
export interface MarketplacePluginVersion {
  version: string;
  langbot_version_min?: string | null;
  langbot_version_max?: string | null;
  /** Present only when the request carried the Core version. */
  compatible?: boolean;
  created_at?: string;
}

/**
 * The marketplace version this Core should install or offer as an update.
 * Falls back to `latest_version` for Space deployments without
 * `compatible_version`; returns null when Space reports no compatible release.
 */
export function installableVersion(
  plugin: Pick<PluginV4, 'latest_version' | 'compatible_version'>,
): string | null {
  if (plugin.compatible_version !== undefined) {
    return plugin.compatible_version || null;
  }
  return plugin.latest_version || null;
}

/** Compatibility of an installed or uploaded package with this Core. */
export interface PluginCompatibility {
  status: 'compatible' | 'incompatible' | 'unspecified' | 'invalid';
  current: string;
  min: string | null;
  max: string | null;
}

export function isPluginIncompatible(
  compatibility: PluginCompatibility | null | undefined,
): boolean {
  return (
    compatibility?.status === 'incompatible' ||
    compatibility?.status === 'invalid'
  );
}

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
