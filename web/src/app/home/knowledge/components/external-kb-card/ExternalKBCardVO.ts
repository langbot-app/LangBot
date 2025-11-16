export class ExternalKBCardVO {
  id: string;
  name: string;
  description: string;
  apiUrl: string;
  top_k: number;
  lastUpdatedTimeAgo: string;

  constructor({
    id,
    name,
    description,
    apiUrl,
    top_k,
    lastUpdatedTimeAgo,
  }: {
    id: string;
    name: string;
    description: string;
    apiUrl: string;
    top_k: number;
    lastUpdatedTimeAgo: string;
  }) {
    this.id = id;
    this.name = name;
    this.description = description;
    this.apiUrl = apiUrl;
    this.top_k = top_k;
    this.lastUpdatedTimeAgo = lastUpdatedTimeAgo;
  }
}
