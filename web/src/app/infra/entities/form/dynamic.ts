import { I18nObject } from '@/app/infra/entities/common';

/** Namespace prefix shared by ``show_if.field`` references and display-only
 *  form item names whose value is resolved from the caller-supplied
 *  ``DynamicFormComponent.systemContext``. */
export const SYSTEM_FIELD_PREFIX = '__system.';

export interface IShowIfCondition {
  field: string;
  operator: 'eq' | 'neq' | 'in';

  value: any;
}

export interface IDynamicFormItemSchema {
  id: string;
  default: string | number | boolean | Array<unknown>;
  label: I18nObject;
  /** Form value key. Names prefixed with ``__system.`` denote display-only
   *  fields whose value is resolved from
   *  ``DynamicFormComponent.systemContext`` (e.g. ``__system.outbound_ips``
   *  → ``systemContext.outbound_ips``) — same namespace as ``show_if``.
   *  Such fields are rendered read-only with copy buttons, excluded from
   *  form state/validation/emission, and hidden when the value is empty. */
  name: string;
  required: boolean;
  type: DynamicFormItemType;
  description?: I18nObject;
  options?: IDynamicFormItemOption[];
  /** When the condition matches, the field is rendered. Same evaluator as
   *  ``disable_if`` — supports the ``__system.*`` namespace via
   *  ``DynamicFormComponent.systemContext``. */
  show_if?: IShowIfCondition;
  /** When the condition matches, the field is rendered as read-only/disabled
   *  but stays visible. Use this when the operator needs to see that the
   *  field exists but can't be edited under the current runtime state (e.g.
   *  a sandbox-bound field when Box is disabled). Pair with
   *  ``disabled_tooltip`` to explain why. */
  disable_if?: IShowIfCondition;
  /** Tooltip shown next to the field label when ``disable_if`` is active. */
  disabled_tooltip?: I18nObject;

  /** when type is PLUGIN_SELECTOR, the scopes is the scopes of components(plugin contains), the default is all */
  scopes?: string[];
  accept?: string; // For file type: accepted MIME types
  login_platform?: string; // For qr-code-login type: platform identifier (e.g. 'feishu', 'weixin')
}

export enum DynamicFormItemType {
  INT = 'integer',
  FLOAT = 'float',
  BOOLEAN = 'boolean',
  STRING = 'string',
  TEXT = 'text',
  STRING_ARRAY = 'array[string]',
  FILE = 'file',
  FILE_ARRAY = 'array[file]',
  SELECT = 'select',
  LLM_MODEL_SELECTOR = 'llm-model-selector',
  EMBEDDING_MODEL_SELECTOR = 'embedding-model-selector',
  RERANK_MODEL_SELECTOR = 'rerank-model-selector',
  MODEL_FALLBACK_SELECTOR = 'model-fallback-selector',
  PROMPT_EDITOR = 'prompt-editor',
  UNKNOWN = 'unknown',
  KNOWLEDGE_BASE_SELECTOR = 'knowledge-base-selector',
  KNOWLEDGE_BASE_MULTI_SELECTOR = 'knowledge-base-multi-selector',
  PLUGIN_SELECTOR = 'plugin-selector',
  BOT_SELECTOR = 'bot-selector',
  TOOLS_SELECTOR = 'tools-selector',
  WEBHOOK_URL = 'webhook-url',
  EMBED_CODE = 'embed-code',
  QR_CODE_LOGIN = 'qr-code-login',
  // Plugin manifest type aliases for compatibility
  SELECT_LLM_MODEL = 'select-llm-model',
  SELECT_KNOWLEDGE_BASES = 'select-knowledge-bases',
  NUMBER = 'number',
  JSON = 'json',
}

export interface IFileConfig {
  file_key: string;
  mimetype: string;
}

export interface IDynamicFormItemOption {
  name: string;
  label: I18nObject;
}
