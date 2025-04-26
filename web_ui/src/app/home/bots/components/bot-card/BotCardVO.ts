export interface IBotCardVO {
    id: string;
    name: string;
    adapter: string;
    description: string;
    updateTime: string;
    pipelineName: string;
}

export class BotCardVO implements IBotCardVO {
    id: string;
    adapter: string;
    description: string;
    name: string;
    updateTime: string;
    pipelineName: string;


    constructor(props: IBotCardVO) {
        this.id = props.id;
        this.name = props.name;
        this.adapter = props.adapter;
        this.description = props.description;
        this.updateTime = props.updateTime;
        this.pipelineName = props.pipelineName;
    }

}