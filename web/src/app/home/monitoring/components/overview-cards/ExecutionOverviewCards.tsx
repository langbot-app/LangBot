import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import {
  Activity,
  BellRing,
  CheckCircle2,
  Timer,
  TriangleAlert,
  Users,
  Zap,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { ExecutionSummary } from '@/app/infra/entities/api/monitoring-executions';
import { formatRunDuration } from '@/app/home/agents/components/processor-run-timing';
import { backendClient, useCurrentWorkspace } from '@/app/infra/http';
import { MetricCard } from './MetricCard';

interface ExecutionOverviewCardsProps {
  summary: ExecutionSummary | null;
  loading?: boolean;
  /** Active bot conversation sessions from the message rollup endpoint. */
  activeSessions?: number | null;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <div className="text-2xl font-bold tabular-nums text-foreground">
        {value}
      </div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

/**
 * Nudges admins toward alerts when the dashboard already shows failures but
 * the Workspace has not turned alerts on. Opens Settings → Alerts in place.
 */
function EnableAlertsHint({ failed }: { failed: number }) {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentWorkspace = useCurrentWorkspace();
  const canView = (currentWorkspace?.permissions ?? []).includes('audit.view');
  const settingsAction = searchParams.get('action');
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!canView || failed <= 0 || settingsAction) return;
    let active = true;
    backendClient
      .getAlertSummary()
      .then((summary) => {
        if (active) setShow(summary.enabled_instance_wide && !summary.enabled);
      })
      .catch(() => {
        if (active) setShow(false);
      });
    return () => {
      active = false;
    };
    // Re-check when the settings dialog closes (its ?action= is removed).
  }, [canView, failed, settingsAction]);

  if (!canView || failed <= 0 || !show) return null;
  return (
    <button
      type="button"
      onClick={() => {
        const params = new URLSearchParams(searchParams);
        params.set('action', 'showAlerts');
        setSearchParams(params);
      }}
      className="inline-flex w-fit items-center gap-1.5 rounded-md border border-red-500/25 bg-red-500/5 px-2 py-1 text-xs font-medium text-red-600 transition-colors hover:bg-red-500/10 dark:text-red-400"
    >
      <BellRing className="size-3.5" />
      {t('alerts.enableHint')}
    </button>
  );
}

export default function ExecutionOverviewCards({
  summary,
  loading,
  activeSessions,
}: ExecutionOverviewCardsProps) {
  const { t } = useTranslation();
  const overview = summary?.executions ?? null;
  const tokens = summary?.tokens ?? null;

  // Bare cards, not a grid: the page owns the grid so every metric and the
  // runtime status card land in the same rows.
  return (
    <>
      <MetricCard
        label={t('monitoring.execution.cards.totalExecutions')}
        icon={<Activity className="h-4 w-4" />}
        accent="#8b5cf6"
        loading={loading}
        value={(overview?.total ?? 0).toLocaleString()}
        hint={t('monitoring.execution.cards.bySource', {
          agent: (overview?.by_source.agent ?? 0).toLocaleString(),
          pipeline: (overview?.by_source.pipeline ?? 0).toLocaleString(),
        })}
      >
        {!!overview?.debug && (
          <div className="text-xs text-muted-foreground">
            {t('monitoring.execution.cards.debugRuns', {
              count: overview.debug,
            })}
          </div>
        )}
      </MetricCard>

      <MetricCard
        label={t('monitoring.execution.cards.successRate')}
        description={t('monitoring.execution.cards.successRateHint')}
        icon={<CheckCircle2 className="h-4 w-4" />}
        accent="#3b82f6"
        loading={loading}
        value={
          overview?.success_rate != null ? `${overview.success_rate}%` : '—'
        }
        hint={t('monitoring.execution.cards.denominator', {
          completed: (overview?.completed ?? 0).toLocaleString(),
          denominator: (overview?.denominator ?? 0).toLocaleString(),
        })}
      />

      <MetricCard
        label={t('monitoring.execution.cards.running')}
        icon={<Activity className="h-4 w-4" />}
        accent="#06b6d4"
        loading={loading}
      >
        <div className="grid grid-cols-3 gap-3">
          <Stat
            label={t('monitoring.execution.cards.running')}
            value={(overview?.running ?? 0).toLocaleString()}
          />
          <Stat
            label={t('monitoring.execution.cards.queued')}
            value={(overview?.queued ?? 0).toLocaleString()}
          />
          <Stat
            label={t('monitoring.execution.cards.waiting')}
            value={(overview?.waiting ?? 0).toLocaleString()}
          />
        </div>
      </MetricCard>

      <MetricCard
        label={t('monitoring.execution.cards.failed')}
        icon={<TriangleAlert className="h-4 w-4" />}
        accent="#ef4444"
        loading={loading}
        value={
          <span className="flex items-center gap-3">
            {(overview?.failed ?? 0).toLocaleString()}
            <Badge variant="secondary">
              {t('monitoring.execution.cards.ignored')}{' '}
              {(overview?.ignored ?? 0).toLocaleString()}
            </Badge>
          </span>
        }
      >
        {!loading && <EnableAlertsHint failed={overview?.failed ?? 0} />}
      </MetricCard>

      <MetricCard
        label={t('monitoring.execution.cards.latency')}
        description={t('monitoring.execution.cards.latencyHint')}
        icon={<Timer className="h-4 w-4" />}
        accent="#f59e0b"
        loading={loading}
      >
        <div className="grid grid-cols-2 gap-3">
          <Stat
            label={t('monitoring.execution.cards.p50')}
            value={
              overview?.p50_duration_ms != null
                ? formatRunDuration(overview.p50_duration_ms)
                : '—'
            }
          />
          <Stat
            label={t('monitoring.execution.cards.p95')}
            value={
              overview?.p95_duration_ms != null
                ? formatRunDuration(overview.p95_duration_ms)
                : '—'
            }
          />
        </div>
        {/* The sample size explains the percentiles above, so it stays under
            them rather than in the card's hint slot. */}
        <div className="text-xs text-muted-foreground">
          {t('monitoring.execution.cards.sample', {
            count: overview?.duration_sample ?? 0,
          })}
        </div>
      </MetricCard>

      <MetricCard
        label={t('monitoring.execution.cards.tokens')}
        description={t('monitoring.execution.cards.tokensHint')}
        icon={<Zap className="h-4 w-4" />}
        accent="#10b981"
        loading={loading}
        value={(tokens?.total_tokens ?? 0).toLocaleString()}
        hint={t('monitoring.execution.cards.coverage', {
          withUsage: (tokens?.calls_with_usage ?? 0).toLocaleString(),
          calls: (tokens?.calls ?? 0).toLocaleString(),
        })}
      />

      <MetricCard
        label={t('monitoring.activeSessions')}
        icon={<Users className="h-4 w-4" />}
        accent="#6366f1"
        loading={loading}
        value={(activeSessions ?? 0).toLocaleString()}
      />
    </>
  );
}
