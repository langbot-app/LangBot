export interface ICreateEmbeddingsField {
  name: string;
  model_provider: string;
  url: string;
  api_key: string;
  dimensions?: number;
  encoding_format?: string;
  extra_args?: string[];
}
