import { useEffect, useState, type ReactNode, type ComponentType } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ArrowRight,
  Check,
  Info,
  Layers,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import * as RemixIcons from '@remixicon/react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { CurrentWorkspace } from '@/app/infra/entities/workspace';
import {
  cloudPlanCheckoutURL,
  cloudPlanPlatformIconURL,
  cloudSubscriptionManagementURL,
  cloudPlanPrice,
  cloudPlanCurrencyForLanguage,
  fetchCloudPlanRevision,
  fetchPublicCloudPlans,
  localizedPlanText,
  type CloudPlanBillingCycle,
  type PublicCloudPlan,
} from './cloud-plans';
import { revisionRows } from './plan-revisions';
import { supportedPlanPlatforms } from './cloud-plan-platforms';
import PlanRevisionStack from './PlanRevisionStack';

function PlanIcon({ name }: { name?: string }) {
  const key = name
    ?.replace(/^ri-/, '')
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('');
  const Icon =
    name && /^ri-[a-z0-9-]+-(line|fill)$/.test(name)
      ? (
          RemixIcons as unknown as Record<
            string,
            ComponentType<{ className?: string }>
          >
        )[`Ri${key}`]
      : undefined;
  return Icon ? (
    <Icon className="size-4 shrink-0 text-blue-500" />
  ) : (
    <Check className="size-4 shrink-0 text-blue-500" />
  );
}

function Help({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          className="flex h-5 shrink-0 items-center rounded text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-primary"
        >
          <Info className="size-3.5" aria-hidden />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-80 whitespace-pre-line">
        {children}
      </TooltipContent>
    </Tooltip>
  );
}

