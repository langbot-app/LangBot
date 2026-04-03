import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  ThumbsUp,
  ThumbsDown,
  TrendingUp,
  TrendingDown,
  Minus,
} from 'lucide-react';

interface FeedbackCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  icon: React.ReactNode;
  trend?: {
    value: number;
    direction: 'up' | 'down' | 'neutral';
  };
  variant?: 'default' | 'success' | 'warning' | 'danger';
  loading?: boolean;
}

export function FeedbackCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  variant = 'default',
  loading = false,
}: FeedbackCardProps) {
  const variantStyles = {
    default: 'bg-white dark:bg-[#2a2a2e] border-gray-200 dark:border-gray-700',
    success:
      'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800',
    warning:
      'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800',
    danger: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800',
  };

  const iconStyles = {
    default: 'text-gray-500 dark:text-gray-400',
    success: 'text-green-500 dark:text-green-400',
    warning: 'text-yellow-500 dark:text-yellow-400',
    danger: 'text-red-500 dark:text-red-400',
  };

  const trendStyles = {
    up: 'text-green-500',
    down: 'text-red-500',
    neutral: 'text-gray-500',
  };

  if (loading) {
    return (
      <div
        className={`p-6 rounded-xl border shadow-sm ${variantStyles.default} animate-pulse`}
      >
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-20 mb-2" />
            <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-16 mb-1" />
            <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-24" />
          </div>
          <div className="w-10 h-10 bg-gray-200 dark:bg-gray-700 rounded-lg" />
        </div>
      </div>
    );
  }

  return (
    <div
      className={`p-6 rounded-xl border shadow-sm ${variantStyles[variant]}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
            {title}
          </p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {value}
          </p>
          {subtitle && (
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              {subtitle}
            </p>
          )}
          {trend && (
            <div
              className={`flex items-center mt-2 text-sm ${trendStyles[trend.direction]}`}
            >
              {trend.direction === 'up' && (
                <TrendingUp className="w-4 h-4 mr-1" />
              )}
              {trend.direction === 'down' && (
                <TrendingDown className="w-4 h-4 mr-1" />
              )}
              {trend.direction === 'neutral' && (
                <Minus className="w-4 h-4 mr-1" />
              )}
              <span>
                {trend.value > 0 ? '+' : ''}
                {trend.value}%
              </span>
            </div>
          )}
        </div>
        <div
          className={`p-3 rounded-lg bg-gray-100 dark:bg-gray-800 ${iconStyles[variant]}`}
        >
          {icon}
        </div>
      </div>
    </div>
  );
}

interface FeedbackStatsProps {
  stats: {
    totalFeedback: number;
    totalLikes: number;
    totalDislikes: number;
    satisfactionRate: number;
  } | null;
  loading?: boolean;
}

export function FeedbackStatsCards({ stats, loading }: FeedbackStatsProps) {
  const { t } = useTranslation();

  const cards = [
    {
      title: t('monitoring.feedback.totalFeedback'),
      value: stats?.totalFeedback ?? 0,
      icon: (
        <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
        </svg>
      ),
      variant: 'default' as const,
    },
    {
      title: t('monitoring.feedback.totalLikes'),
      value: stats?.totalLikes ?? 0,
      icon: <ThumbsUp className="w-6 h-6" />,
      variant: 'success' as const,
    },
    {
      title: t('monitoring.feedback.totalDislikes'),
      value: stats?.totalDislikes ?? 0,
      icon: <ThumbsDown className="w-6 h-6" />,
      variant: 'danger' as const,
    },
    {
      title: t('monitoring.feedback.satisfactionRate'),
      value: stats ? `${stats.satisfactionRate}%` : '0%',
      icon: (
        <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor">
          <path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z" />
        </svg>
      ),
      variant: (stats && stats.satisfactionRate >= 80
        ? 'success'
        : stats && stats.satisfactionRate >= 50
          ? 'warning'
          : 'danger') as 'default' | 'success' | 'warning' | 'danger',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
      {cards.map((card, index) => (
        <FeedbackCard
          key={index}
          title={card.title}
          value={card.value}
          icon={card.icon}
          variant={card.variant}
          loading={loading}
        />
      ))}
    </div>
  );
}
