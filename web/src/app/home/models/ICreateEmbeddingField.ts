export interface ICreateEmbeddingField {
  name: string;
  model_provider: string;
  url: string;
  api_key: string;
  extra_args?: string[];
}
