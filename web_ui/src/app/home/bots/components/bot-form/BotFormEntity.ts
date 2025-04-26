export interface IBotFormEntity {
    name: string,
    description: string,
    adapter: string,
    adapter_config: object;
}

export class BotFormEntity implements IBotFormEntity {
    adapter: string;
    description: string;
    name: string;
    adapter_config: object;

    constructor(props: IBotFormEntity) {
        this.adapter = props.adapter;
        this.description = props.description;
        this.name = props.name;
        this.adapter_config = props.adapter_config;
    }
}