/**
 * Types for the operation traceability surface.
 *
 * The backend stores one append-only row per traced operation and answers
 * "what was changed into what" through the ``changes`` diff. All
 * human-readable strings arrive as i18n keys so the panel owns the copy.
 */

/** Capture levels, ordered by increasing scope. */
export type OperationLevel = 0 | 1 | 2;

export interface OperationLevelOption {
  level: OperationLevel;
  /** Frontend translation key, e.g. ``operationTrace.levels.read``. */
  i18n_key: string;
}

export interface OperationLogLimits {
  min_retention_days: number;
  max_retention_days: number;
  min_max_rows: number;
  max_max_rows: number;
  min_dedupe_window_seconds: number;
  max_dedupe_window_seconds: number;
}

export interface OperationGovernance {
  configured_level: OperationLevel;
  configured_level_name: string;
  retention_days: number;
  max_rows: number;
  /** Seconds during which an identical observation is collapsed into one row. */
  dedupe_window_seconds: number;
  supported_levels: OperationLevelOption[];
  limits: OperationLogLimits;
}

export interface OperationChangeField {
  field: string;
  before: unknown;
  after: unknown;
}

export interface OperationLogRecord {
  id: number;
  /** Whether the stored hash still matches the row content. */
  integrity_ok: boolean;
  /** Whether this row still links to its predecessor correctly. */
  chain_ok: boolean;
  /** Either check failed: the card is flagged as possibly tampered. */
  tampered: boolean;
  record_hash: string | null;
  actor_account_uuid: string | null;
  actor_name: string | null;
  actor_role: string | null;
  http_method: string | null;
  action: string | null;
  /** Translation key resolved by the panel, e.g. ``operationTrace.actions.view``. */
  action_i18n_key: string;
  resource_type: string | null;
  resource_id: string | null;
  level: OperationLevel;
  level_name: string;
  outcome: 'ok' | 'denied' | 'error';
  status_code: number | null;
  summary: string | null;
  changes: OperationChangeField[];
  duration_ms: number;
  created_at: string | null;
}

export interface OperationLogPage {
  records: OperationLogRecord[];
  total: number;
  limit: number;
  offset: number;
  /** How many records on this page failed hash or chain verification. */
  tampered_count: number;
}

export interface OperationLogFilters {
  actions: string[];
  resource_types: string[];
  actors: { account_uuid: string; name: string }[];
}

export interface OperationLogQuery {
  limit?: number;
  offset?: number;
  action?: string;
  resource_type?: string;
  actor?: string;
  level?: OperationLevel;
  since?: string;
  until?: string;
}
