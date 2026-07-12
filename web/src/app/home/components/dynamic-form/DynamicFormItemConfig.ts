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
): Record<string, any> {
  return itemConfigList.reduce(
    (acc, item) => {
      // `__system.*` fields are display-only (resolved from systemContext);
      // their placeholder defaults must not leak into the config values.
      if (item.name.startsWith(SYSTEM_FIELD_PREFIX)) {
        return acc;
      }
      acc[item.name] = item.default;
      if (item.type === DynamicFormItemType.RICH_TOOLS_SELECTOR) {
        acc['enable-all-tools'] = true;
      }
      if (item.type === DynamicFormItemType.RESOURCES_SELECTOR) {
        acc['mcp-resources'] = [];
        acc['mcp-resource-agent-read-enabled'] = true;
      }
      return acc;
    },

    {} as Record<string, any>,
  );
}
