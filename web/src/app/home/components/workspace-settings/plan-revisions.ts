/** Only trusted subscription data may populate the current side of a comparison. */
export interface PlanRevisionBenefits {
  name: string;
  revision: number;
  limits: Record<string, number>;
  entitlement_features?: Record<string, boolean>;
  disabled_adapters?: string[];
  chat_history_retention_days?: number;
  monthly_bonus_credits?: number;
}

export function benefitValues(plan: PlanRevisionBenefits) {
  const values: Record<string, number | boolean> = {};
  for (const [key, value] of Object.entries(plan.limits))
    values[`limit:${key}`] = value;
  values['limit:chat_history.retention_days'] =
    plan.limits['chat_history.retention_days'] ??
    plan.chat_history_retention_days ??
    30;
  values.monthly_credits = plan.monthly_bonus_credits ?? 0;
  for (const [key, value] of Object.entries(plan.entitlement_features ?? {}))
    values[`feature:${key}`] = value;
  for (const adapter of plan.disabled_adapters ?? [])
    values[`feature:platform.${adapter}`] = false;
  return values;
}

export function revisionRows(
  current: PlanRevisionBenefits,
  latest?: PlanRevisionBenefits,
) {
  const left = benefitValues(current);
  const right = latest ? benefitValues(latest) : {};
  return [...new Set([...Object.keys(left), ...Object.keys(right)])]
    .sort()
    .map((key) => {
      // Platform adapters are allowed unless explicitly disabled. Other feature
      // switches must be explicitly granted, matching Core's admission semantics.
      const fallback = key.startsWith('feature:platform.')
        ? true
        : key.startsWith('feature:')
          ? false
          : undefined;
      const before = left[key] ?? fallback;
      const after = right[key] ?? fallback;
      return { key, before, after, changed: !!latest && before !== after };
    });
}
