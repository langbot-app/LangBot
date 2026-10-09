import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { BarChart3, ChevronDown } from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Card } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Skeleton } from '@/components/ui/skeleton';
import { MonitoringData } from '../../types/monitoring';

interface TrafficChartProps {
  traffic?: MonitoringData['traffic'];
  loading?: boolean;
}

export default function TrafficChart(props: TrafficChartProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(() => {
    try { return localStorage.getItem('langbot-traffic-chart-open') !== 'false'; }
    catch { return true; }
  });
  return (
    <Collapsible open={open} onOpenChange={(value) => {
      setOpen(value);
      try { localStorage.setItem('langbot-traffic-chart-open', String(value)); } catch { /* Storage may be unavailable. */ }
    }} asChild>
      <Card className="gap-0 overflow-hidden py-0">
        <CollapsibleTrigger asChild>
          <button type="button" className="group flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400"><BarChart3 className="size-4" /></span>
            <span className="flex-1 text-sm font-semibold">{t('monitoring.trafficChart.title')}</span>
            <span className="hidden items-center gap-4 text-xs text-muted-foreground sm:flex">
              <span className="flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-blue-500" />{t('monitoring.trafficChart.messages')}</span>
              <span className="flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-violet-500" />{t('monitoring.trafficChart.llmCalls')}</span>
            </span>
            <ChevronDown className={`ml-2 size-4 text-muted-foreground transition-transform motion-reduce:transition-none ${open ? 'rotate-180' : ''}`} />
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="border-t px-3 pb-4 pt-4 sm:px-5">
            <TrafficChartContent {...props} />
          </div>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}

function TrafficChartContent({ traffic, loading }: TrafficChartProps) {
  const { t } = useTranslation();
  const chartData = useMemo(
    () =>
      (traffic?.points ?? []).map((point) => ({
        ...point,
        time: point.timestamp.toLocaleString(
          [],
          traffic?.bucket === 'day'
            ? { month: 'short', day: 'numeric' }
            : {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              },
        ),
      })),
    [traffic],
  );

  if (loading) {
    return (
      <div>
        <div className="h-[300px] flex items-center justify-center">
          <Skeleton className="w-full h-full rounded" />
        </div>
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div>
        <div className="h-[300px] flex flex-col items-center justify-center text-muted-foreground gap-2">
          <BarChart3 className="h-[3rem] w-[3rem]" />
          <div className="text-sm">
            {t(
              traffic
                ? 'monitoring.trafficChart.noData'
                : 'monitoring.trafficChart.unavailable',
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {traffic?.truncated && (
        <p role="status" className="text-sm text-muted-foreground mb-3">
          {t('monitoring.trafficChart.truncated')}
        </p>
      )}
      <div className="h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={chartData}
            margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="colorMessages" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.05} />
              </linearGradient>
              <linearGradient id="colorLLMCalls" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--border)"
              vertical={false}
            />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
              dy={10}
            />
            <YAxis
              tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
              width={40}
              allowDecimals={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--card)',
                border: '1px solid var(--border)',
                borderRadius: '12px',
                boxShadow:
                  '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
                fontSize: '13px',
                padding: '12px',
                color: 'var(--foreground)',
              }}
              labelStyle={{
                fontWeight: 600,
                marginBottom: '8px',
                color: 'var(--foreground)',
              }}
              itemStyle={{ padding: '4px 0' }}
            />
            <Area
              type="monotone"
              dataKey="messages"
              name={t('monitoring.trafficChart.messages')}
              stroke="#3b82f6"
              strokeWidth={2.5}
              fillOpacity={1}
              fill="url(#colorMessages)"
              dot={false}
              activeDot={{ r: 6, strokeWidth: 2 }}
            />
            <Area
              type="monotone"
              dataKey="llmCalls"
              name={t('monitoring.trafficChart.llmCalls')}
              stroke="#8b5cf6"
              strokeWidth={2.5}
              fillOpacity={1}
              fill="url(#colorLLMCalls)"
              dot={false}
              activeDot={{ r: 6, strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
