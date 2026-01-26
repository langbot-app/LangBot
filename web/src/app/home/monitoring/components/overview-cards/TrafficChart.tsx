'use client';

import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
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
import { MonitoringMessage, LLMCall } from '../../types/monitoring';

interface TrafficChartProps {
  messages: MonitoringMessage[];
  llmCalls: LLMCall[];
  loading?: boolean;
}

interface ChartDataPoint {
  time: string;
  timestamp: number;
  messages: number;
  llmCalls: number;
}

export default function TrafficChart({
  messages,
  llmCalls,
  loading,
}: TrafficChartProps) {
  const { t } = useTranslation();

  const chartData = useMemo(() => {
    if (!messages.length && !llmCalls.length) {
      return [];
    }

    // Combine all timestamps and find the range
    const allTimestamps = [
      ...messages.map((m) => m.timestamp.getTime()),
      ...llmCalls.map((c) => c.timestamp.getTime()),
    ];

    if (allTimestamps.length === 0) return [];

    const minTime = Math.min(...allTimestamps);
    const maxTime = Math.max(...allTimestamps);
    const timeRange = maxTime - minTime;

    // Determine bucket size based on time range
    let bucketSize: number;
    let formatTime: (date: Date) => string;

    if (timeRange <= 60 * 60 * 1000) {
      // <= 1 hour: 5-minute buckets
      bucketSize = 5 * 60 * 1000;
      formatTime = (date) =>
        date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (timeRange <= 6 * 60 * 60 * 1000) {
      // <= 6 hours: 15-minute buckets
      bucketSize = 15 * 60 * 1000;
      formatTime = (date) =>
        date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (timeRange <= 24 * 60 * 60 * 1000) {
      // <= 24 hours: 1-hour buckets
      bucketSize = 60 * 60 * 1000;
      formatTime = (date) =>
        date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (timeRange <= 7 * 24 * 60 * 60 * 1000) {
      // <= 7 days: 4-hour buckets
      bucketSize = 4 * 60 * 60 * 1000;
      formatTime = (date) =>
        `${date.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${date.toLocaleTimeString([], { hour: '2-digit' })}`;
    } else {
      // > 7 days: 1-day buckets
      bucketSize = 24 * 60 * 60 * 1000;
      formatTime = (date) =>
        date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }

    // Create buckets
    const buckets: Map<number, ChartDataPoint> = new Map();
    const startBucket = Math.floor(minTime / bucketSize) * bucketSize;
    const endBucket = Math.ceil(maxTime / bucketSize) * bucketSize;

    for (let bucket = startBucket; bucket <= endBucket; bucket += bucketSize) {
      buckets.set(bucket, {
        time: formatTime(new Date(bucket)),
        timestamp: bucket,
        messages: 0,
        llmCalls: 0,
      });
    }

    // Count messages per bucket
    messages.forEach((msg) => {
      const bucket =
        Math.floor(msg.timestamp.getTime() / bucketSize) * bucketSize;
      const point = buckets.get(bucket);
      if (point) {
        point.messages++;
      }
    });

    // Count LLM calls per bucket
    llmCalls.forEach((call) => {
      const bucket =
        Math.floor(call.timestamp.getTime() / bucketSize) * bucketSize;
      const point = buckets.get(bucket);
      if (point) {
        point.llmCalls++;
      }
    });

    return Array.from(buckets.values()).sort(
      (a, b) => a.timestamp - b.timestamp,
    );
  }, [messages, llmCalls]);

  if (loading) {
    return (
      <div className="bg-white dark:bg-[#2a2a2e] rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="h-5 w-32 bg-gray-200 dark:bg-gray-700 animate-pulse rounded"></div>
          <div className="flex gap-4">
            <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 animate-pulse rounded"></div>
            <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 animate-pulse rounded"></div>
          </div>
        </div>
        <div className="h-[300px] flex items-center justify-center">
          <div className="animate-pulse w-full h-full bg-gray-100 dark:bg-gray-800 rounded"></div>
        </div>
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="bg-white dark:bg-[#2a2a2e] rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm p-6">
        <h3 className="text-base font-semibold text-gray-800 dark:text-gray-200 mb-4">
          {t('monitoring.trafficChart.title')}
        </h3>
        <div className="h-[300px] flex flex-col items-center justify-center text-gray-400 dark:text-gray-500">
          <svg
            className="w-16 h-16 mb-4 text-gray-300 dark:text-gray-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
          <p className="text-sm font-medium">{t('monitoring.trafficChart.noData')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-[#2a2a2e] rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm p-6 hover:shadow-md transition-shadow duration-300">
      <h3 className="text-base font-semibold text-gray-800 dark:text-gray-200 mb-6">
        {t('monitoring.trafficChart.title')}
      </h3>
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
              stroke="#e5e7eb"
              className="dark:stroke-gray-700"
              vertical={false}
            />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 12, fill: '#9ca3af' }}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
              dy={10}
            />
            <YAxis
              tick={{ fontSize: 12, fill: '#9ca3af' }}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
              width={40}
              allowDecimals={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(255, 255, 255, 0.98)',
                border: '1px solid #e5e7eb',
                borderRadius: '12px',
                boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
                fontSize: '13px',
                padding: '12px',
              }}
              labelStyle={{ fontWeight: 600, marginBottom: '8px', color: '#374151' }}
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
