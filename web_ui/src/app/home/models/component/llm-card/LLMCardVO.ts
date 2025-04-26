export interface ILLMCardVO {
    id: string;
    name: string;
    model: string;
    company: string;
    URL: string;
    updateTime: string;
}

export class LLMCardVO implements ILLMCardVO {
    id: string;
    name: string;
    model: string;
    company: string;
    URL: string;
    updateTime: string;

    constructor(props: ILLMCardVO) {
        this.id = props.id;
        this.name = props.name;
        this.model = props.model;
        this.company = props.company;
        this.URL = props.URL;
        this.updateTime = props.updateTime;
    }

}