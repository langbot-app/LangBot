import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import { PipelineConfigTab } from '@/app/infra/entities/pipeline';
import { I18nObject } from '@/app/infra/entities/common';
import { Message } from '@/app/infra/entities/message';
import { Plugin, PluginV4 } from '@/app/infra/entities/plugin';

export interface ApiResponse<T> {
  code: number;
  data: T;
  msg: string;
}

export interface AsyncTaskCreatedResp {
  task_id: number;
}

export interface GithubRefEntry {
  name: string;
  commit_sha: string;
}

export interface GithubRefsResp {
  owner: string;
  repo: string;
  default_branch: string;
  requested_ref: string;
  source_subdir: string;
  branches: GithubRefEntry[];
  tags: GithubRefEntry[];
  truncated: boolean;
  source: {
    kind: 'direct' | 'mirror';
    host: string;
    latency_ms: number;
  };
}

export interface ApiRespProviderRequesters {
  requesters: Requester[];
}

export interface ApiRespProviderRequester {
  requester: Requester;
}

export interface Requester {
  name: string;
  label: I18nObject;
  description: I18nObject;
  icon?: string;
  spec: {
    config: IDynamicFormItemSchema[];
    provider_category: string;
    support_type?: string[];
    alias?: string;
  };
}

export interface ApiRespProviderLLMModels {
  models: LLMModel[];
}

export interface ApiRespProviderLLMModel {
  model: LLMModel;
}

