import { I18nLabel } from '@/app/infra/entities/common';
import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';

export interface PipelineFormEntity {
  basic: object;
  ai: object;
  trigger: object;
  safety: object;
  output: object;
}

export interface PipelineConfigTab {
  name: string;
  label: I18nLabel;
  stages: PipelineConfigStage[];
}

export interface PipelineConfigStage {
  name: string;
  label: I18nLabel;
  description?: I18nLabel;
  config: IDynamicFormItemSchema[];
}
