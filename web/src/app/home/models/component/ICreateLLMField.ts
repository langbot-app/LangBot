export interface ICreateLLMField {
  name: string;
  model_provider: string;
  url: string;
  api_key: string;
  abilities: string[];
  extra_args: string[];
}
