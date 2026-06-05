import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ComposedChart,
  Area,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  Coins,
  ArrowDownToLine,
  ArrowUpFromLine,
  Gauge,
  AlertTriangle,
  TrendingUp,
} from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';

interface TokenSummary {
  total_calls: number;
  success_calls: number;
  error_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost: number;
  avg_tokens_per_call: number;
  avg_duration_ms: number;
  avg_tokens_per_second: number;
  zero_token_success_calls: number;
}

interface TokenByModel {
  model_name: string;
  calls: number;
  error_calls: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  avg_tokens_per_call: number;
  avg_duration_ms: number;
}

interface TokenTimeseriesPoint {
  bucket: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  calls: number;
}

interface TokenStatistics {
  summary: TokenSummary;
  by_model: TokenByModel[];
  timeseries: TokenTimeseriesPoint[];
  bucket: string;
}

interface TokenMonitoringProps {
  botIds?: string[];
  pipelineIds?: string[];
  startTime?: string;
  endTime?: string;
  /** Bumped by the parent to trigger a refetch on manual refresh. */
  refreshKey?: number;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

const TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: 'var(--card)',
  border: '1px solid var(--border)',
  borderRadius: '12px',
  boxShadow:
    '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  fontSize: '13px',
  padding: '12px',
  color: 'var(--foreground)',
};

