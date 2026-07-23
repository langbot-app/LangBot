import type { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';

export type DynamicFormSaveValueSpec = Pick<
  IDynamicFormItemSchema,
  'default' | 'name' | 'type'
>;

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
    values[spec.name] =
      spec.type === 'string' && typeof value === 'string'
        ? value.trim()
        : value;
    return values;
  }, {});
}
