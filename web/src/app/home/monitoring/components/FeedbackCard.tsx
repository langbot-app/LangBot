import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  ThumbsUp,
  ThumbsDown,
  TrendingUp,
  TrendingDown,
  Minus,
  Heart,
  Smile,
} from 'lucide-react';
import { MetricCard } from './overview-cards/MetricCard';

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

// The variant only tints the icon tile; the card surface stays neutral so the
// feedback row matches the token-monitoring cards.
const variantAccents: Record<
  NonNullable<FeedbackCardProps['variant']>,
  string
> = {
  default: '#64748b',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
};

export function FeedbackCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  variant = 'default',
  loading = false,
}: FeedbackCardProps) {
  const trendStyles = {
    up: 'text-green-500',
    down: 'text-destructive',
    neutral: 'text-muted-foreground',
  };

  return (
    <MetricCard
      label={title}
      value={value}
      hint={subtitle}
      icon={icon}
      accent={variantAccents[variant]}
      loading={loading}
    >
      {trend && (
        <div
          className={`flex items-center text-sm ${trendStyles[trend.direction]}`}
        >
          {trend.direction === 'up' && <TrendingUp className="mr-1 h-4 w-4" />}
          {trend.direction === 'down' && (
            <TrendingDown className="mr-1 h-4 w-4" />
          )}
          {trend.direction === 'neutral' && <Minus className="mr-1 h-4 w-4" />}
          <span>
            {trend.value > 0 ? '+' : ''}
            {trend.value}%
          </span>
        </div>
      )}
    </MetricCard>
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
      icon: <Heart className="h-4 w-4" />,
      variant: 'default' as const,
    },
    {
      title: t('monitoring.feedback.totalLikes'),
      value: stats?.totalLikes ?? 0,
      icon: <ThumbsUp className="h-4 w-4" />,
      variant: 'success' as const,
    },
    {
      title: t('monitoring.feedback.totalDislikes'),
      value: stats?.totalDislikes ?? 0,
      icon: <ThumbsDown className="h-4 w-4" />,
      variant: 'danger' as const,
    },
    {
      title: t('monitoring.feedback.satisfactionRate'),
      value: stats ? `${stats.satisfactionRate}%` : '0%',
      icon: <Smile className="h-4 w-4" />,
      // The rate is the one feedback metric that is good or bad on its own, so
      // its tile keeps encoding the verdict (as it did before the restyle).
      variant: (stats && stats.satisfactionRate >= 80
        ? 'success'
        : stats && stats.satisfactionRate >= 50
          ? 'warning'
          : 'danger') as 'success' | 'warning' | 'danger',
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
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
