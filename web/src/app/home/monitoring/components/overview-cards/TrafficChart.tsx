import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { BarChart3 } from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { MonitoringData } from '../../types/monitoring';

interface TrafficChartProps {
  traffic?: MonitoringData['traffic'];
  loading?: boolean;
}

export default function TrafficChart({ traffic, loading }: TrafficChartProps) {
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
      <div className="bg-card rounded-xl border p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="h-5 w-32 bg-muted animate-pulse rounded"></div>
          <div className="flex gap-4">
            <div className="h-4 w-24 bg-muted animate-pulse rounded"></div>
            <div className="h-4 w-24 bg-muted animate-pulse rounded"></div>
          </div>
        </div>
        <div className="h-[300px] flex items-center justify-center">
          <div className="animate-pulse w-full h-full bg-muted rounded"></div>
        </div>
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="bg-card rounded-xl border p-6">
        <h3 className="text-base font-semibold text-foreground mb-4">
          {t('monitoring.trafficChart.title')}
        </h3>
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
    <div className="bg-card rounded-xl border p-6 transition-shadow duration-300">
      <h3 className="text-base font-semibold text-foreground mb-6">
        {t('monitoring.trafficChart.title')}
      </h3>
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
            <Legend
              wrapperStyle={{
                fontSize: '13px',
                paddingTop: '16px',
                fontWeight: 500,
              }}
              iconType="circle"
              iconSize={10}
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