function MetricTile({
  icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="bg-card rounded-xl border p-4 flex flex-col gap-2">
      <div className="flex items-center gap-2 text-muted-foreground text-sm">
        <span
          className="flex items-center justify-center h-7 w-7 rounded-lg"
          style={{
            backgroundColor: accent ? `${accent}1a` : 'var(--muted)',
            color: accent || 'var(--foreground)',
          }}
        >
          {icon}
        </span>
        {label}
      </div>
      <div className="text-2xl font-semibold text-foreground tabular-nums">
        {value}
      </div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

export default function TokenMonitoring({
  botIds,
  pipelineIds,
  startTime,
  endTime,
  refreshKey,
}: TokenMonitoringProps) {
  const { t } = useTranslation();
  const [bucket, setBucket] = useState<'hour' | 'day'>('hour');
  const [stats, setStats] = useState<TokenStatistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const botIdsKey = JSON.stringify(botIds);
  const pipelineIdsKey = JSON.stringify(pipelineIds);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await httpClient.getTokenStatistics({
        botId: botIds,
        pipelineId: pipelineIds,
        startTime,
        endTime,
        bucket,
      });
      setStats(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botIdsKey, pipelineIdsKey, startTime, endTime, bucket, refreshKey]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const chartData = useMemo(() => {
    if (!stats) return [];
    return stats.timeseries.map((p) => ({
      bucket: p.bucket,
      input: p.input_tokens,
      output: p.output_tokens,
      total: p.total_tokens,
    }));
  }, [stats]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="bg-card rounded-xl border p-4 h-24 animate-pulse"
            />
          ))}
        </div>
        <div className="bg-card rounded-xl border p-6 h-[320px] animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-card rounded-xl border p-6 text-sm text-destructive flex items-center gap-2">
        <AlertTriangle className="h-4 w-4" />
        {t('monitoring.tokens.loadError', { error })}
      </div>
    );
  }

  if (!stats || stats.summary.total_calls === 0) {
    return (
      <div className="bg-card rounded-xl border p-6">
        <div className="h-[260px] flex flex-col items-center justify-center text-muted-foreground gap-2">
          <Coins className="h-[3rem] w-[3rem]" />
          <div className="text-sm">{t('monitoring.tokens.noData')}</div>
        </div>
      </div>
    );
  }

  const { summary, by_model } = stats;

  return (
    <div className="space-y-6">
      {/* Data-quality warning: streamed calls that recorded 0 tokens */}
      {summary.zero_token_success_calls > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-400 rounded-xl p-4 text-sm flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>
            {t('monitoring.tokens.zeroTokenWarning', {
              count: summary.zero_token_success_calls,
            })}
          </span>
        </div>
      )}

      {/* Summary tiles */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricTile
          icon={<Coins className="h-4 w-4" />}
          label={t('monitoring.tokens.totalTokens')}
          value={formatNumber(summary.total_tokens)}
          sub={t('monitoring.tokens.acrossCalls', {
            count: summary.total_calls,
          })}
          accent="#8b5cf6"
        />
        <MetricTile
          icon={<ArrowDownToLine className="h-4 w-4" />}
          label={t('monitoring.tokens.inputTokens')}
          value={formatNumber(summary.total_input_tokens)}
          accent="#3b82f6"
        />
        <MetricTile
          icon={<ArrowUpFromLine className="h-4 w-4" />}
          label={t('monitoring.tokens.outputTokens')}
          value={formatNumber(summary.total_output_tokens)}
          accent="#10b981"
        />
        <MetricTile
          icon={<TrendingUp className="h-4 w-4" />}
          label={t('monitoring.tokens.avgPerCall')}
          value={formatNumber(summary.avg_tokens_per_call)}
          accent="#f59e0b"
        />
        <MetricTile
          icon={<Gauge className="h-4 w-4" />}
          label={t('monitoring.tokens.throughput')}
          value={`${summary.avg_tokens_per_second}`}
          sub={t('monitoring.tokens.tokensPerSec')}
          accent="#06b6d4"
        />
        <MetricTile
          icon={<AlertTriangle className="h-4 w-4" />}
          label={t('monitoring.tokens.errorCalls')}
          value={`${summary.error_calls}`}
          sub={t('monitoring.tokens.ofTotal', { count: summary.total_calls })}
          accent="#ef4444"
        />
      </div>

      {/* Token usage over time */}
      <div className="bg-card rounded-xl border p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-base font-semibold text-foreground">
            {t('monitoring.tokens.usageOverTime')}
          </h3>
          <div className="inline-flex rounded-lg border p-0.5 text-sm">
            {(['hour', 'day'] as const).map((b) => (
              <button
                key={b}
                onClick={() => setBucket(b)}
                className={`px-3 py-1 rounded-md transition-colors ${
                  bucket === b
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {t(`monitoring.tokens.bucket.${b}`)}
              </button>
            ))}
          </div>
        </div>
        <div className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={chartData}
              margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id="tokTotal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.03} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="var(--border)"
                vertical={false}
              />
              <XAxis
                dataKey="bucket"
                tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
                tickLine={false}
                axisLine={{ stroke: 'var(--border)' }}
                dy={10}
              />
              <YAxis
                tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
                tickLine={false}
                axisLine={{ stroke: 'var(--border)' }}
                width={48}
                tickFormatter={(v) => formatNumber(Number(v))}
              />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                labelStyle={{
                  fontWeight: 600,
                  marginBottom: '8px',
                  color: 'var(--foreground)',
                }}
                formatter={(value: number) => formatNumber(Number(value))}
              />
              <Legend
                wrapperStyle={{
                  fontSize: '13px',
                  paddingTop: '16px',
                  fontWeight: 500,
                }}
                iconType="circle"
                iconSize={10}
              />
              <Bar
                dataKey="input"
                name={t('monitoring.tokens.inputTokens')}
                stackId="io"
                fill="#3b82f6"
                radius={[0, 0, 0, 0]}
                barSize={18}
              />
              <Bar
                dataKey="output"
                name={t('monitoring.tokens.outputTokens')}
                stackId="io"
                fill="#10b981"
                radius={[4, 4, 0, 0]}
                barSize={18}
              />
              <Area
                type="monotone"
                dataKey="total"
                name={t('monitoring.tokens.totalTokens')}
                stroke="#8b5cf6"
                strokeWidth={2.5}
                fill="url(#tokTotal)"
                dot={false}
                activeDot={{ r: 5, strokeWidth: 2 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Per-model breakdown */}
      <div className="bg-card rounded-xl border p-6">
        <h3 className="text-base font-semibold text-foreground mb-4">
          {t('monitoring.tokens.byModel')}
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground border-b">
                <th className="py-2 pr-4 font-medium">
                  {t('monitoring.tokens.model')}
                </th>
                <th className="py-2 px-4 font-medium text-right">
                  {t('monitoring.tokens.calls')}
                </th>
                <th className="py-2 px-4 font-medium text-right">
                  {t('monitoring.tokens.inputTokens')}
                </th>
                <th className="py-2 px-4 font-medium text-right">
                  {t('monitoring.tokens.outputTokens')}
                </th>
                <th className="py-2 px-4 font-medium text-right">
                  {t('monitoring.tokens.totalTokens')}
                </th>
                <th className="py-2 px-4 font-medium text-right">
                  {t('monitoring.tokens.avgPerCall')}
                </th>
                <th className="py-2 pl-4 font-medium text-right">
                  {t('monitoring.tokens.avgLatency')}
                </th>
              </tr>
            </thead>
            <tbody>
              {by_model.map((m) => {
                const share =
                  summary.total_tokens > 0
                    ? (m.total_tokens / summary.total_tokens) * 100
                    : 0;
                return (
                  <tr
                    key={m.model_name}
                    className="border-b last:border-0 hover:bg-muted/40 transition-colors"
                  >
                    <td className="py-2.5 pr-4">
                      <div className="font-medium text-foreground">
                        {m.model_name}
                      </div>
                      <div className="mt-1 h-1.5 w-32 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full rounded-full bg-violet-500"
                          style={{ width: `${share}%` }}
                        />
                      </div>
                    </td>
                    <td className="py-2.5 px-4 text-right tabular-nums">
                      {m.calls}
                      {m.error_calls > 0 && (
                        <span className="text-destructive">
                          {' '}
                          ({m.error_calls}✕)
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-4 text-right tabular-nums">
                      {formatNumber(m.input_tokens)}
                    </td>
                    <td className="py-2.5 px-4 text-right tabular-nums">
                      {formatNumber(m.output_tokens)}
                    </td>
                    <td className="py-2.5 px-4 text-right tabular-nums font-medium">
                      {formatNumber(m.total_tokens)}
                    </td>
                    <td className="py-2.5 px-4 text-right tabular-nums">
                      {formatNumber(m.avg_tokens_per_call)}
                    </td>
                    <td className="py-2.5 pl-4 text-right tabular-nums">
                      {m.avg_duration_ms}ms
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
