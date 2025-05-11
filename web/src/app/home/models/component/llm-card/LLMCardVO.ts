export interface ILLMCardVO {
  id: string;
  iconURL: string;
  name: string;
  providerLabel: string;
  baseURL: string;
  abilities: string[];
}

export class LLMCardVO implements ILLMCardVO {
  id: string;
  iconURL: string;
  providerLabel: string;
  name: string;
  baseURL: string;
  abilities: string[];

  constructor(props: ILLMCardVO) {
    this.id = props.id;
    this.iconURL = props.iconURL;
    this.providerLabel = props.providerLabel;
    this.name = props.name;
    this.baseURL = props.baseURL;
    this.abilities = props.abilities;
  }
}
