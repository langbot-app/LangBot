export interface IEmbeddingsCardVO {
  id: string;
  iconURL: string;
  name: string;
  providerLabel: string;
  baseURL: string;
  dimensions?: number;
  encoding_format?: string;
}

export class EmbeddingsCardVO implements IEmbeddingsCardVO {
  id: string;
  iconURL: string;
  providerLabel: string;
  name: string;
  baseURL: string;
  dimensions?: number;
  encoding_format?: string;

  constructor(props: IEmbeddingsCardVO) {
    this.id = props.id;
    this.iconURL = props.iconURL;
    this.providerLabel = props.providerLabel;
    this.name = props.name;
    this.baseURL = props.baseURL;
    this.dimensions = props.dimensions;
    this.encoding_format = props.encoding_format;
  }
}
