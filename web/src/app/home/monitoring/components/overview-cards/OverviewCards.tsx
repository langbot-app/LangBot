'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';
import MetricCard from './MetricCard';
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
}

export default function OverviewCards({
  metrics,
  messages = [],
  llmCalls = [],
  loading,
}: OverviewCardsProps) {
  const { t } = useTranslation();

  const cards = [
    {
      title: t('monitoring.totalMessages'),
      value: metrics?.totalMessages || 0,
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M6.45455 19L2 22.5V4C2 3.44772 2.44772 3 3 3H21C21.5523 3 22 3.44772 22 4V18C22 18.5523 21.5523 19 21 19H6.45455ZM4 18.3851L5.76282 17H20V5H4V18.3851Z"></path>
        </svg>
      ),
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
      title: t('monitoring.llmCallsCount'),
      value: metrics?.llmCalls || 0,
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M10.6144 17.7956C10.277 18.5682 9.20776 18.5682 8.8704 17.7956L7.99275 15.7854C7.21171 13.9966 5.80589 12.5726 4.0523 11.7942L1.63658 10.7219C.868536 10.381.868537 9.26368 1.63658 8.92276L3.97685 7.88394C5.77553 7.08552 7.20657 5.60881 7.97427 3.75892L8.8633 1.61673C9.19319.821767 10.2916.821765 10.6215 1.61673L11.5105 3.75894C12.2782 5.60881 13.7092 7.08552 15.5079 7.88394L17.8482 8.92276C18.6162 9.26368 18.6162 10.381 17.8482 10.7219L15.4325 11.7942C13.6789 12.5726 12.2731 13.9966 11.492 15.7854L10.6144 17.7956ZM19.4014 22.6899 19.6482 22.1242C20.0882 21.1156 20.8807 20.3125 21.8695 19.8732L22.6299 19.5353C23.0412 19.3526 23.0412 18.7549 22.6299 18.5722L21.9121 18.2532C20.8978 17.8026 20.0911 16.9698 19.6586 15.9269L19.4052 15.3156C19.2285 14.8896 18.6395 14.8896 18.4628 15.3156L18.2094 15.9269C17.777 16.9698 16.9703 17.8026 15.956 18.2532L15.2381 18.5722C14.8269 18.7549 14.8269 19.3526 15.2381 19.5353L15.9985 19.8732C16.9874 20.3125 17.7798 21.1156 18.2198 22.1242L18.4667 22.6899C18.6473 23.104 19.2207 23.104 19.4014 22.6899Z"></path>
        </svg>
      ),
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
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M10 15.172L19.192 5.979L20.607 7.393L10 18L3.636 11.636L5.05 10.222L10 15.172Z"></path>
        </svg>
      ),
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
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M2 22C2 17.5817 5.58172 14 10 14C14.4183 14 18 17.5817 18 22H16C16 18.6863 13.3137 16 10 16C6.68629 16 4 18.6863 4 22H2ZM10 13C6.685 13 4 10.315 4 7C4 3.685 6.685 1 10 1C13.315 1 16 3.685 16 7C16 10.315 13.315 13 10 13ZM10 11C12.21 11 14 9.21 14 7C14 4.79 12.21 3 10 3C7.79 3 6 4.79 6 7C6 9.21 7.79 11 10 11ZM18.2837 14.7028C21.0644 15.9561 23 18.7519 23 22H21C21 19.3742 19.4041 17.1096 17.1582 16.2466L18.2837 14.7028ZM17.5962 3.41321C19.5944 4.23703 21 6.20361 21 8.5C21 11.3702 18.8042 13.7252 16 13.9776V11.9646C17.6967 11.7222 19 10.264 19 8.5C19 7.11935 18.2016 5.92603 17.041 5.35635L17.5962 3.41321Z"></path>
        </svg>
      ),
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
      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
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
      </div>

      {/* Traffic Chart */}
      <TrafficChart messages={messages} llmCalls={llmCalls} loading={loading} />
    </div>
  );
}
