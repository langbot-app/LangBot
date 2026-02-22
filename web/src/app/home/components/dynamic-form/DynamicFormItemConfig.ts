import {
  IDynamicFormItemSchema,
  DynamicFormItemType,
  IDynamicFormItemOption,
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
  editable?: boolean;

  constructor(params: IDynamicFormItemSchema) {
    this.id = params.id;
    this.name = params.name;
    this.default = params.default;
    this.label = params.label;
    this.required = params.required;
    this.type = params.type;
    this.description = params.description;
    this.options = params.options;
    this.editable = params.editable;
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
  return isDynamicFormItemType(value) ? value : DynamicFormItemType.UNKNOWN;
}

export function getDefaultValues(
  itemConfigList: IDynamicFormItemSchema[],
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): Record<string, any> {
  return itemConfigList.reduce(
    (acc, item) => {
      acc[item.name] = item.default;
      return acc;
    },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    {} as Record<string, any>,
  );
}
