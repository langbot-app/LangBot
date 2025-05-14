import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import { PipelineConfigTab } from '@/app/infra/entities/pipeline';

export interface ApiResponse<T> {
  code: number;
  data: T;
  msg: string;
}

export interface I18nText {
  en_US: string;
  zh_Hans: string;
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
  label: I18nText;
  description: I18nText;
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
  label: I18nText;
  description: I18nText;
  icon?: string;
  spec: {
    config: AdapterSpecConfig[];
  };
}

export interface AdapterSpecConfig {
  default: string | number | boolean | Array<unknown>;
  label: I18nText;
  name: string;
  required: boolean;
  type: string;
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
  description: I18nText;
  label: I18nText;
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
  ai: {
    'dashscope-app-api': {
      'api-key': string;
      'app-id': string;
      'app-type': 'agent' | 'workflow';
      'references-quote'?: string;
    };
    'dify-service-api': {
      'api-key': string;
      'app-type': 'chat' | 'agent' | 'workflow';
      'base-url': string;
      'thinking-convert': 'plain' | 'original' | 'remove';
      timeout?: number;
    };
    'local-agent': {
      'max-round': number;
      model: string;
      prompt: Array<{
        content: string;
        role: string;
      }>;
    };
    runner: {
      runner: 'local-agent' | 'dify-service-api' | 'dashscope-app-api';
    };
  };
  output: {
    'force-delay': {
      max: number;
      min: number;
    };
    'long-text-processing': {
      'font-path': string;
      strategy: 'forward' | 'image';
      threshold: number;
    };
    misc: {
      'at-sender': boolean;
      'hide-exception': boolean;
      'quote-origin': boolean;
      'track-function-calls': boolean;
    };
  };
  safety: {
    'content-filter': {
      'check-sensitive-words': boolean;
      scope: 'all' | 'income-msg' | 'output-msg';
    };
    'rate-limit': {
      limitation: number;
      strategy: 'drop' | 'wait';
      'window-length': number;
    };
  };
  trigger: {
    'access-control': {
      blacklist: string[];
      mode: 'blacklist' | 'whitelist';
      whitelist: string[];
    };
    'group-respond-rules': {
      at: boolean;
      prefix: string[];
      random: number;
      regexp: string[];
    };
    'ignore-rules': {
      prefix: string[];
      regexp: string[];
    };
  };
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
