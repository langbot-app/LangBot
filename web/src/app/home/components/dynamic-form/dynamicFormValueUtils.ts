import {
  DynamicFormItemType,
  IDynamicFormItemSchema,
} from '@/app/infra/entities/form/dynamic';

interface PromptEditorMessage {
  role: string;
  content: string;
}

const DEFAULT_PROMPT_EDITOR_VALUE: PromptEditorMessage[] = [
  {
    role: 'system',
    content: '',
  },
];

function clonePromptEditorValue(): PromptEditorMessage[] {
  return DEFAULT_PROMPT_EDITOR_VALUE.map((message) => ({ ...message }));
}

// Provide stable fallback values for array/object-backed dynamic fields so the UI
// never crashes when metadata defaults are missing or persisted values are malformed.
export function getDynamicFieldFallbackValue(
  type: DynamicFormItemType,
): unknown {
  switch (type) {
    case DynamicFormItemType.STRING_ARRAY:
    case DynamicFormItemType.KNOWLEDGE_BASE_MULTI_SELECTOR:
      return [];
    case DynamicFormItemType.MODEL_FALLBACK_SELECTOR:
      return {
        primary: '',
        fallbacks: [],
      };
    case DynamicFormItemType.PROMPT_EDITOR:
      return clonePromptEditorValue();
    default:
      return undefined;
  }
}

export function normalizeDynamicFieldValue(
  item: IDynamicFormItemSchema,
  value: unknown,
): unknown {
  const fallbackValue = getDynamicFieldFallbackValue(item.type);

  if (item.type === DynamicFormItemType.MODEL_FALLBACK_SELECTOR) {
    if (value != null && typeof value === 'object' && !Array.isArray(value)) {
      const obj = value as Record<string, unknown>;
      return {
        primary: typeof obj.primary === 'string' ? obj.primary : '',
        fallbacks: Array.isArray(obj.fallbacks)
          ? (obj.fallbacks as unknown[]).filter(
              (candidate): candidate is string => typeof candidate === 'string',
            )
          : [],
      };
    }

    return {
      primary: typeof value === 'string' ? value : '',
      fallbacks: [],
    };
  }

  if (
    item.type === DynamicFormItemType.STRING_ARRAY ||
    item.type === DynamicFormItemType.KNOWLEDGE_BASE_MULTI_SELECTOR
  ) {
    return Array.isArray(value)
      ? value.filter(
          (candidate): candidate is string => typeof candidate === 'string',
        )
      : ((fallbackValue as string[]) ?? []);
  }

  if (item.type === DynamicFormItemType.PROMPT_EDITOR) {
    if (Array.isArray(value)) {
      const normalizedMessages = value
        .filter(
          (message): message is Record<string, unknown> =>
            message != null &&
            typeof message === 'object' &&
            !Array.isArray(message),
        )
        .map((message, index) => ({
          role:
            typeof message.role === 'string'
              ? message.role
              : index === 0
                ? 'system'
                : 'user',
          content: typeof message.content === 'string' ? message.content : '',
        }));

      return normalizedMessages.length > 0
        ? normalizedMessages
        : clonePromptEditorValue();
    }

    return clonePromptEditorValue();
  }

  return value;
}