function Benefits({
  plan,
  spaceURL,
}: {
  plan: Pick<
    PublicCloudPlan,
    | 'limits'
    | 'features'
    | 'disabled_adapters'
    | 'display_config'
    | 'chat_history_retention_days'
    | 'monthly_bonus_credits'
  >;
  spaceURL: string;
}) {
  const { t, i18n } = useTranslation();
  const text = (values: Parameters<typeof localizedPlanText>[0]) =>
    localizedPlanText(values, i18n.language);
  const config = plan.display_config;
  const platforms = supportedPlanPlatforms(plan.disabled_adapters);
  const quotaLabel = text(config?.quota_summary) || t('cloudPlans.quotas');
  const legacyFeatures: Record<string, string> = {
    'Multi-user workspace': 'multiUserWorkspace',
    'Remote E2B sandbox configuration': 'remoteE2BSandbox',
    'Community support': 'communitySupport',
    'Everything in Free': 'everythingInFree',
    'One always-on global sandbox': 'alwaysOnSandbox',
    'Higher workspace limits': 'higherWorkspaceLimits',
  };
  const items =
    config?.items ??
    (plan.features ?? []).map((feature) => ({
      label: {
        en_US: legacyFeatures[feature]
          ? t(`cloudPlans.features.${legacyFeatures[feature]}`)
          : feature,
      },
      icon: 'ri-check-line',
      tooltip: {},
    }));
  const rows: Record<string, ReactNode> = {
    quota_summary: (
      <>
        <Layers className="size-4 shrink-0 text-blue-500" />
        <span className="min-w-0 break-words">{quotaLabel}</span>
        <Help label={quotaLabel}>
          {text(config?.tooltips?.quota_summary) && (
            <p className="mb-2">{text(config?.tooltips?.quota_summary)}</p>
          )}
          <ul className="space-y-2">
            {Object.entries(plan.limits)
              .filter(([key]) => key !== 'chat_history.retention_days')
              .map(([key, limit]) => {
                const resource = key.replace(/\.max$/, '');
                const label =
                  text(config?.quotas?.[key]?.label) ||
                  t(`cloudPlans.limits.${resource}`, {
                    defaultValue: resource.replace(/_/g, ' '),
                  });
                return (
                  <li key={key}>
                    <div className="flex justify-between gap-5">
                      <span>{label}</span>
                      <span>
                        {limit < 0
                          ? t('cloudPlans.unlimited')
                          : limit.toLocaleString()}
                      </span>
                    </div>
                    {text(config?.quotas?.[key]?.tooltip) && (
                      <p className="mt-1 opacity-75">
                        {text(config?.quotas?.[key]?.tooltip)}
                      </p>
                    )}
                  </li>
                );
              })}
          </ul>
        </Help>
      </>
    ),
    retention: (
      <>
        <PlanIcon name="ri-history-line" />
        <span className="min-w-0 break-words">
          {t('cloudPlans.retention', {
            count: plan.chat_history_retention_days,
          })}
        </span>
        <Help label={t('cloudPlans.retentionLabel')}>
          {text(config?.tooltips?.retention) || t('cloudPlans.retentionHelp')}
        </Help>
      </>
    ),
    monthly_credits: (
      <>
        <PlanIcon name="ri-coin-line" />
        <span className="min-w-0 break-words">
          {t('cloudPlans.credits', { count: plan.monthly_bonus_credits })}
        </span>
        <Help label={t('cloudPlans.creditsLabel')}>
          {text(config?.tooltips?.monthly_credits) ||
            t('cloudPlans.creditsHelp')}
        </Help>
      </>
    ),
    supported_platforms: (
      <>
        <PlanIcon name="ri-apps-2-line" />
        <span className="min-w-0 break-words">{t('cloudPlans.platforms')}</span>
        <Tooltip>
          <TooltipTrigger
            type="button"
            aria-label={t('cloudPlans.platforms')}
            className="flex h-5 shrink-0 items-center rounded text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-primary"
            onPointerDown={(event) => {
              if (event.pointerType === 'touch') event.preventDefault();
            }}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
            }}
          >
            <Info className="size-3.5" aria-hidden />
          </TooltipTrigger>
          <TooltipContent
            className="max-w-[min(360px,calc(100vw-2rem))] bg-foreground p-3 text-background"
            arrowClassName="bg-foreground fill-foreground"
          >
            {text(config?.tooltips?.supported_platforms) && (
              <p className="mb-2 whitespace-pre-line break-words">
                {text(config?.tooltips?.supported_platforms)}
              </p>
            )}
            <div className="flex flex-wrap gap-1.5" data-supported-platforms>
              {platforms.map((platform) => (
                <span
                  key={platform.name}
                  className="inline-flex items-center gap-1.5 rounded border border-background/30 px-1.5 py-1 text-xs"
                >
                  <img
                    src={cloudPlanPlatformIconURL(spaceURL, platform.icon)}
                    alt=""
                    referrerPolicy="no-referrer"
                    className="size-4 shrink-0 rounded-sm bg-white p-0.5 object-contain"
                  />
                  {t(
                    `cloudPlans.platformNames.${platform.name.replace('LINE', 'line').replace('openclaw-weixin', 'openclaw_weixin')}`,
                    { defaultValue: platform.label },
                  )}
                </span>
              ))}
            </div>
            {platforms.length === 0 && <p>{t('common.none')}</p>}
          </TooltipContent>
        </Tooltip>
      </>
    ),
  };
  items.forEach((item, index) => {
    const label = text(item.label);
    rows[`item:${index}`] = (
      <>
        <PlanIcon name={item.icon} />
        <span className="min-w-0 whitespace-pre-line break-words">{label}</span>
        {text(item.tooltip) && <Help label={label}>{text(item.tooltip)}</Help>}
      </>
    );
  });
  const order = [
    ...new Set([
      ...(config?.order ?? []),
      'quota_summary',
      'supported_platforms',
      'retention',
      'monthly_credits',
      ...items.map((_, index) => `item:${index}`),
    ]),
  ].filter((key) => key in rows);
  return (
    <ul className="space-y-3 text-sm">
      {order.map((key) => (
        <li key={key} className="flex items-start gap-2 break-words">
          {rows[key]}
        </li>
      ))}
    </ul>
  );
}

