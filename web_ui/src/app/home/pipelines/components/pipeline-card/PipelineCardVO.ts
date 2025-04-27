export interface IPipelineCardVO {
    id: string;
    name: string;
    description: string;
    createTime: string;
    version: string;
}

export class PipelineCardVO implements IPipelineCardVO {
    createTime: string;
    description: string;
    id: string;
    name: string;
    version: string;

    constructor(props: IPipelineCardVO) {
        this.id = props.id;
        this.name = props.name;
        this.description = props.description;
        this.createTime = props.createTime;
        this.version = props.version;
    }
}