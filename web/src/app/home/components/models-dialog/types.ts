import {
  LLMModel,
  EmbeddingModel,
  ModelProvider,
  ProviderScanDebugInfo,
  ScannedProviderModel,
} from '@/app/infra/entities/api';

export type ExtraArg = {
  key: string;
  type: 'string' | 'number' | 'boolean';
  value: string;
};

export type ModelType = 'llm' | 'embedding';

export interface ProviderModels {
  llm: LLMModel[];
  embedding: EmbeddingModel[];
}

export interface TestResult {
  success: boolean;
  duration: number;
}

export type SelectedScannedModel = {
  model: ScannedProviderModel;
  abilities: string[];
};

export type ScanModelsResult = {
  models: ScannedProviderModel[];
  debug?: ProviderScanDebugInfo;
};

export interface ModelItemProps {
  model: LLMModel | EmbeddingModel;
  modelType: ModelType;
  providerUuid: string;
  isLangBotModels: boolean;
  isEditOpen: boolean;
  isDeleteOpen: boolean;
  onEditOpen: () => void;
  onEditClose: () => void;
  onDeleteOpen: () => void;
  onDeleteClose: () => void;
  onDelete: () => void;
  onUpdate: (
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) => Promise<void>;
  onTest: (
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) => Promise<void>;
  isSubmitting: boolean;
  isTesting: boolean;
  testResult: TestResult | null;
}

export interface ProviderCardProps {
  provider: ModelProvider;
  isLangBotModels?: boolean;
  isExpanded: boolean;
  isLoading: boolean;
  models?: ProviderModels;
  accountType: 'local' | 'space';
  spaceCredits: number | null;
  requesterNameList: { label: string; value: string }[];
  // Popover states
  addModelPopoverOpen: string | null;
  editModelPopoverOpen: string | null;
  deleteConfirmOpen: string | null;
  // Handlers
  onToggle: () => void;
  onEditProvider: () => void;
  onDeleteProvider: () => void;
  onSpaceLogin: () => void;
  onOpenAddModel: () => void;
  onCloseAddModel: () => void;
  onAddModel: (
    modelType: ModelType,
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) => Promise<void>;
  onScanModels: (modelType: ModelType) => Promise<ScanModelsResult>;
  onAddScannedModels: (
    modelType: ModelType,
    models: SelectedScannedModel[],
  ) => Promise<void>;
  onOpenEditModel: (modelId: string) => void;
  onCloseEditModel: () => void;
  onUpdateModel: (
    modelId: string,
    modelType: ModelType,
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) => Promise<void>;
  onOpenDeleteConfirm: (modelId: string) => void;
  onCloseDeleteConfirm: () => void;
  onDeleteModel: (modelId: string, modelType: ModelType) => Promise<void>;
  onTestModel: (
    name: string,
    modelType: ModelType,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) => Promise<void>;
  isSubmitting: boolean;
  isTesting: boolean;
  testResult: TestResult | null;
  onResetTestResult: () => void;
}

export const LANGBOT_MODELS_PROVIDER_REQUESTER = 'space-chat-completions';
