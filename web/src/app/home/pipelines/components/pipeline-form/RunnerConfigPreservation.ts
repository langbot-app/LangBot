type Values = Record<string, unknown>;
const isRecord = (value: unknown): value is Values =>
  value !== null && typeof value === 'object' && !Array.isArray(value);

/** Apply only edits relative to the mounted form's normalized emission.
 * The raw persisted object remains authoritative for unedited values, including
 * fields not represented by the schema, nulls, omitted defaults and whitespace.
 */
export function preserveRunnerConfig(
  current: Values,
  previous: Values | undefined,
  emitted: Values,
): Values {
  if (!previous) return current;
  const result = { ...current };
  for (const key of new Set([
    ...Object.keys(previous),
    ...Object.keys(emitted),
  ])) {
    if (JSON.stringify(previous[key]) === JSON.stringify(emitted[key]))
      continue;
    if (!Object.prototype.hasOwnProperty.call(emitted, key)) {
      delete result[key];
    } else if (isRecord(previous[key]) && isRecord(emitted[key])) {
      result[key] = preserveRunnerConfig(
        isRecord(current[key]) ? current[key] : {},
        previous[key],
        emitted[key],
      );
    } else {
      result[key] = emitted[key];
    }
  }
  return result;
}
