export class ExternalKBCardVO {
  id: string;
  name: string;
  description: string;
  retrieverName: string;
  retrieverConfig: Record<string, unknown>;
  lastUpdatedTimeAgo: string;

  constructor({
    id,
    name,
    description,
    retrieverName,
    retrieverConfig,
    lastUpdatedTimeAgo,
  }: {
    id: string;
    name: string;
    description: string;
    retrieverName: string;
    retrieverConfig: Record<string, unknown>;
    lastUpdatedTimeAgo: string;
  }) {
    this.id = id;
    this.name = name;
    this.description = description;
    this.retrieverName = retrieverName;
    this.retrieverConfig = retrieverConfig;
    this.lastUpdatedTimeAgo = lastUpdatedTimeAgo;
  }
}
