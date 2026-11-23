export interface IBotCardVO {
  id: string;
  iconURL: string;
  name: string;
  description: string;
  adapter: string;
  adapterLabel: string;
  adapterConfig: object;
  usePipelineName: string;
  enable: boolean;
}

export class BotCardVO implements IBotCardVO {
  id: string;
  iconURL: string;
  name: string;
  description: string;
  adapter: string;
  adapterLabel: string;
  adapterConfig: object;
  usePipelineName: string;
  enable: boolean;

  constructor(props: IBotCardVO) {
    this.id = props.id;
    this.iconURL = props.iconURL;
    this.name = props.name;
    this.description = props.description;
    this.adapter = props.adapter;
    this.adapterConfig = props.adapterConfig;
    this.adapterLabel = props.adapterLabel;
    this.usePipelineName = props.usePipelineName;
    this.enable = props.enable;
  }
}
