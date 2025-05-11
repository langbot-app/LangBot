import { I18nLabel } from '@/app/infra/entities/common';

export interface IDynamicFormItemSchema {
  id: string;
  default: string | number | boolean | Array<unknown>;
  label: I18nLabel;
  name: string;
  required: boolean;
  type: DynamicFormItemType;
  description?: I18nLabel;
  options?: IDynamicFormItemOption[];
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
}

export interface IDynamicFormItemOption {
  name: string;
  label: I18nLabel;
}
