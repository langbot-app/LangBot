export interface IEmbeddingCardVO {
  id: string;
  iconURL: string;
  name: string;
  providerLabel: string;
  baseURL: string;
}

export class EmbeddingCardVO implements IEmbeddingCardVO {
  id: string;
  iconURL: string;
  providerLabel: string;
  name: string;
  baseURL: string;

  constructor(props: IEmbeddingCardVO) {
    this.id = props.id;
    this.iconURL = props.iconURL;
    this.providerLabel = props.providerLabel;
    this.name = props.name;
    this.baseURL = props.baseURL;
  }
}
