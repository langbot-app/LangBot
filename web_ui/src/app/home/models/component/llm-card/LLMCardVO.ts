export interface ILLMCardVO {
    id: string;
    name: string;
    model: string;
    company: string;
    URL: string;
}

export class LLMCardVO implements ILLMCardVO {
    id: string;
    name: string;
    model: string;
    company: string;
    URL: string;

    constructor(props: ILLMCardVO) {
        this.id = props.id;
        this.name = props.name;
        this.model = props.model;
        this.company = props.company;
        this.URL = props.URL;
    }

}