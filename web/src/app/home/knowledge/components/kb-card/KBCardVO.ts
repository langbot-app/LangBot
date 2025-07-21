export interface IKnowledgeBaseVO {
  id: string;
  name: string;
  description: string;
  embeddingModelUUID: string;
  lastUpdatedTimeAgo: string;
}

export class KnowledgeBaseVO implements IKnowledgeBaseVO {
  id: string;
  name: string;
  description: string;
  embeddingModelUUID: string;
  lastUpdatedTimeAgo: string;

  constructor(props: IKnowledgeBaseVO) {
    this.id = props.id;
    this.name = props.name;
    this.description = props.description;
    this.embeddingModelUUID = props.embeddingModelUUID;
    this.lastUpdatedTimeAgo = props.lastUpdatedTimeAgo;
  }
}
