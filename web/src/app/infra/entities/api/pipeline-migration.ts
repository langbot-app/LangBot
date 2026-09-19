export type PipelineMigrationState =
  | 'ready'
  | 'needs_plugin'
  | 'blocked'
  | 'already_current'
  | 'not_legacy'
  | 'activation_pending';

export interface PipelineMigrationIssue {
  code: string;
  field?: string | null;
}

export interface PipelineMigrationItem {
  pipeline_uuid: string;
  name: string;
  state: PipelineMigrationState;
  legacy_runner: string | null;
  target_runner_id: string | null;
  target_plugin: { author: string; name: string; version: string } | null;
  changed_paths: string[];
  blockers: PipelineMigrationIssue[];
  warnings: PipelineMigrationIssue[];
  preview_token: string | null;
}

export interface PipelineMigrationPreview {
  planner_version: string;
  workspace_uuid: string;
  items: PipelineMigrationItem[];
  total: number;
}

export type PipelineMigrationRequest =
  | { confirmed: true; all: true; install_plugins: boolean }
  | {
      confirmed: true;
      items: { pipeline_uuid: string; preview_token: string }[];
    };

export interface PipelineMigrationResult {
  pipeline_uuid: string;
  state:
    | 'pending'
    | 'migrated'
    | 'already_current'
    | 'blocked'
    | 'stale'
    | 'failed'
    | 'activation_pending';
  code: string | null;
}

export interface PipelineMigrationTaskMetadata {
  kind: 'pipeline_migration';
  phase?: 'installing' | 'migrating' | 'finished';
  results: PipelineMigrationResult[];
  installations?: MigrationInstallation[];
}

export interface MigrationInstallation {
  author: string;
  name: string;
  version: string;
  status: 'installing' | 'completed' | 'failed';
  stage: string;
  code: string | null;
  progress_percent?: number;
  download_current?: number;
  download_total?: number;
  download_speed?: number;
  deps_total?: number;
  started_at: number;
  updated_at: number;
  finished_at: number | null;
  steps: { stage: string; started_at: number; finished_at: number | null }[];
}
