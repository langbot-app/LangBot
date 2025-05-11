export interface IPipelineCardVO {
  id: string;
  name: string;
  description: string;
  lastUpdatedTimeAgo: string;
  isDefault: boolean;
}

export class PipelineCardVO implements IPipelineCardVO {
  id: string;
  description: string;
  name: string;
  lastUpdatedTimeAgo: string;
  isDefault: boolean;

  constructor(props: IPipelineCardVO) {
    this.id = props.id;
    this.name = props.name;
    this.description = props.description;
    this.lastUpdatedTimeAgo = props.lastUpdatedTimeAgo;
    this.isDefault = props.isDefault;
  }
}
