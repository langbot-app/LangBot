export class ExternalKBCardVO {
  id: string;
  name: string;
  description: string;
  retrieverName: string;
  retrieverConfig: Record<string, unknown>;
  lastUpdatedTimeAgo: string;
  pluginAuthor: string;
  pluginName: string;

  constructor({
    id,
    name,
    description,
    retrieverName,
    retrieverConfig,
    lastUpdatedTimeAgo,
    pluginAuthor,
    pluginName,
  }: {
    id: string;
    name: string;
    description: string;
    retrieverName: string;
    retrieverConfig: Record<string, unknown>;
    lastUpdatedTimeAgo: string;
    pluginAuthor: string;
    pluginName: string;
  }) {
    this.id = id;
    this.name = name;
    this.description = description;
    this.retrieverName = retrieverName;
    this.retrieverConfig = retrieverConfig;
    this.lastUpdatedTimeAgo = lastUpdatedTimeAgo;
    this.pluginAuthor = pluginAuthor;
    this.pluginName = pluginName;
  }
}
