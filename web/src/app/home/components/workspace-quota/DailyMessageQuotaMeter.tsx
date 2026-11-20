import { MessageSquare } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import {
  formatQuotaReset,
  openCloudPlans,
  quotaLevel,
  useDailyMessageQuota,
  type QuotaLevel,
} from './useDailyMessageQuota';

const BAR_COLOR: Record<QuotaLevel, string> = {
  normal: 'bg-primary',
  warning: 'bg-amber-500',
  exhausted: 'bg-destructive',
};

function UsageBar({ percent, level }: { percent: number; level: QuotaLevel }) {
  return (
    <div
      className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(percent)}
    >
      <div
        className={cn('h-full rounded-full transition-all', BAR_COLOR[level])}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

/**
 * Compact daily message meter for the sidebar footer. Renders nothing outside
 * Cloud or when the plan does not cap messages.
 */
export function SidebarDailyMessageQuota() {
  const { t } = useTranslation();
  const { cloud, quota } = useDailyMessageQuota();
  if (!cloud || !quota?.enforced || quota.limit <= 0) return null;

  const level = quotaLevel(quota);
  const percent = Math.min(100, (quota.used / quota.limit) * 100);
  const reset = formatQuotaReset(t, quota.resets_at);
  const summary = t('dailyMessageQuota.usage', {
    used: quota.used.toLocaleString(),
    limit: quota.limit.toLocaleString(),
  });

  return (
    <>
      {/* Collapsed sidebar: an icon with the numbers in a tooltip. */}
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={openCloudPlans}
            aria-label={`${t('dailyMessageQuota.title')} ${summary}`}
            className={cn(
              'mx-auto hidden size-8 items-center justify-center rounded-md hover:bg-sidebar-accent group-data-[collapsible=icon]:flex',
              level === 'exhausted'
                ? 'text-destructive'
                : level === 'warning'
                  ? 'text-amber-600'
                  : 'text-muted-foreground',
            )}
          >
            <MessageSquare className="size-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right">
          {t('dailyMessageQuota.title')} · {summary}
        </TooltipContent>
      </Tooltip>

      <div
        className={cn(
          'mx-2 space-y-2 rounded-lg border px-3 py-2.5 group-data-[collapsible=icon]:hidden',
          level === 'exhausted'
            ? 'border-destructive/40 bg-destructive/5'
            : 'bg-sidebar',
        )}
        data-daily-message-quota
      >
        <div className="flex items-center justify-between gap-2 text-xs">
          <span className="flex items-center gap-1.5 font-medium">
            <MessageSquare className="size-3.5 text-muted-foreground" />
            {t('dailyMessageQuota.title')}
          </span>
          <span
            className={cn(
              'tabular-nums',
              level === 'exhausted'
                ? 'font-medium text-destructive'
                : 'text-muted-foreground',
            )}
          >
            {summary}
          </span>
        </div>
        <UsageBar percent={percent} level={level} />
        {level === 'exhausted' ? (
          <div className="space-y-2">
            <p className="text-[11px] leading-4 text-destructive">
              {t('dailyMessageQuota.exhaustedHint', { time: reset })}
            </p>
            <Button
              size="sm"
              className="h-7 w-full text-xs"
              onClick={openCloudPlans}
            >
              {t('dailyMessageQuota.upgrade')}
            </Button>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
            <span>
              {level === 'warning'
                ? t('dailyMessageQuota.nearLimit')
                : t('dailyMessageQuota.remaining', {
                    count: quota.remaining,
                  })}
            </span>
            <span>{t('dailyMessageQuota.resetsAt', { time: reset })}</span>
          </div>
        )}
      </div>
    </>
  );
}

/** Daily message quota section for the Workspace settings panel. */
export function WorkspaceDailyMessageQuota({
  onUpgrade,
}: {
  onUpgrade: () => void;
}) {
  const { t } = useTranslation();
  const { cloud, quota, error } = useDailyMessageQuota();
  if (!cloud) return null;

  const enforced = !!quota?.enforced && quota.limit > 0;
  const level = quota ? quotaLevel(quota) : 'normal';
  const percent = enforced
    ? Math.min(100, (quota!.used / quota!.limit) * 100)
    : 0;

  return (
    <section className="space-y-3" data-workspace-daily-message-quota>
      <div>
        <h3 className="text-sm font-semibold">
          {t('dailyMessageQuota.settingsTitle')}
        </h3>
        <p className="text-xs text-muted-foreground">
          {t('dailyMessageQuota.settingsDescription')}
        </p>
      </div>
      <div className="rounded-lg border p-4">
        {!quota ? (
          <p className="text-sm text-muted-foreground">
            {error ? t('dailyMessageQuota.unavailable') : '…'}
          </p>
        ) : !enforced ? (
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm">{t('dailyMessageQuota.title')}</span>
            <span className="text-sm font-medium">
              {t('dailyMessageQuota.unlimited')}
            </span>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-end justify-between gap-3">
              <div>
                <p className="text-xs text-muted-foreground">
                  {t('dailyMessageQuota.title')}
                </p>
                <p
                  className={cn(
                    'text-2xl font-semibold tabular-nums',
                    level === 'exhausted' && 'text-destructive',
                  )}
                >
                  {quota.used.toLocaleString()}
                  <span className="text-sm font-normal text-muted-foreground">
                    {' '}
                    / {quota.limit.toLocaleString()}
                  </span>
                </p>
              </div>
              <p className="text-xs text-muted-foreground">
                {t('dailyMessageQuota.resetsAt', {
                  time: formatQuotaReset(t, quota.resets_at),
                })}
              </p>
            </div>
            <UsageBar percent={percent} level={level} />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p
                className={cn(
                  'text-xs',
                  level === 'exhausted'
                    ? 'text-destructive'
                    : 'text-muted-foreground',
                )}
              >
                {level === 'exhausted'
                  ? t('dailyMessageQuota.exhausted')
                  : t('dailyMessageQuota.remaining', {
                      count: quota.remaining,
                    })}
              </p>
              <Button size="sm" variant="outline" onClick={onUpgrade}>
                {t('dailyMessageQuota.upgrade')}
              </Button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
