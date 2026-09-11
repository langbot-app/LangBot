import {
  SYSTEM_FIELD_PREFIX,
  type IDynamicFormItemSchema,
  type IShowIfCondition,
} from '@/app/infra/entities/form/dynamic';

/** System references use caller context; other fields prefer live form values. */
export function resolveShowIfValue(
  field: string,
  watchedValues: Record<string, unknown>,
  externalDependentValues?: Record<string, unknown>,
  systemContext?: Record<string, unknown>,
): unknown {
  if (field.startsWith(SYSTEM_FIELD_PREFIX)) {
    return systemContext?.[field.slice(SYSTEM_FIELD_PREFIX.length)];
  }
  if (watchedValues[field] !== undefined) {
    return watchedValues[field];
  }
  return externalDependentValues?.[field];
}

export function matchesFormCondition(
  condition: IShowIfCondition,
  watchedValues: Record<string, unknown>,
  externalDependentValues?: Record<string, unknown>,
  systemContext?: Record<string, unknown>,
): boolean {
  const value = resolveShowIfValue(
    condition.field,
    watchedValues,
    externalDependentValues,
    systemContext,
  );
  switch (condition.operator) {
    case 'eq':
      return value === condition.value;
    case 'neq':
      return value !== condition.value;
    case 'in':
      return Array.isArray(condition.value) && condition.value.includes(value);
    default:
      return false;
  }
}

export function resolveDisabledState(
  config: Pick<
    IDynamicFormItemSchema,
    'disable_if' | 'disabled_tooltip' | 'disabled_tooltip_overrides'
  >,
  watchedValues: Record<string, unknown>,
  externalDependentValues?: Record<string, unknown>,
  systemContext?: Record<string, unknown>,
) {
  const matches = (condition: IShowIfCondition) =>
    matchesFormCondition(
      condition,
      watchedValues,
      externalDependentValues,
      systemContext,
    );
  const isDisabledByCondition =
    !!config.disable_if && matches(config.disable_if);
  const disabledTooltip = isDisabledByCondition
    ? (config.disabled_tooltip_overrides?.find((override) =>
        matches(override.when),
      )?.tooltip ?? config.disabled_tooltip)
    : undefined;
  return { isDisabledByCondition, disabledTooltip };
}
