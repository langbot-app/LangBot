import { I18nObject } from '@/app/infra/entities/common';

export interface IDynamicFormItemSchema {
  id: string;
  default: string | number | boolean | Array<unknown>;
  label: I18nObject;
  name: string;
  required: boolean;
  type: DynamicFormItemType;
  description?: I18nObject;
  options?: IDynamicFormItemOption[];

  /** when type is PLUGIN_SELECTOR, the scopes is the scopes of components(plugin contains), the default is all */
  scopes?: string[];
}

export enum DynamicFormItemType {
  INT = 'integer',
  FLOAT = 'float',
  BOOLEAN = 'boolean',
  STRING = 'string',
  STRING_ARRAY = 'array[string]',
  SELECT = 'select',
  LLM_MODEL_SELECTOR = 'llm-model-selector',
  PROMPT_EDITOR = 'prompt-editor',
  UNKNOWN = 'unknown',
  KNOWLEDGE_BASE_SELECTOR = 'knowledge-base-selector',
  PLUGIN_SELECTOR = 'plugin-selector',
}

export interface IDynamicFormItemOption {
  name: string;
  label: I18nObject;
}
