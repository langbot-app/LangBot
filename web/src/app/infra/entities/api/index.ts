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
  };
}

export interface ApiRespProviderLLMModels {
  models: LLMModel[];
}

export interface ApiRespProviderLLMModel {
  model: LLMModel;
}

export interface LLMModel {
  name: string;
  description: string;
  uuid: string;
  requester: string;
  requester_config: {
    base_url: string;
    timeout: number;
  };
  extra_args?: object;
  api_keys: string[];
  abilities?: string[];
  // created_at: string;
  // updated_at: string;
}

export interface KnowledgeBase {
  uuid?: string;
  name: string;
  description: string;
  embedding_model_uuid: string;
  created_at?: string;
  top_k: number;
}

export interface ApiRespProviderEmbeddingModels {
  models: EmbeddingModel[];
}

export interface ApiRespProviderEmbeddingModel {
  model: EmbeddingModel;
}

export interface EmbeddingModel {
  name: string;
  description: string;
  uuid: string;
  requester: string;
  requester_config: {
    base_url: string;
    timeout: number;
  };
  extra_args?: object;
  api_keys: string[];
  // created_at: string;
  // updated_at: string;
}

export interface ApiRespPipelines {
  pipelines: Pipeline[];
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
  use_pipeline_name?: string;
  use_pipeline_uuid?: string;
  created_at?: string;
  updated_at?: string;
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
  embedding_model_uuid: string;
  top_k: number;
  created_at?: string;
  updated_at?: string;
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
export interface ApiRespSystemInfo {
  debug: boolean;
  version: string;
  cloud_service_url: string;
  enable_marketplace: boolean;
}

export interface ApiRespPluginSystemStatus {
  is_enable: boolean;
  is_connected: boolean;
  plugin_connector_error: string;
}

export interface ApiRespAsyncTasks {
  tasks: AsyncTask[];
}

export interface AsyncTaskRuntimeInfo {
  done: boolean;
  exception?: string;
  result?: object;
  state: string;
}

export interface AsyncTaskTaskContext {
  current_action: string;
  log: string;
}

export interface AsyncTask {
  id: number;
  kind: string;
  name: string;
  task_type: string; // system or user
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

export interface RetrieveResult {
  id: string;
  metadata: {
    file_id: string;
    text: string;
    uuid: string;
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
}

export enum MCPSessionStatus {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  ERROR = 'error',
}

export interface MCPServerRuntimeInfo {
  status: MCPSessionStatus;
  error_message: string;
  tool_count: number;
  tools: MCPTool[];
}

export interface MCPServer {
  uuid?: string;
  name: string;
  mode: 'stdio' | 'sse';
  enable: boolean;
  extra_args: MCPServerExtraArgsSSE;
  runtime_info?: MCPServerRuntimeInfo;
  created_at?: string;
  updated_at?: string;
}

export interface MCPTool {
  name: string;
  description: string;
  parameters?: object;
}
