export class ExternalKBCardVO {
  id: string;
  name: string;
  description: string;
  emoji?: string;
  retrieverName: string;
  retrieverConfig: Record<string, unknown>;
  lastUpdatedTimeAgo: string;
  pluginAuthor: string;
  pluginName: string;

  constructor({
    id,
    name,
    description,
    emoji,
    retrieverName,
    retrieverConfig,
    lastUpdatedTimeAgo,
    pluginAuthor,
    pluginName,
  }: {
    id: string;
    name: string;
    description: string;
    emoji?: string;
    retrieverName: string;
    retrieverConfig: Record<string, unknown>;
    lastUpdatedTimeAgo: string;
    pluginAuthor: string;
    pluginName: string;
  }) {
    this.id = id;
    this.name = name;
    this.description = description;
    this.emoji = emoji;
    this.retrieverName = retrieverName;
    this.retrieverConfig = retrieverConfig;
    this.lastUpdatedTimeAgo = lastUpdatedTimeAgo;
    this.pluginAuthor = pluginAuthor;
    this.pluginName = pluginName;
  }
}
