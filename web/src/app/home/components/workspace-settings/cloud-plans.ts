export type CloudPlanBillingCycle = 'monthly' | 'annual';
export type CloudPlanCurrency = 'CNY' | 'USD' | 'JPY';
export type PlanLocalizedText = Partial<Record<string, string>>;
export interface PublicCloudPlan {
  entitlement_features?: Record<string, boolean>;
  uuid: string;
  name: string;
  revision: number;
  display_name: PlanLocalizedText;
  description: PlanLocalizedText;
  price_cny: string;
  price_usd: string;
  price_jpy: string;
  limits: Record<string, number>;
  features: string[];
  is_active: boolean;
  subscription_disabled?: boolean;
  sort_order: number;
  highlight: boolean;
  chat_history_retention_days: number;
  monthly_bonus_credits: number;
  disabled_adapters: string[];
  display_config?: {
    icon?: string;
    order?: string[];
    quota_summary?: PlanLocalizedText;
    tooltips?: Partial<Record<string, PlanLocalizedText>>;
    quotas?: Record<
      string,
      { label?: PlanLocalizedText; tooltip?: PlanLocalizedText }
    >;
    items?: Array<{
      label: PlanLocalizedText;
      tooltip?: PlanLocalizedText;
      icon: string;
    }>;
  } | null;
}

export function localizedPlanText(
  values: PlanLocalizedText | undefined,
  language: string,
): string {
  if (!values) return '';
  const locale = language.replace(/-/g, '_');
  const key = Object.keys(values).find(
    (key) => key.toLowerCase() === locale.toLowerCase(),
  );
  return (
    (key && values[key]) ||
    values.en_US ||
    values.zh_Hans ||
    Object.values(values).find(Boolean) ||
    ''
  );
}

export function cloudPlanCurrencyForLanguage(
  language: string,
): CloudPlanCurrency {
  const locale = language.replace(/_/g, '-').toLowerCase();
  if (locale === 'zh-hans' || locale.startsWith('zh-hans-')) return 'CNY';
  if (locale === 'ja' || locale.startsWith('ja-')) return 'JPY';
  return 'USD';
}

export function cloudPlanPrice(
  plan: PublicCloudPlan,
  cycle: CloudPlanBillingCycle,
  currency: CloudPlanCurrency,
): number {
  const amount = Number(
    plan[
      currency === 'CNY'
        ? 'price_cny'
        : currency === 'JPY'
          ? 'price_jpy'
          : 'price_usd'
    ],
  );
  if (!Number.isFinite(amount) || amount < 0)
    throw new Error('Invalid public plan price');
  return amount * (cycle === 'annual' ? 10 : 1);
}

function spaceURL(base: string, path: string): URL {
  const url = new URL(base);
  if (
    !['http:', 'https:'].includes(url.protocol) ||
    url.username ||
    url.password
  )
    throw new Error('Invalid Space URL');
  url.pathname = `${url.pathname.replace(/\/$/, '')}${path}`;
  url.search = '';
  url.hash = '';
  return url;
}

export function cloudPlanCheckoutURL(
  base: string,
  workspace: string,
  plan: string,
  billing: CloudPlanBillingCycle,
  currency: CloudPlanCurrency,
): string {
  const url = spaceURL(base, '/cloud');
  url.search = new URLSearchParams({
    environment: 'new',
    step: 'plan',
    workspace,
    plan,
    billing,
    currency,
  }).toString();
  return url.toString();
}

/** Workspace navigation only; Space authenticates and authorizes independently. */
export function cloudSubscriptionManagementURL(
  base: string,
  workspace: string,
): string {
  const url = spaceURL(base, '/cloud');
  url.search = new URLSearchParams({
    environment: 'new',
    step: 'subscription',
    workspace,
  }).toString();
  return url.toString();
}

export function cloudPlanPlatformIconURL(base: string, icon: string): string {
  return spaceURL(base, icon).toString();
}

/** This request is deliberately independent of Core and Space authenticated clients. */
export async function fetchPublicCloudPlans(
  base: string,
  signal: AbortSignal,
): Promise<PublicCloudPlan[]> {
  const response = await fetch(spaceURL(base, '/api/v1/cloud/v2/plans'), {
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
    signal,
  });
  if (!response.ok) throw new Error('Could not load public plans');
  const result = await response.json();
  if (result.code !== 0 || !Array.isArray(result.data))
    throw new Error('Invalid plan catalog');
  const plans = (result.data as PublicCloudPlan[]).filter(
    (plan) => plan.is_active,
  );
  for (const plan of plans) {
    if (!plan.uuid || !plan.name || !plan.limits)
      throw new Error('Invalid public plan');
    for (const currency of ['CNY', 'USD', 'JPY'] as const)
      cloudPlanPrice(plan, 'monthly', currency);
  }
  return plans.sort((a, b) => a.sort_order - b.sort_order);
}

// Catalog metadata (copy, prices, display items) of one historical revision.
export async function fetchCloudPlanRevision(
  base: string,
  name: string,
  revision: number,
  signal: AbortSignal,
): Promise<PublicCloudPlan> {
  const response = await fetch(
    spaceURL(
      base,
      `/api/v1/cloud/v2/plans/${encodeURIComponent(name)}/revisions/${revision}`,
    ),
    { credentials: 'omit', referrerPolicy: 'no-referrer', signal },
  );
  if (!response.ok) throw new Error('Could not load plan revision');
  const result = await response.json();
  const plan = result?.data as PublicCloudPlan | undefined;
  if (result?.code !== 0 || !plan?.name || plan.name !== name)
    throw new Error('Invalid plan revision');
  return plan;
}
