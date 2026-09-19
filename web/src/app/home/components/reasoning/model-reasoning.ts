import { LANGBOT_MODELS_PROVIDER_REQUESTER } from '../models-dialog/types';

interface ModelReasoningInfo {
  abilities?: string[];
  reasoning_capabilities?: { supported?: boolean };
  provider?: { requester?: string };
}

export function hasModelReasoningAbility(
  model: ModelReasoningInfo | undefined,
  isLangBotModels = model?.provider?.requester ===
    LANGBOT_MODELS_PROVIDER_REQUESTER,
): boolean {
  return Boolean(
    model?.abilities?.includes('reasoning') ||
    (isLangBotModels && model?.reasoning_capabilities?.supported === true),
  );
}
