export interface IDynamicFormItemConfig {
    id: string;
    default: string | number | boolean | Array<unknown>;
    label: IDynamicFormItemLabel;
    name: string;
    required: boolean;
    type: DynamicFormItemType
    description?: IDynamicFormItemLabel;
}

export class DynamicFormItemConfig implements IDynamicFormItemConfig {
    id: string;
    name: string;
    default: string | number | boolean | Array<unknown>;
    label: IDynamicFormItemLabel;
    required: boolean;
    type: DynamicFormItemType;
    description?: IDynamicFormItemLabel;

    constructor(params: IDynamicFormItemConfig) {
        this.id = params.id;
        this.name = params.name;
        this.default = params.default;
        this.label = params.label;
        this.required = params.required;
        this.type = params.type;
        this.description = params.description;
    }

}

export interface IDynamicFormItemLabel {
    en_US: string,
    zh_CN: string,
}

export enum DynamicFormItemType {
    INT = "integer",
    STRING = "string",
    BOOLEAN = "boolean",
    STRING_ARRAY = "array[string]",
    UNKNOWN = "unknown",
}

export function isDynamicFormItemType(value: string): value is DynamicFormItemType {
    return Object.values(DynamicFormItemType).includes(value as DynamicFormItemType);
}

export function parseDynamicFormItemType(value: string): DynamicFormItemType {
    return isDynamicFormItemType(value) ? value : DynamicFormItemType.UNKNOWN;
}