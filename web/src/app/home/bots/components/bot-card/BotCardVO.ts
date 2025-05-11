export interface IBotCardVO {
  id: string;
  iconURL: string;
  name: string;
  description: string;
  adapterLabel: string;
  usePipelineName: string;
}

export class BotCardVO implements IBotCardVO {
  id: string;
  iconURL: string;
  name: string;
  description: string;
  adapterLabel: string;
  usePipelineName: string;

  constructor(props: IBotCardVO) {
    this.id = props.id;
    this.iconURL = props.iconURL;
    this.name = props.name;
    this.description = props.description;
    this.adapterLabel = props.adapterLabel;
    this.usePipelineName = props.usePipelineName;
  }
}
