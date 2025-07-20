import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import { PipelineConfigTab } from '@/app/infra/entities/pipeline';
import { I18nLabel } from '@/app/infra/entities/common';
import { Message } from '@/app/infra/entities/message';

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
  label: I18nLabel;
  description: I18nLabel;
  icon?: string;
  spec: {
    config: IDynamicFormItemSchema[];
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
  top_k?: number;
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
  label: I18nLabel;
  description: I18nLabel;
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

export interface Plugin {
  author: string;
  name: string;
  description: I18nLabel;
  label: I18nLabel;
  version: string;
  enabled: boolean;
  priority: number;
  status: string;
  tools: object[];
  event_handlers: object;
  main_file: string;
  pkg_path: string;
  repository: string;
  config_schema: IDynamicFormItemSchema[];
}

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

export interface MarketPlugin {
  ID: number;
  CreatedAt: string; // ISO 8601 格式日期
  UpdatedAt: string;
  DeletedAt: string | null;
  name: string;
  author: string;
  description: string;
  repository: string; // GitHub 仓库路径
  artifacts_path: string;
  stars: number;
  downloads: number;
  status: 'initialized' | 'mounted'; // 可根据实际状态值扩展联合类型
  synced_at: string;
  pushed_at: string; // 最后一次代码推送时间
}

export interface MarketPluginResponse {
  plugins: MarketPlugin[];
  total: number;
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