export default function CloudPlansDialog({
  open,
  onOpenChange,
  workspace,
  spaceURL,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspace: CurrentWorkspace;
  spaceURL: string;
}) {
  const { t, i18n } = useTranslation();
  const [plans, setPlans] = useState<PublicCloudPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [cycle, setCycle] = useState<CloudPlanBillingCycle>('annual');
  const currency = cloudPlanCurrencyForLanguage(i18n.language);
  const canManage = ['owner', 'admin'].includes(workspace.membership.role);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    let active = true;
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    setLoading(true);
    setError(false);
    fetchPublicCloudPlans(spaceURL, controller.signal)
      .then((value) => {
        if (active) setPlans(value);
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        window.clearTimeout(timeout);
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, [open, spaceURL, attempt]);
  const owned = workspace.current_plan;
  const latest = plans.find((plan) => plan.name === owned?.name);
  // Catalog copy of the purchased revision, so its card renders exactly like
  // the latest one. Benefits still come from the entitlement snapshot below.
  const [ownedRevision, setOwnedRevision] = useState<PublicCloudPlan | null>(
    null,
  );
  const ownedName = owned?.name;
  const ownedRevisionNumber = owned?.revision;
  const needsOwnedRevision =
    !!latest && !!ownedName && latest.revision !== ownedRevisionNumber;
  useEffect(() => {
    setOwnedRevision(null);
    if (!open || !needsOwnedRevision || !ownedName || !ownedRevisionNumber)
      return;
    const controller = new AbortController();
    fetchCloudPlanRevision(
      spaceURL,
      ownedName,
      ownedRevisionNumber,
      controller.signal,
    )
      .then(setOwnedRevision)
      // Fall back to the snapshot-only card when the revision is unavailable.
      .catch(() => {});
    return () => controller.abort();
  }, [open, spaceURL, needsOwnedRevision, ownedName, ownedRevisionNumber]);
  const rows = owned ? revisionRows(owned, latest) : [];
  const distinct =
    !!owned &&
    (!latest ||
      (owned.revision !== latest.revision && rows.some((row) => row.changed)));
  const entries: (PublicCloudPlan | 'owned')[] = [...plans];
  if (distinct) {
    const index = entries.findIndex(
      (plan) => plan !== 'owned' && plan.name === owned.name,
    );
    entries.splice(index < 0 ? 0 : index, 0, 'owned');
  }
  // Copy, prices and display items come from the purchased revision itself;
  // limits, platforms, retention and credits come only from the workspace
  // entitlement snapshot, never from the latest revision.
  const ownedCatalog =
    ownedRevision?.revision === owned?.revision ? ownedRevision : null;
  const ownedPlan: PublicCloudPlan | null =
    distinct && owned
      ? {
          uuid: `owned-${owned.name}-${owned.revision}`,
          name: owned.name,
          revision: owned.revision,
          display_name:
            ownedCatalog?.display_name ?? latest?.display_name ?? {},
          description: ownedCatalog?.description ?? {},
          price_cny: ownedCatalog?.price_cny ?? '0',
          price_usd: ownedCatalog?.price_usd ?? '0',
          price_jpy: ownedCatalog?.price_jpy ?? '0',
          limits: owned.limits,
          features: ownedCatalog?.features ?? [],
          is_active: true,
          sort_order: latest?.sort_order ?? 0,
          highlight: ownedCatalog?.highlight ?? false,
          chat_history_retention_days:
            owned.limits['chat_history.retention_days'] ?? 30,
          monthly_bonus_credits: owned.monthly_bonus_credits,
          disabled_adapters: Object.entries(owned.entitlement_features)
            .filter(([key, enabled]) => key.startsWith('platform.') && !enabled)
            .map(([key]) => key.slice(9)),
          display_config: ownedCatalog?.display_config
            ? ownedCatalog.display_config
            : latest?.display_config
              ? {
                  icon: latest.display_config.icon,
                  order: latest.display_config.order,
                  tooltips: latest.display_config.tooltips,
                  quotas: latest.display_config.quotas,
                  items: [],
                }
              : { items: [] },
        }
      : null;
  const subscribedOn = owned?.subscription_started_at
    ? t('planRevision.subscribedOn', {
        interpolation: { escapeValue: false },
        date: new Date(owned.subscription_started_at * 1000).toLocaleDateString(
          i18n.language.replace('_', '-'),
        ),
      })
    : null;
  const formatPrice = (price: number) =>
    new Intl.NumberFormat(i18n.language.replace('_', '-'), {
      style: 'currency',
      currency,
      maximumFractionDigits: currency === 'JPY' ? 0 : 2,
    }).format(price);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[90dvh] flex-col gap-5 overflow-hidden sm:max-w-5xl"
        data-cloud-plans
      >
        <DialogHeader>
          <DialogTitle>{t('cloudPlans.title')}</DialogTitle>
          <DialogDescription>
            {t('cloudPlans.description', {
              workspace: workspace.workspace.name,
            })}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div
            className="inline-flex rounded-lg bg-muted p-1"
            role="group"
            aria-label={t('cloudPlans.billing')}
          >
            {(['monthly', 'annual'] as const).map((value) => (
              <Button
                key={value}
                size="sm"
                variant="ghost"
                aria-pressed={cycle === value}
                className={cn(cycle === value && 'bg-background shadow-sm')}
                onClick={() => setCycle(value)}
              >
                {t(`cloudPlans.${value}`)}
              </Button>
            ))}
          </div>
        </div>
        <div className="min-h-0 overflow-y-auto [scrollbar-gutter:stable]">
          {!loading && (
            <>
              {!workspace.current_plan && (
                <p className="mb-4 text-sm" role="status">
                  {t('planRevision.unknown')}
                </p>
              )}
            </>
          )}
          {loading ? (
            <div
              className="flex min-h-48 items-center justify-center"
              role="status"
            >
              <Loader2 className="size-6 animate-spin" />
              <span className="sr-only">{t('cloudPlans.loading')}</span>
            </div>
          ) : error ? (
            <div className="space-y-3 py-10 text-center" role="alert">
              <p>{t('cloudPlans.error')}</p>
              <Button
                variant="outline"
                onClick={() => setAttempt((value) => value + 1)}
              >
                <RefreshCw />
                {t('cloudPlans.retry')}
              </Button>
            </div>
          ) : !entries.length ? (
            <p className="py-10 text-center text-muted-foreground">
              {t('cloudPlans.empty')}
            </p>
          ) : (
            <TooltipProvider delayDuration={200}>
              <div
                className={cn(
                  'flex gap-4 overflow-x-auto p-1 [&>*]:w-72 [&>*]:shrink-0 [&>*]:grow',
                )}
              >
                {entries.map((plan) => {
                  const renderCard = (
                    plan: PublicCloudPlan,
                    ownedCard = false,
                  ) => {
                    const samePlan = workspace.plan_name === plan.name;
                    const current =
                      ownedCard || (samePlan && !distinct && !!owned);
                    // Both stacked revisions share one card style; only the
                    // badge text tells them apart.
                    const stacked = distinct && plan.name === owned?.name;
                    const downgradeBlocked =
                      Boolean(
                        workspace.plan_name && workspace.plan_name !== 'free',
                      ) && plan.name === 'free';
                    const price = cloudPlanPrice(plan, cycle, currency);
                    const name =
                      localizedPlanText(plan.display_name, i18n.language) ||
                      plan.name.toUpperCase();
                    return (
                      <article
                        key={plan.uuid}
                        data-owned-plan={ownedCard || undefined}
                        className={cn(
                          'flex min-w-0 flex-col rounded-xl border p-5',
                          current &&
                            !stacked &&
                            'border-blue-500/50 bg-blue-500/5',
                        )}
                        aria-label={name}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <h3 className="flex items-center gap-2 font-semibold">
                            <PlanIcon name={plan.display_config?.icon} />
                            {name}
                          </h3>
                          {current ? (
                            <Badge variant={stacked ? 'default' : 'secondary'}>
                              {t('cloudPlans.current')}
                            </Badge>
                          ) : plan.highlight ? (
                            <Badge>{t('cloudPlans.recommended')}</Badge>
                          ) : null}
                        </div>
                        <p className="mt-2 text-sm text-muted-foreground">
                          {localizedPlanText(plan.description, i18n.language)}
                          {distinct &&
                            !ownedCard &&
                            plan.name === owned?.name && (
                              <span className="block" data-latest-quota>
                                {t('planRevision.latestQuota')}
                              </span>
                            )}
                          {ownedCard && subscribedOn && (
                            <span className="block" data-subscribed-on>
                              {subscribedOn}
                            </span>
                          )}
                        </p>
                        {ownedCard && !ownedCatalog ? (
                          <div className="mb-5" />
                        ) : (
                          <>
                            <p className="mt-5 text-2xl font-semibold">
                              {price === 0
                                ? t('cloudPlans.free')
                                : formatPrice(price)}
                              {price > 0 && (
                                <span className="ml-1 text-xs font-normal text-muted-foreground">
                                  / {t(`cloudPlans.${cycle}`)}
                                </span>
                              )}
                            </p>
                            <p className="mb-5 mt-1 min-h-4 text-xs text-muted-foreground">
                              {cycle === 'annual' && price > 0
                                ? t('cloudPlans.annualNote', {
                                    price: formatPrice(price / 12),
                                  })
                                : ''}
                            </p>
                          </>
                        )}
                        <div className="flex-1">
                          <Benefits plan={plan} spaceURL={spaceURL} />
                        </div>
                        {plan.subscription_disabled && (
                          <p className="mt-4 text-xs text-muted-foreground">
                            {t('cloudPlans.subscriptionUnavailableHint')}
                          </p>
                        )}
                        {plan.subscription_disabled && !current ? (
                          <Button
                            className="mt-6 w-full"
                            variant="outline"
                            disabled
                          >
                            {t('cloudPlans.subscriptionUnavailable')}
                          </Button>
                        ) : downgradeBlocked ? null : !canManage ? (
                          <Button
                            className="mt-6 w-full"
                            variant="outline"
                            disabled
                          >
                            {t('cloudPlans.ownerOnly')}
                          </Button>
                        ) : distinct &&
                          !ownedCard &&
                          plan.name === owned?.name ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                asChild
                                className="mt-6 w-full"
                                variant={plan.highlight ? 'default' : 'outline'}
                              >
                                <a
                                  href={cloudSubscriptionManagementURL(
                                    spaceURL,
                                    workspace.workspace.uuid,
                                  )}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  {t('cloudPlans.manageSubscription')}
                                  <ArrowRight className="size-4" />
                                </a>
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              {t('planRevision.cancelToSubscribe')}
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <Button
                            asChild
                            className="mt-6 w-full"
                            variant={plan.highlight ? 'default' : 'outline'}
                          >
                            <a
                              href={
                                workspace.plan_name &&
                                workspace.plan_name !== 'free'
                                  ? cloudSubscriptionManagementURL(
                                      spaceURL,
                                      workspace.workspace.uuid,
                                    )
                                  : cloudPlanCheckoutURL(
                                      spaceURL,
                                      workspace.workspace.uuid,
                                      plan.name,
                                      cycle,
                                      currency,
                                    )
                              }
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {t(
                                workspace.plan_name &&
                                  workspace.plan_name !== 'free'
                                  ? 'cloudPlans.manageSubscription'
                                  : 'cloudPlans.choose',
                              )}
                              <ArrowRight className="size-4" />
                            </a>
                          </Button>
                        )}
                        {ownedCard && !latest && (
                          <p className="mt-4 text-sm">
                            {t('planRevision.unavailable')}
                          </p>
                        )}
                      </article>
                    );
                  };
                  if (plan === 'owned')
                    return ownedPlan && !latest
                      ? renderCard(ownedPlan, true)
                      : null;
                  return ownedPlan && latest === plan ? (
                    <PlanRevisionStack
                      key={plan.uuid}
                      current={renderCard(ownedPlan, true)}
                      latest={renderCard(plan)}
                    />
                  ) : (
                    renderCard(plan)
                  );
                })}
              </div>
            </TooltipProvider>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {t('cloudPlans.handoff')}
        </p>
      </DialogContent>
    </Dialog>
  );
}
