import {
  IDynamicFormItemSchema,
  DynamicFormItemType,
  IDynamicFormItemOption,
  IShowIfCondition,
  SYSTEM_FIELD_PREFIX,
} from '@/app/infra/entities/form/dynamic';
import { I18nObject } from '@/app/infra/entities/common';

export class DynamicFormItemConfig implements IDynamicFormItemSchema {
  id: string;
  name: string;
  default: string | number | boolean | Array<unknown>;
  label: I18nObject;
  required: boolean;
  type: DynamicFormItemType;
  description?: I18nObject;
  options?: IDynamicFormItemOption[];
  show_if?: IShowIfCondition;
  login_platform?: string;

  constructor(params: IDynamicFormItemSchema) {
    this.id = params.id;
    this.name = params.name;
    this.default = params.default;
    this.label = params.label;
    this.required = params.required;
    this.type = params.type;
    this.description = params.description;
    this.options = params.options;
    this.show_if = params.show_if;
    this.login_platform = params.login_platform;
  }
}

export function isDynamicFormItemType(
  value: string,
): value is DynamicFormItemType {
  return Object.values(DynamicFormItemType).includes(
    value as DynamicFormItemType,
  );
}

export function parseDynamicFormItemType(value: string): DynamicFormItemType {
  const typeMap: Record<string, DynamicFormItemType> = {
    [DynamicFormItemType.SELECT_LLM_MODEL]:
      DynamicFormItemType.LLM_MODEL_SELECTOR,
    [DynamicFormItemType.SELECT_KNOWLEDGE_BASES]:
      DynamicFormItemType.KNOWLEDGE_BASE_MULTI_SELECTOR,
    [DynamicFormItemType.NUMBER]: DynamicFormItemType.FLOAT,
    [DynamicFormItemType.JSON]: DynamicFormItemType.TEXT,
  };
  if (value in typeMap) {
    return typeMap[value];
  }

  return isDynamicFormItemType(value) ? value : DynamicFormItemType.UNKNOWN;
}

export function getDefaultValues(
  itemConfigList: IDynamicFormItemSchema[],
): Record<string, any> {
  return itemConfigList.reduce(
    (acc, item) => {
      // `__system.*` fields are display-only (resolved from systemContext);
      // their placeholder defaults must not leak into the config values.
      if (item.name.startsWith(SYSTEM_FIELD_PREFIX)) {
        return acc;
      }
      acc[item.name] = item.default;
      return acc;
    },

    {} as Record<string, any>,
  );
}
