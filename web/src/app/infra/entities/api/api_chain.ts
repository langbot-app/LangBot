export interface APIChain {
  uuid: string;
  name: string;
  description?: string;
  chain_config: APIChainItem[];
  health_check_interval: number;
  health_check_enabled: boolean;
  created_at?: string;
  updated_at?: string;
  statuses?: APIChainStatus[];
}

export interface APIChainKeyPriority {
  index: number;
  priority: number;
}

export interface APIChainModelConfig {
  model_name: string;
  priority: number;
  api_key_indices?: APIChainKeyPriority[];
}

export interface APIChainItem {
  provider_uuid: string;
  priority: number;
  is_aggregated: boolean;
  max_retries: number;
  timeout_ms: number;
  /** Per-model configuration (optional). Empty = use original query model */
  model_configs?: APIChainModelConfig[];
}

export interface APIChainStatus {
  provider_uuid: string;
  /** null = provider-level, non-null = specific model */
  model_name: string | null;
  /** null = round-robin, non-null = specific API key index */
  api_key_index: number | null;
  is_healthy: boolean;
  failure_count: number;
  last_failure_time?: string;
  last_success_time?: string;
  last_health_check_time?: string;
  last_error_message?: string;
  /** True when the last health-check probe itself failed (not a normal request failure) */
  health_check_last_failed?: boolean;
}

export interface CreateAPIChainRequest {
  name: string;
  description?: string;
  chain_config: APIChainItem[];
  health_check_interval?: number;
  health_check_enabled?: boolean;
}

export interface UpdateAPIChainRequest {
  name?: string;
  description?: string;
  chain_config?: APIChainItem[];
  health_check_interval?: number;
  health_check_enabled?: boolean;
}
