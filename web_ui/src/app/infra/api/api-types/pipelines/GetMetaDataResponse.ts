export interface GetMetaDataResponse {
    configs: Config[]
}


interface Label {
    en_US: string;
    zh_CN: string;
}

interface Option {
    label: Label;
    name: string;
}

interface ConfigItem {
    default?: boolean | Array<unknown> | number | string;
    description?: Label;
    items?: {
        type?: string;
        properties?: {
            [key: string]: {
                type: string;
                default?: any;
            };
        };
    };
    label: Label;
    name: string;
    options?: Option[];
    required: boolean;
    scope?: string;
    type: string;
}

interface Stage {
    config: ConfigItem[];
    description?: Label;
    label: Label;
    name: string;
}

interface Config {
    label: Label;
    name: string;
    stages: Stage[];
}
