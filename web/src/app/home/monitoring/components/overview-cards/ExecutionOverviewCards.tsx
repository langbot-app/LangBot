import { useTranslation } from 'react-i18next';
import {
  Activity,
  CheckCircle2,
  Timer,
  TriangleAlert,
  Users,
  Zap,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { ExecutionSummary } from '@/app/infra/entities/api/monitoring-executions';
import { formatRunDuration } from '@/app/home/agents/components/processor-run-timing';
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
      />

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
