export interface ILLMCardVO {
    id: string;
    name: string;
    company: string;
    URL: string;
}

export class LLMCardVO implements ILLMCardVO {
    id: string;
    name: string;
    company: string;
    URL: string;

    constructor(props: ILLMCardVO) {
        this.id = props.id;
        this.name = props.name;
        this.company = props.company;
        this.URL = props.URL;
    }

}