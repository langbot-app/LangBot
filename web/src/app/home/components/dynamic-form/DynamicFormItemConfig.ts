import {
  IDynamicFormItemSchema,
  DynamicFormItemType,
  IDynamicFormItemOption,
  IShowIfCondition,
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
  url?: string;
  download_filename?: string;
  help_links?: Record<string, string>;
  help_label?: I18nObject;

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
    this.url = params.url;
    this.download_filename = params.download_filename;
    this.help_links = params.help_links;
    this.help_label = params.help_label;
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
