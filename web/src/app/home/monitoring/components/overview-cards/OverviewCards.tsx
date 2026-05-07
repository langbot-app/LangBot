import React from 'react';
import { useTranslation } from 'react-i18next';
import { MessageSquare, Sparkles, Check, Users } from 'lucide-react';
import MetricCard from './MetricCard';
import SystemStatusCard from './SystemStatusCards';
import TrafficChart from './TrafficChart';
import {
  OverviewMetrics,
  MonitoringMessage,
  LLMCall,
} from '../../types/monitoring';

interface OverviewCardsProps {
  metrics: OverviewMetrics | null;
  messages?: MonitoringMessage[];
  llmCalls?: LLMCall[];
  loading?: boolean;
  refreshKey?: number;
}

export default function OverviewCards({
  metrics,
  messages = [],
  llmCalls = [],
  loading,
  refreshKey,
}: OverviewCardsProps) {
  const { t } = useTranslation();

  const cards = [
    {
      title: t('monitoring.totalMessages'),
      value: metrics?.totalMessages || 0,
      icon: <MessageSquare />,
      trend: metrics?.trends
        ? {
            value: metrics.trends.messages,
            direction: (metrics.trends.messages >= 0 ? 'up' : 'down') as
              | 'up'
              | 'down',
          }
        : undefined,
    },
    {
      title: t('monitoring.modelCallsCount'),
      value: metrics?.modelCalls || 0,
      icon: <Sparkles />,
      trend: metrics?.trends
        ? {
            value: metrics.trends.llmCalls,
            direction: (metrics.trends.llmCalls >= 0 ? 'up' : 'down') as
              | 'up'
              | 'down',
          }
        : undefined,
    },
    {
      title: t('monitoring.successRate'),
      value: metrics ? `${metrics.successRate}%` : '0%',
      icon: <Check />,
      trend: metrics?.trends
        ? {
            value: metrics.trends.successRate,
            direction: (metrics.trends.successRate >= 0 ? 'up' : 'down') as
              | 'up'
              | 'down',
          }
        : undefined,
    },
    {
      title: t('monitoring.activeSessions'),
      value: metrics?.activeSessions || 0,
      icon: <Users />,
      trend: metrics?.trends
        ? {
            value: metrics.trends.sessions,
            direction: (metrics.trends.sessions >= 0 ? 'up' : 'down') as
              | 'up'
              | 'down',
          }
        : undefined,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Metric Cards + System Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-6">
        {cards.map((card, index) => (
          <MetricCard
            key={index}
            title={card.title}
            value={card.value}
            icon={card.icon}
            trend={card.trend}
            loading={loading}
          />
        ))}
        <SystemStatusCard refreshKey={refreshKey} />
      </div>

      {/* Traffic Chart */}
      <TrafficChart messages={messages} llmCalls={llmCalls} loading={loading} />
    </div>
  );
}
