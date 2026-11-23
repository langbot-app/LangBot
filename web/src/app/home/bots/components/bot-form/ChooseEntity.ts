export interface IChooseAdapterEntity {
  label: string;
  value: string;
  categories?: string[];
  legacy?: boolean;
}

export interface IPipelineEntity {
  label: string;
  value: string;
  emoji?: string;
}
