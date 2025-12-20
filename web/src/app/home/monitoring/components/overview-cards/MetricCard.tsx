'use client';

import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: {
    value: number;
    direction: 'up' | 'down';
  };
  loading?: boolean;
}

export default function MetricCard({
  title,
  value,
  icon,
  trend,
  loading,
}: MetricCardProps) {
  if (loading) {
    return (
      <Card className="bg-white dark:bg-[#2a2a2e]">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
          <div className="h-4 w-4 text-gray-500 dark:text-gray-400">{icon}</div>
        </CardHeader>
        <CardContent>
          <div className="h-8 w-24 bg-gray-200 dark:bg-gray-700 animate-pulse rounded"></div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-white dark:bg-[#2a2a2e]">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-gray-700 dark:text-gray-200">
          {title}
        </CardTitle>
        <div className="h-4 w-4 text-gray-500 dark:text-gray-400">{icon}</div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold text-gray-900 dark:text-white">
          {value}
        </div>
        {trend && (
          <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
            <span
              className={
                trend.direction === 'up' ? 'text-green-600' : 'text-red-600'
              }
            >
              {trend.direction === 'up' ? '↑' : '↓'} {Math.abs(trend.value)}%
            </span>
          </p>
        )}
      </CardContent>
    </Card>
  );
}
