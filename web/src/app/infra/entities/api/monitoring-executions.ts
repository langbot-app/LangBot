export type ExecutionSource = 'agent' | 'pipeline' | 'event';
export type ExecutionSourceFilter = 'all' | ExecutionSource;
export type ExecutionModeFilter = 'all' | 'real' | 'debug';

export interface ExecutionUsage {
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
}

export interface ExecutionRow {
  source: ExecutionSource;
  id: string;
  event_id: string | null;
  status: string;
  status_group:
    | 'completed'
    | 'failed'
    | 'running'
    | 'queued'
    | 'cancelled'
    | 'ignored'
    | string;
  title: string;
  input_preview?: string;
  event_type?: string;
  status_reason?: string | null;
  target_kind: 'agent' | 'pipeline' | 'processor' | string;
  target_id: string | null;
  target_name: string | null;
  bot_id: string | null;
  bot_name: string | null;
  pipeline_id: string | null;
  pipeline_name: string | null;
  runner_id: string | null;
  conversation_id: string | null;
  session_id: string | null;
  created_at_ms: number | null;
  started_at_ms: number | null;
  finished_at_ms: number | null;
  duration_ms: number | null;
  usage: ExecutionUsage | null;
  cost: Record<string, unknown> | null;
  queue_name: string | null;
  debug: boolean;
  has_error: boolean;
  platform?: string | null;
  user_id?: string | null;
  user_name?: string | null;
}

export interface ExecutionOverview {
  total: number;
  by_source: { agent: number; pipeline: number };
  by_status: Record<string, number>;
  completed: number;
  failed: number;
  running: number;
  queued: number;
  cancelled: number;
  ignored: number;
  waiting: number;
  success_rate: number | null;
  denominator: number;
  p50_duration_ms: number | null;
  p95_duration_ms: number | null;
  duration_sample: number;
  debug: number;
  real: number;
}

export interface TokenCoverage {
  total_tokens: number;
  calls: number;
  calls_with_usage: number;
}

export interface ExecutionSummary {
  executions: ExecutionOverview;
  tokens: TokenCoverage;
}

export interface ExecutionListResult {
  items: ExecutionRow[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  summary: ExecutionSummary;
}

export interface PipelineMessageRow {
  id: string;
  timestamp: string;
  bot_id: string;
  bot_name: string;
  pipeline_id: string;
  pipeline_name: string;
  message_content: string;
  session_id: string;
  status: string;
  level: string;
  platform?: string | null;
  user_id?: string | null;
  user_name?: string | null;
  runner_name?: string | null;
  role?: string | null;
}

export interface ExecutionCallRow {
  id: string;
  timestamp: string;
  /** LLM/tool calls report a status; error records carry `error_type` instead. */
  status?: string | null;
  duration?: number | null;
  error_type?: string | null;
  error_message?: string | null;
  [key: string]: unknown;
}

export type ExecutionSection =
  | 'inputs'
  | 'outputs'
  | 'deliveries'
  | 'conversation'
  | 'related'
  | 'events'
  | 'llm_calls'
  | 'tool_calls'
  | 'errors';

export interface ExecutionDetailItem {
  id: string | number;
  timestamp_ms?: number | null;
  role?: string;
  origin?: string;
  event_type?: string;
  actor_name?: string;
  actor_id?: string;
  content?: unknown;
  attachments?: unknown[];
  status?: string;
  type?: string;
  sequence?: number;
  data?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  delivery?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ExecutionDetailPage {
  items: ExecutionDetailItem[];
  has_more: boolean;
  next_offset: number;
}

export interface ExecutionDetail {
  source: ExecutionSource;
  row: ExecutionRow;
  pages: Partial<Record<ExecutionSection, ExecutionDetailPage>>;
  legacy_context: boolean;
}

export type AgentExecutionDetail = ExecutionDetail & { source: 'agent' };
export type PipelineExecutionDetail = ExecutionDetail & { source: 'pipeline' };

export interface InflightSnapshot {
  items: (ExecutionRow & { progress_event?: string })[];
  active_total: number;
  truncated: boolean;
}
export type InflightFrame =
  | { kind: 'snapshot'; data: InflightSnapshot }
  | { kind: 'heartbeat' | 'unavailable' };
