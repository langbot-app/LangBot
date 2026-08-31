import type { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';

export type DynamicFormSaveValueSpec = Pick<
  IDynamicFormItemSchema,
  'default' | 'name' | 'type'
>;

const ARRAY_FIELD_TYPES = new Set([
  'array[string]',
  'array[file]',
  'knowledge-base-multi-selector',
  'resources-selector',
  'rich-tools-selector',
  'tools-selector',
]);

const STRING_FIELD_TYPES = new Set([
  'string',
  'text',
  'select',
  'llm-model-selector',
  'embedding-model-selector',
  'rerank-model-selector',
  'knowledge-base-selector',
  'bot-selector',
]);

/**
 * Coerce empty dynamic-form defaults into controlled React values.
 * Metadata from older adapters and runners can omit `default`; inputs must
 * still receive a stable value from their first render.
 */
export function normalizeDynamicFormFieldValue(
  spec: DynamicFormSaveValueSpec,
  value: unknown,
): unknown {
  if (spec.name === 'mcp-resources' || ARRAY_FIELD_TYPES.has(spec.type)) {
    return Array.isArray(value) ? value : [];
  }
  if (spec.type === 'boolean') {
    return typeof value === 'boolean' ? value : false;
  }
  if (STRING_FIELD_TYPES.has(spec.type)) {
    return typeof value === 'string' ? value : '';
  }
  if (spec.type === 'model-fallback-selector') {
    if (value != null && typeof value === 'object' && !Array.isArray(value)) {
      const objectValue = value as Record<string, unknown>;
      return {
        primary:
          typeof objectValue.primary === 'string' ? objectValue.primary : '',
        fallbacks: Array.isArray(objectValue.fallbacks)
          ? objectValue.fallbacks.filter(
              (fallback): fallback is string => typeof fallback === 'string',
            )
          : [],
        reasoning:
          objectValue.reasoning != null &&
          typeof objectValue.reasoning === 'object' &&
          !Array.isArray(objectValue.reasoning)
            ? Object.fromEntries(
                Object.entries(objectValue.reasoning).filter(
                  (entry): entry is [string, string] =>
                    typeof entry[1] === 'string',
                ),
              )
            : {},
      };
    }
    return {
      primary: typeof value === 'string' ? value : '',
      fallbacks: [],
      reasoning: {},
    };
  }
  if (spec.type === 'prompt-editor') {
    return Array.isArray(value) ? value : [{ role: 'system', content: '' }];
  }
  return value;
}

const reasoningLevels = new Set([
  'disabled',
  'enabled',
  'minimal',
  'low',
  'medium',
  'high',
  'xhigh',
  'max',
]);

function normalizeModelFallbackValue(value: unknown): {
  primary: string;
  fallbacks: string[];
  reasoning: Record<string, string>;
} {
  const raw =
    value != null && typeof value === 'object' && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : {};
  const primary =
    typeof raw.primary === 'string'
      ? raw.primary
      : typeof value === 'string'
        ? value
        : '';
  const fallbacks = Array.isArray(raw.fallbacks)
    ? raw.fallbacks.filter(
        (fallback): fallback is string => typeof fallback === 'string',
      )
    : [];
  const selectedModels = new Set([primary, ...fallbacks].filter(Boolean));
  const rawReasoning =
    raw.reasoning != null &&
    typeof raw.reasoning === 'object' &&
    !Array.isArray(raw.reasoning)
      ? (raw.reasoning as Record<string, unknown>)
      : {};
  const reasoning = Object.fromEntries(
    Object.entries(rawReasoning).filter(
      ([modelUuid, level]) =>
        selectedModels.has(modelUuid) &&
        typeof level === 'string' &&
        reasoningLevels.has(level),
    ),
  ) as Record<string, string>;

  return { primary, fallbacks, reasoning };
}

/**
 * Build the value snapshot emitted to parent forms for persistence.
 * Only single-line string fields trim surrounding whitespace; multiline text
 * and every other dynamic form field type preserve their original values.
 */
export function normalizeDynamicFormValuesForSave(
  specs: readonly DynamicFormSaveValueSpec[],
  formValues: Record<string, unknown>,
): Record<string, unknown> {
  return specs.reduce<Record<string, unknown>>((values, spec) => {
    const value = formValues[spec.name] ?? spec.default;
    if (spec.type === 'model-fallback-selector') {
      values[spec.name] = normalizeModelFallbackValue(value);
    } else {
      values[spec.name] =
        spec.type === 'string' && typeof value === 'string'
          ? value.trim()
          : value;
    }
    return values;
  }, {});
}
