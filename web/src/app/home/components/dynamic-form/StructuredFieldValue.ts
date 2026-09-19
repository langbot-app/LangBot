export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };
export type PromptMessage = {
  role: string;
  content?: string | null | JsonValue[];
  [key: string]: JsonValue | undefined;
};

export function isJsonValue(value: unknown): value is JsonValue {
  if (value === null || typeof value === 'string' || typeof value === 'boolean')
    return true;
  if (typeof value === 'number') return Number.isFinite(value);
  if (Array.isArray(value)) return value.every(isJsonValue);
  return (
    typeof value === 'object' &&
    value !== null &&
    Object.values(value).every(isJsonValue)
  );
}
export function isPromptValue(value: unknown): value is PromptMessage[] {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        item !== null &&
        typeof item === 'object' &&
        !Array.isArray(item) &&
        typeof item.role === 'string' &&
        (!Object.prototype.hasOwnProperty.call(item, 'content') ||
          typeof item.content === 'string' ||
          item.content === null ||
          Array.isArray(item.content)) &&
        isJsonValue(item),
    )
  );
}
export function parseStructuredDraft(
  draft: string,
  prompt: boolean,
): JsonValue {
  const value: unknown = JSON.parse(draft);
  if (!(prompt ? isPromptValue(value) : isJsonValue(value)))
    throw new TypeError('JSON');
  return value as JsonValue;
}
export function isSimplePrompt(
  value: unknown,
): value is { role: string; content: string }[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every(
      (item, index) =>
        item &&
        typeof item.content === 'string' &&
        (index === 0
          ? item.role === 'system'
          : ['user', 'assistant'].includes(item.role)) &&
        Object.keys(item).every((key) => key === 'role' || key === 'content'),
    )
  );
}