export interface ModelProvider {
  uuid: string;
  name: string;
  requester: string;
  base_url: string;
  api_keys: string[];
  llm_count?: number;
  embedding_count?: number;
  rerank_count?: number;
  asr_count?: number;
  tts_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface ApiRespModelProviders {
  providers: ModelProvider[];
}

export interface ApiRespModelProvider {
  provider: ModelProvider;
}

export interface ScannedProviderModel {
  id: string;
  name: string;
  type: 'llm' | 'embedding';
  abilities?: string[];
  display_name?: string;
  description?: string;
  context_length?: number | null;
  owned_by?: string;
  input_modalities?: string[];
  output_modalities?: string[];
  already_added: boolean;
}

export interface ProviderScanDebugInfo {
  request?: {
    method?: string;
    url?: string;
    headers?: Record<string, string>;
  };
  response?: unknown;
}

export interface ApiRespScannedProviderModels {
  models: ScannedProviderModel[];
  debug?: ProviderScanDebugInfo;
}

export interface LLMModel {
  uuid: string;
  name: string;
  provider_uuid: string;
  provider?: ModelProvider;
  abilities?: string[];
  context_length?: number | null;
  reasoning_config?: ReasoningConfig;
  reasoning_capabilities?: ReasoningCapabilities;
  extra_args?: object;
}

export type ReasoningLevel =
  | 'provider_default'
  | 'disabled'
  | 'enabled'
  | 'minimal'
  | 'low'
  | 'medium'
  | 'high'
  | 'xhigh'
  | 'max';

export interface ReasoningConfig {
  level: ReasoningLevel;
}

export interface ReasoningCapabilities {
  supported: boolean;
  levels: ReasoningLevel[];
  legacy_levels?: ReasoningLevel[];
  source: 'litellm' | 'provider' | 'manual' | 'unknown';
}

export interface ApiRespProviderEmbeddingModels {
  models: EmbeddingModel[];
}

export interface ApiRespProviderEmbeddingModel {
  model: EmbeddingModel;
}

export interface EmbeddingModel {
  uuid: string;
  name: string;
  provider_uuid: string;
  provider?: ModelProvider;
  extra_args?: object;
}

export interface ApiRespProviderRerankModels {
  models: RerankModel[];
}

export interface ApiRespProviderRerankModel {
  model: RerankModel;
}

export interface RerankModel {
  uuid: string;
  name: string;
  provider_uuid: string;
  provider?: ModelProvider;
  extra_args?: object;
}

export interface ApiRespProviderASRModels {
  models: ASRModel[];
}

export interface ApiRespProviderASRModel {
  model: ASRModel;
}

export interface ASRModel {
  uuid: string;
  name: string;
  provider_uuid: string;
  provider?: ModelProvider;
  extra_args?: object;
}

export interface ApiRespProviderTTSModels {
  models: TTSModel[];
}

export interface ApiRespProviderTTSModel {
  model: TTSModel;
}

export interface TTSModel {
  uuid: string;
  name: string;
  provider_uuid: string;
  provider?: ModelProvider;
  extra_args?: object;
}

export interface LangBotModelAvailability {
  up: boolean | null;
  last_probed_at: string | null;
  latency_ms: number;
  http_code: number;
}

export interface LangBotModelAvailabilityItem {
  uuid: string;
  model_id: string;
  category: string | null;
  listed_at?: string | null;
  input_credits: number | null;
  output_credits: number | null;
  availability: LangBotModelAvailability;
}

export interface ApiRespLangBotModelAvailability {
  models: LangBotModelAvailabilityItem[];
}

export interface ApiRespPipelines {
  pipelines: Pipeline[];
}

export type AgentKind =
  'agent' | 'pipeline' | 'event_processor' | 'command_processor' | 'workflow';

export interface RunnerDescriptor {
  id: string;
  label: Record<string, string>;
  plugin_author: string;
  plugin_name: string;
  config_schema: import('../form/dynamic').IDynamicFormItemSchema[];
  supported_event_patterns: string[];
  permissions?: {
    workspace_operations?: string[];
    [key: string]: unknown;
  };
}

export interface ProcessorRun {
  run_id: string;
  binding_id?: string;
  runner_id?: string;
  usage?: {
    prompt_tokens?: number | null;
    completion_tokens?: number | null;
    total_tokens?: number | null;
  } | null;
  status: string;
  status_reason?: string;
  created_at: number;
  started_at?: number | null;
  finished_at?: number | null;
  created_at_ms?: number | null;
  started_at_ms?: number | null;
  finished_at_ms?: number | null;
  metadata: {
    event_type?: string;
    source?: string;
    input?: { text?: string; contents?: unknown[]; attachments?: unknown[] };
    input_event?: unknown;
    delivery?: unknown;
    command?: string;
  };
}

export interface CommandOutput {
  text?: string;
  error?: string;
  image_url?: string;
  image?: string;
  file_url?: string;
  file_name?: string;
}

export interface CommandDebugResult {
  run_id: string | null;
  status: 'completed' | 'failed';
  command: string;
  outputs: CommandOutput[];
  error: string | null;
}

export interface ProcessorRunEvent {
  sequence: number;
  type: string;
  data: Record<string, unknown>;
}

export interface ProcessorRunPage {
  items: ProcessorRun[];
  total?: number;
  next_cursor: number | null;
  has_more: boolean;
}

export interface ProcessorRunEventPage {
  run: ProcessorRun;
  items: ProcessorRunEvent[];
  next_cursor: number | null;
  has_more: boolean;
}

export interface AgentCapability {
  supported_event_patterns: string[];
  message_only: boolean;
}

export interface Agent {
  uuid?: string;
  name: string;
  description: string;
  emoji?: string;
  kind: AgentKind;
  component_ref?: string | null;
  config?: Record<string, unknown>;
  supported_event_patterns?: string[];
  capability?: AgentCapability;
  created_at?: string;
  updated_at?: string;
}

export type CreateAgentRequest = Pick<
  Agent,
  'name' | 'description' | 'emoji' | 'kind' | 'component_ref' | 'config'
> & {
  runner_id?: string;
};

export interface ApiRespAgents {
  agents: Agent[];
}

export interface ApiRespAgent {
  agent: Agent;
}

export interface WorkspaceOperationItem {
  id: string;
  domain: string;
  label: Record<string, string>;
  summary: string;
  risk: 'read' | 'write' | 'dangerous';
  permission: string;
  grantable: boolean;
}

export interface DomainMeta {
  domain: string;
  label: Record<string, string>;
  summary?: string;
  count?: number;
}

export interface GetAgentMetadataResponseData {
  workspace_operation_grants?: Record<string, string[]>;
  event_processors?: RunnerDescriptor[];
  command_processors?: CommandProcessorDescriptor[];
  runner_config?: PipelineConfigTab;
  platform_tools: AgentPlatformTool[];
  host_tools?: PluginTool[] | null;
  workspace_operations?: WorkspaceOperationItem[];
  domains?: DomainMeta[];
  kinds: Array<{
    name: AgentKind;
    supported_event_patterns: string[];
    message_only: boolean;
  }>;
}

export interface AgentPlatformTool {
  name: string;
  api: string;
  scope: 'event' | 'platform';
  category: string;
  risk: 'read' | 'write' | 'dangerous';
  label: I18nObject;
  description: I18nObject;
  event_patterns: string[];
  parameters: Record<string, unknown>;
}

export interface Pipeline {
  uuid?: string;
  name: string;
  description: string;
  for_version?: string;
  config: object;
  stages?: string[];
  is_default?: boolean;
  created_at?: string;
  updated_at?: string;
  emoji?: string;
}

export interface ApiRespPlatformAdapters {
  adapters: Adapter[];
}

export interface ApiRespPlatformAdapter {
  adapter: Adapter;
}

export interface Adapter {
  name: string;
  label: I18nObject;
  description: I18nObject;
  icon?: string;
  spec: {
    categories?: string[];
    legacy?: boolean;
    help_links?: Record<string, string>;
    supported_events?: string[];
    supported_apis?: string[];
    command_registration?: PlatformCommandCapability;
    platform_specific_apis?: { action: string }[];
    config: IDynamicFormItemSchema[];
  };
}

export interface ApiRespPlatformBots {
  bots: Bot[];
}

export interface ApiRespPlatformBot {
  bot: Bot;
}

export interface Bot {
  uuid?: string;
  name: string;
  description: string;
  enable?: boolean;
  adapter: string;
  adapter_config: object;
  event_bindings?: EventBinding[];
  plugin_processors?: PluginProcessorBinding[];
  command_settings?: BotCommandSettings;
  message_policy?: MessagePolicy;
  platform_command_sync?: PlatformCommandSync;
  platform_command_registration?: {
    rejected?: { name: string; reason: string }[];
    error?: string;
  };
  created_at?: string;
  updated_at?: string;
  adapter_runtime_values?: object;
}

export interface BotCommandProcessorBinding {
  processor_uuid: string;
  enabled: boolean;
}

export interface CommandComponentDescriptor {
  name: string;
  label: Record<string, string>;
  description?: Record<string, string> | null;
  config_schema: import('../form/dynamic').IDynamicFormItemSchema[];
}

export interface CommandProcessorDescriptor {
  id: string;
  plugin_id: string;
  commands: CommandComponentDescriptor[];
}

export type CommandPermission = 'everyone' | 'admins';

export interface BotCommandSettings {
  enabled: boolean;
  prefixes: string[];
  processors: BotCommandProcessorBinding[];
  platform_commands?: { enabled: boolean; selected: string[] };
  /** Built-in (system) commands by name; missing entries use the defaults. */
  builtin?: Record<string, { enabled: boolean; permission: CommandPermission }>;
  /** Plugin command permissions keyed by `author/plugin/command`. */
  plugin_permissions?: Record<string, CommandPermission>;
  /** What a sender without permission gets: nothing, or a notice. */
  denied_reply?: 'silent' | 'notice';
}

export interface BuiltinCommandDescriptor {
  name: string;
  aliases: string[];
  group: 'session' | 'info' | 'admin';
  default_enabled: boolean;
  default_permission: CommandPermission;
  label: import('../common').I18nObject;
  description: import('../common').I18nObject;
}

export interface PlatformCommandCapability {
  max_commands: number;
  name_pattern: string;
  description_max_length: number;
  multilingual: boolean;
  scopes: boolean;
  lowercase?: boolean;
}

export interface PlatformCommandSync {
  synced_at?: string;
  error?: string | null;
  skipped?: boolean;
  rejected?: { name: string; reason: string }[];
}

export interface PluginProcessorBinding {
  processor_uuid: string;
  enabled: boolean;
}

export interface EventBinding {
  id?: string;
  event_pattern: string;
  target_type: Exclude<AgentKind, 'command_processor'> | 'discard';
  target_uuid: string;
  filters?: Array<Record<string, unknown>>;
  priority: number;
  enabled: boolean;
  description?: string;
  order?: number;
  /** Partial message policy overriding the bot's for this route; null clears it. */
  policy?: MessagePolicyOverride | null;
}

export type MessagePolicySectionName = 'trigger' | 'safety' | 'output';

export interface PluginSelection {
  enable_all: boolean;
  plugins: { author: string; name: string }[];
}

/** A bot's message policy: sections of blocks, as in the policy metadata. */
export interface MessagePolicy {
  trigger?: Record<string, Record<string, unknown>>;
  safety?: Record<string, Record<string, unknown>>;
  output?: Record<string, Record<string, unknown>>;
  plugins?: PluginSelection;
}

export interface MessagePolicyOverride extends Omit<MessagePolicy, 'plugins'> {
  plugins?: PluginSelection | null;
}

export interface MessagePolicyMetadata {
  configs: import('../pipeline').PipelineConfigTab[];
  default: MessagePolicy;
  neutral: MessagePolicy;
}

/** Where a hook takes effect: Chat (``messaging``), Agent or command. */
export type HookProcessor = 'messaging' | 'agent' | 'command';

export interface PluginRegistration {
  commands?: string[] | null;
  events?: string[] | null;
  event_processors?: Record<string, HookProcessor[]> | null;
}

export interface ApiRespPluginRegistrations {
  /** null when the Plugin Runtime cannot report registrations. */
  plugins: Record<string, PluginRegistration> | null;
}

export interface BotRouteDryRunRequest {
  event_type: string;
  payload?: Record<string, unknown>;
  event_bindings?: EventBinding[];
}

export interface BotRouteDryRunTarget {
  target_type: EventBinding['target_type'];
  target_uuid?: string | null;
  target_name?: string | null;
  kind?: AgentKind | 'discard' | null;
}

export interface BotRouteDryRunResult {
  matched: boolean;
  target?: BotRouteDryRunTarget | null;
  binding_id?: string | null;
  event_pattern?: string | null;
  target_type?: EventBinding['target_type'] | null;
  target_uuid?: string | null;
  reason?: string | null;
  failure_code?: string | null;
  diagnostic_steps: string[];
  diagnostic_details?: Array<Record<string, unknown>>;
  matched_binding_id?: string | null;
  matched_binding_index?: number | null;
}

export interface BotEventRouteStatus {
  binding_id?: string | null;
  event_pattern?: string | null;
  event_type?: string | null;
  target_type?: EventBinding['target_type'] | string | null;
  target_uuid?: string | null;
  last_status?:
    | 'matched'
    | 'delivered'
    | 'discarded'
    | 'failed'
    | 'not_matched'
    | string
    | null;
  failure_code?: string | null;
  reason?: string | null;
  run_id?: string | null;
  timestamp?: number | null;
  seq_id?: number | null;
  level?: string | null;
  message?: string | null;
  order?: number | null;
  enabled?: boolean;
  current?: boolean;
  /** Last 24h `message.received` events whose primary route was this rule. */
  counts_24h?: BotRouteCounts;
}

export interface BotRouteCounts {
  ai: number;
  command: number;
  plugin: number;
  policy: number;
}

/** One item of the workspace "upgrade check" (message policy migration). */
export type UpgradeCheckCode =
  | 'command_prefix_changed'
  | 'plugin_command_collision'
  | 'command_admin_missing'
  | 'command_plugin_enabled'
  | 'equivalent_route_policies'
  | 'chat_settings_moved';

export type UpgradeCheckAction =
  | 'restore_prefixes'
  | 'uninstall_essential'
  | 'remove_plugin'
  | 'promote_route_policy';

export interface UpgradeCheckItem {
  id: string;
  code: UpgradeCheckCode | string;
  params: {
    bot_uuid?: string;
    original_prefixes?: string[];
    essential_installed?: boolean;
    names?: string[];
    plugin?: string;
    /** Route ids; `null` is the bot default. */
    scopes?: (string | null)[];
    route_ids?: string[];
    changes_unrouted_commands?: boolean;
    routes?: { bot_uuid: string; route_id: string; chat_uuid?: string }[];
    [key: string]: unknown;
  };
  actions: (UpgradeCheckAction | string)[];
  confirmed: boolean;
}

export interface UpgradeChecksResponse {
  items: UpgradeCheckItem[];
  reports: Record<string, unknown>[];
}

export interface BotEventRouteStatusResponse {
  routes: BotEventRouteStatus[];
  unmatched_events: BotEventRouteStatus[];
  stale_routes: BotEventRouteStatus[];
}

export interface ApiRespKnowledgeBases {
  bases: KnowledgeBase[];
}

export interface ApiRespKnowledgeBase {
  base: KnowledgeBase;
}

export interface KnowledgeBase {
  uuid?: string;
  name: string;
  description: string;
  created_at?: string;
  updated_at?: string;
  emoji?: string;
  // New unified fields
  knowledge_engine_plugin_id?: string;
  creation_settings?: Record<string, unknown>;
  retrieval_settings?: Record<string, unknown>;
  initialized?: boolean;
  defer_initialization?: boolean;
  initialize_engine?: boolean;
  knowledge_engine?: KnowledgeEngineInfo;
}

// Knowledge Engine types
export interface KnowledgeEngineInfo {
  plugin_id: string | null;
  name: I18nObject;
  capabilities: string[];
}

export interface KnowledgeEngine {
  plugin_id: string;
  name: I18nObject;
  description?: I18nObject;
  capabilities: string[];
  // Schema format: Array of form field definitions (IDynamicFormItemSchema-like)
  // Each item: { name, label, type, required, default, description?, options? }
  creation_schema?: unknown[];
  retrieval_schema?: unknown[];
}

export interface ApiRespKnowledgeEngines {
  engines: KnowledgeEngine[];
}

export interface ParserInfo {
  plugin_id: string;
  name: I18nObject;
  description?: I18nObject;
  supported_mime_types: string[];
}

export interface ApiRespParsers {
  parsers: ParserInfo[];
}

export interface ApiRespKnowledgeBaseFiles {
  files: KnowledgeBaseFile[];
}

export interface KnowledgeBaseFile {
  uuid: string;
  file_name: string;
  status: string;
}

// plugins
export interface ApiRespPlugins {
  plugins: Plugin[];
}

export type ExtensionItem =
  | { type: 'plugin'; plugin: Plugin }
  | { type: 'mcp'; server: MCPServer }
  | { type: 'skill'; skill: Skill };

export interface ApiRespExtensions {
  extensions: ExtensionItem[];
}

export interface ApiRespPlugin {
  plugin: Plugin;
}

// export interface Plugin {
//   author: string;
//   name: string;
//   description: I18nLabel;
//   label: I18nLabel;
//   version: string;
//   enabled: boolean;
//   priority: number;
//   status: string;
//   tools: object[];
//   event_handlers: object;
//   main_file: string;
//   pkg_path: string;
//   repository: string;
//   config_schema: IDynamicFormItemSchema[];
// }

export interface ApiRespPluginConfig {
  config: object;
}

export interface PluginReorderElement {
  author: string;
  name: string;
  priority: number;
}

// system
export interface SystemLimitation {
  max_bots: number;
  max_pipelines: number;
  max_workflows?: number;
  max_extensions: number;
  max_knowledge_bases?: number;
  /** When non-empty, every pipeline is forced to this Box sandbox-scope
   *  template (e.g. ``{global}``) and the per-pipeline "Sandbox Scope"
   *  selector is locked. Used by SaaS deployments. Empty = no restriction. */
  force_box_session_id_template?: string;
}

export interface WizardProgress {
  step: number;
  selected_scenario?: string | null;
  selected_adapter: string | null;
  created_bot_uuid: string | null;
  created_pipeline_uuid?: string | null;
  bot_saved: boolean;
  message_received?: boolean;
  selected_runner: string | null;
}

export interface ApiRespCloudBanner {
  enabled: boolean;
  /** Visual tone requested by the deployment: info, warning, maintenance. */
  level: 'info' | 'warning' | 'maintenance';
  dismissible: boolean;
  /** Append the dedicated-environment / self-hosting links after the copy. */
  show_links: boolean;
  dedicated_url: string;
  repository_url: string;
  /** Language key (`zh_hans`, `en_us`, ...) -> operator-authored copy. */
  content: Record<string, string>;
}

export interface ApiRespSystemInfo {
  debug: boolean;
  version: string;
  edition: string;
  beta: boolean;
  deployment_mode: 'cloud' | 'oss';
  /** Cloud-only instance notice from `cloud.banner` in config.yaml. Null for
   *  OSS deployments or when the banner is disabled. */
  cloud_banner?: ApiRespCloudBanner | null;
  /** Independent instance-level gate for local stdio MCP transports. */
  mcp_stdio_enabled: boolean;
  cloud_service_url: string;
  enable_marketplace: boolean;
  allow_modify_login_info: boolean;
  disable_models_service: boolean;
  invitation_delivery?: {
    enabled: boolean;
    provider: 'resend' | 'smtp' | null;
  };
  limitation: SystemLimitation;
  /** Public outbound IPs of the deployment (``system.outbound_ips`` in
   *  config.yaml). Shown on adapter config forms whose platform requires
   *  trusted-IP / IP-whitelist settings. Empty = not configured. */
  outbound_ips: string[];
  wizard_status: string; // 'none' | 'skipped' | 'completed'
  wizard_progress: WizardProgress | null;
}

export interface RagMigrationStatusResp {
  needed: boolean;
  internal_kb_count: number;
  external_kb_count: number;
}

export interface ApiRespPluginSystemStatus {
  is_enable: boolean;
  is_connected: boolean;
  plugin_connector_error: string;
}

export interface ApiRespBoxStatus {
  available: boolean;
  /** UI hint: hide the Box runtime status surface for this deployment. */
  hidden?: boolean;
  /** Whether ``box.enabled`` is true in config. When false, the sandbox
   * is deliberately disabled — distinct from "configured but failed". */
  enabled?: boolean;
  profile: string;
  recent_error_count: number;
  connector_error?: string;
  backend?: {
    name: string;
    available: boolean;
  };
  active_sessions?: number;
  managed_processes?: number;
  session_ttl_sec?: number;
}

export interface BoxSessionInfo {
  session_id: string;
  backend_name: string;
  image: string;
  network: string;
  host_path: string | null;
  host_path_mode: string;
  mount_path: string;
  cpus: number;
  memory_mb: number;
  created_at: string;
  last_used_at: string;
}

export interface ApiRespAsyncTasks {
  tasks: AsyncTask[];
}

export interface AsyncTaskRuntimeInfo {
  done: boolean;
  exception?: string;
  /** Structured failure, currently only `plugin_incompatible_langbot_version`. */
  error?: { code: string; details?: Record<string, unknown> };
  result?: object;
  state: string;
}

export interface AsyncTaskTaskContext {
  current_action: string;
  log: string;
  metadata?: Record<string, unknown>;
}

export interface AsyncTask {
  id: number;
  kind: string;
  name: string;
  label: string;
  task_type: string; // system or user
  /** Unix epoch seconds (float) when the task was created. */
  created_at?: number;
  runtime: AsyncTaskRuntimeInfo;
  task_context: AsyncTaskTaskContext;
}

export interface ApiRespUserToken {
  token: string;
}

export interface ApiRespMarketplacePlugins {
  plugins: PluginV4[];
  total: number;
}

export interface ApiRespMarketplacePluginDetail {
  plugin: PluginV4;
}

interface GetPipelineConfig {
  ai: object;
  output: object;
  safety: object;
  speech?: object;
  trigger: object;
}

interface GetPipeline {
  config: GetPipelineConfig;
  created_at: string;
  description: string;
  for_version: string;
  is_default: boolean;
  name: string;
  stages: string[];
  updated_at: string;
  uuid: string;
  emoji?: string;
}

export interface GetPipelineResponseData {
  pipeline: GetPipeline;
}

export interface GetPipelineMetadataResponseData {
  configs: PipelineConfigTab[];
}

export interface ApiRespWebChatMessage {
  message: Message;
}

export interface ApiRespWebChatMessages {
  messages: Message[];
}

export interface RetrieveResultContent {
  type: 'text' | 'image_url' | 'image_base64' | 'file_url';
  text?: string;
  file_name?: string;
  file_url?: string;
  image_url?: string;
  image_base64?: string;
}

export interface RetrieveResult {
  id: string;
  content?: RetrieveResultContent[];
  metadata: {
    file_id?: string;
    text?: string;
    uuid?: string;
    [key: string]: unknown;
  };
  distance: number;
}

export interface ApiRespKnowledgeBaseRetrieve {
  results: RetrieveResult[];
}

// MCP
export interface ApiRespMCPServers {
  servers: MCPServer[];
}

export interface ApiRespMCPServer {
  server: MCPServer;
}

export interface MCPServerExtraArgsSSE {
  url: string;
  headers: Record<string, string>;
  timeout: number;
  ssereadtimeout: number;
  tool_call_timeout_sec?: number;
}

export interface MCPServerExtraArgsStdio {
  command: string;
  args: string[];
  env: Record<string, string>;
  tool_call_timeout_sec?: number;
}

export interface MCPServerExtraArgsHttp {
  url: string;
  headers: Record<string, string>;
  timeout: number;
  tool_call_timeout_sec?: number;
}

// "remote" mode: the user only supplies a URL; the backend auto-detects the
// transport (Streamable HTTP first, falling back to legacy SSE). headers /
// timeout are optional advanced settings.
export interface MCPServerExtraArgsRemote {
  url: string;
  headers?: Record<string, string>;
  timeout?: number;
  tool_call_timeout_sec?: number;
}

export enum MCPSessionStatus {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  ERROR = 'error',
}

export interface MCPServerRuntimeInfo {
  error_code?: string;
  status: MCPSessionStatus;
  error_message?: string;
  /** Stage at which the session failed. Frontends key off this to render
   *  a localized actionable message instead of the raw ``error_message``.
   *  Notable values: ``box_unavailable`` (stdio MCP refused because Box is
   *  disabled / unreachable). See ``MCPSessionErrorPhase`` (backend). */
  error_phase?: string;
  retry_count?: number;
  tool_count: number;
  tools: MCPTool[];
  /** Optional ``box_session_id`` / ``box_enabled`` set when this stdio
   *  server runs inside Box. Absent when Box is unavailable. */
  box_session_id?: string;
  box_enabled?: boolean;
  resource_count: number;
  resources: MCPResource[];
  resource_template_count?: number;
  resource_templates?: MCPResourceTemplate[];
  resource_capabilities?: Record<string, unknown>;
}

export type MCPServer =
  | {
      uuid?: string;
      name: string;
      mode: 'sse';
      enable: boolean;
      extra_args: MCPServerExtraArgsSSE;
      runtime_info?: MCPServerRuntimeInfo;
      /** ${VAR} placeholder names still to fill (community installs). */
      unfilled_inputs?: string[];
      readme?: string;
      created_at?: string;
      updated_at?: string;
    }
  | {
      uuid?: string;
      name: string;
      mode: 'http';
      enable: boolean;
      extra_args: MCPServerExtraArgsHttp;
      runtime_info?: MCPServerRuntimeInfo;
      /** ${VAR} placeholder names still to fill (community installs). */
      unfilled_inputs?: string[];
      readme?: string;
      created_at?: string;
      updated_at?: string;
    }
  | {
      uuid?: string;
      name: string;
      mode: 'remote';
      enable: boolean;
      extra_args: MCPServerExtraArgsRemote;
      runtime_info?: MCPServerRuntimeInfo;
      /** ${VAR} placeholder names still to fill (community installs). */
      unfilled_inputs?: string[];
      readme?: string;
      created_at?: string;
      updated_at?: string;
    }
  | {
      uuid?: string;
      name: string;
      mode: 'stdio';
      enable: boolean;
      extra_args: MCPServerExtraArgsStdio;
      runtime_info?: MCPServerRuntimeInfo;
      /** ${VAR} placeholder names still to fill (community installs). */
      unfilled_inputs?: string[];
      readme?: string;
      created_at?: string;
      updated_at?: string;
    };

export interface MCPTool {
  name: string;
  description: string;
  parameters?: object;
}

export interface MCPResource {
  uri: string;
  name: string;
  title?: string;
  description: string;
  mime_type: string;
  size?: number;
  icons?: object[];
  annotations?: Record<string, unknown>;
  _meta?: Record<string, unknown>;
}

export interface MCPResourceTemplate {
  uri_template: string;
  name: string;
  title?: string;
  description: string;
  mime_type: string;
  icons?: object[];
  annotations?: Record<string, unknown>;
  _meta?: Record<string, unknown>;
}

export interface MCPResourceContent {
  uri: string;
  mime_type: string;
  type: 'text' | 'blob';
  text?: string;
  blob?: string | null;
  bytes?: number;
  truncated?: boolean;
  binary_omitted?: boolean;
  _meta?: Record<string, unknown>;
}

export interface ApiRespMCPResources {
  resources: MCPResource[];
  resource_templates?: MCPResourceTemplate[];
  resource_capabilities?: Record<string, unknown>;
}

export interface ApiRespMCPResourceContents {
  contents: MCPResourceContent[];
  server_name?: string;
  server_uuid?: string;
  uri?: string;
  source?: string;
  bytes?: number;
  truncated?: boolean;
  cache_hit?: boolean;
  warnings?: string[];
}

export interface PluginTool {
  name: string;
  description: string;
  human_desc: string;
  parameters: object;
  source?: 'builtin' | 'plugin' | 'mcp' | 'skill';
  source_name?: string;
  source_id?: string;
}

export interface ApiRespTools {
  tools: PluginTool[];
}

export interface ApiRespToolDetail {
  tool: Omit<PluginTool, 'source' | 'source_id'> & {
    source: NonNullable<PluginTool['source']>;
    source_id: string | null;
  };
}

// ============ Workflow Types ============
export type WorkflowStepType =
  | 'start'
  | 'llm'
  | 'classify'
  | 'extract'
  | 'condition'
  | 'remember'
  | 'reply'
  | 'send'
  | 'http'
  | 'handoff'
  | 'knowledge'
  | 'tts'
  | 'asr'
  | 'random'
  | 'code'
  | 'history'
  | 'platform';

export interface WorkflowStep {
  id: string;
  type: WorkflowStepType;
  name: string;
  config: Record<string, unknown>;
}

export interface WorkflowEdge {
  from: string;
  to: string;
  branch?: string;
}

export interface WorkflowGraph {
  nodes: WorkflowStep[];
  edges: WorkflowEdge[];
}

export interface WorkflowTrigger {
  type: 'message' | 'command' | 'schedule' | 'event' | 'webhook';
  [key: string]: unknown;
}

export interface Workflow {
  uuid: string;
  name: string;
  description?: string | null;
  emoji?: string | null;
  is_enabled?: boolean;
  timezone?: string;
  triggers?: WorkflowTrigger[];
  graph: WorkflowGraph;
  created_at?: string;
  updated_at?: string;
}

export interface WorkflowSummary {
  uuid: string;
  name: string;
  description?: string | null;
  emoji?: string | null;
  is_enabled?: boolean;
  step_count?: number;
  updated_at?: string;
}

export interface WorkflowIssue {
  code: string;
  severity: 'error' | 'warning';
  node_id?: string;
  field?: string;
}

export interface ApiRespWorkflows {
  workflows: WorkflowSummary[];
}

export interface ApiRespWorkflow {
  workflow: Workflow;
  issues: WorkflowIssue[];
}

export interface WorkflowStepRun {
  seq: number;
  node_id: string;
  node_type: WorkflowStepType;
  node_name: string;
  status: 'completed' | 'failed' | 'skipped' | 'running';
  branch?: string | null;
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  error?: string | null;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
}

export interface WorkflowHandoff {
  target_type: 'chat' | 'agent' | 'workflow';
  target_uuid: string;
  name?: string;
}

export interface WorkflowExecution {
  uuid: string;
  workflow_uuid: string;
  status: 'running' | 'completed' | 'failed' | 'waiting';
  trigger: string;
  input_text?: string | null;
  bot_uuid?: string | null;
  session_id?: string | null;
  handoff?: WorkflowHandoff | null;
  error?: string | null;
  started_at?: string;
  finished_at?: string | null;
  duration_ms?: number | null;
  steps?: WorkflowStepRun[];
}

export interface ApiRespWorkflowExecutions {
  executions: WorkflowExecution[];
  total: number;
}

export interface ApiRespWorkflowExecution {
  execution: WorkflowExecution;
}

export interface WorkflowTestRequest {
  text: string;
  session_type: 'person' | 'group';
  graph?: WorkflowGraph;
}

export interface ApiRespWorkflowTest {
  execution_uuid: string;
  status: WorkflowExecution['status'];
  error?: string | null;
  replies: string[];
  handoff?: WorkflowHandoff | null;
  steps: WorkflowStepRun[];
}

export interface CreateWorkflowRequest {
  name: string;
  description?: string;
  emoji?: string;
  graph?: WorkflowGraph;
}

export interface UpdateWorkflowRequest {
  name?: string;
  description?: string;
  emoji?: string;
  is_enabled?: boolean;
  graph?: WorkflowGraph;
  triggers?: WorkflowTrigger[];
}

export interface Skill {
  name: string;
  display_name?: string;
  description: string;
  instructions?: string;
  package_root?: string;
  revision?: string;
  is_builtin?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ApiRespSkills {
  skills: Skill[];
}

export interface ApiRespSkill {
  skill: Skill;
}

export type {
  ExecutionSource,
  ExecutionSourceFilter,
  ExecutionModeFilter,
  ExecutionUsage,
  ExecutionRow,
  ExecutionOverview,
  TokenCoverage,
  ExecutionSummary,
  ExecutionListResult,
  PipelineMessageRow,
  ExecutionCallRow,
  AgentExecutionDetail,
  PipelineExecutionDetail,
  ExecutionDetail,
} from './monitoring-executions';
