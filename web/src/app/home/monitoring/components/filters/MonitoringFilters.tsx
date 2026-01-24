'use client';

import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { backendClient } from '@/app/infra/http';
import { TimeRangeOption } from '../../types/monitoring';

interface MonitoringFiltersProps {
  selectedBots: string[];
  selectedPipelines: string[];
  timeRange: TimeRangeOption;
  onBotsChange: (bots: string[]) => void;
  onPipelinesChange: (pipelines: string[]) => void;
  onTimeRangeChange: (timeRange: TimeRangeOption) => void;
}

interface Bot {
  uuid: string;
  name: string;
}

interface Pipeline {
  uuid: string;
  name: string;
}

export default function MonitoringFilters({
  selectedBots,
  selectedPipelines,
  timeRange,
  onBotsChange,
  onPipelinesChange,
  onTimeRangeChange,
}: MonitoringFiltersProps) {
  const { t } = useTranslation();
  const [bots, setBots] = useState<Bot[]>([]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loadingBots, setLoadingBots] = useState(false);
  const [loadingPipelines, setLoadingPipelines] = useState(false);

  // Fetch bots list
  useEffect(() => {
    const fetchBots = async () => {
      setLoadingBots(true);
      try {
        const response = await backendClient.getBots();
        // Filter out bots without uuid and map to local Bot interface
        const validBots = (response.bots || [])
          .filter((bot): bot is typeof bot & { uuid: string } => !!bot.uuid)
          .map((bot) => ({ uuid: bot.uuid, name: bot.name }));
        setBots(validBots);
      } catch (error) {
        console.error('Failed to fetch bots:', error);
      } finally {
        setLoadingBots(false);
      }
    };

    fetchBots();
  }, []);

  // Fetch pipelines list
  useEffect(() => {
    const fetchPipelines = async () => {
      setLoadingPipelines(true);
      try {
        const response = await backendClient.getPipelines();
        // Filter out pipelines without uuid and map to local Pipeline interface
        const validPipelines = (response.pipelines || [])
          .filter(
            (pipeline): pipeline is typeof pipeline & { uuid: string } =>
              !!pipeline.uuid,
          )
          .map((pipeline) => ({ uuid: pipeline.uuid, name: pipeline.name }));
        setPipelines(validPipelines);
      } catch (error) {
        console.error('Failed to fetch pipelines:', error);
      } finally {
        setLoadingPipelines(false);
      }
    };

    fetchPipelines();
  }, []);

  const handleBotChange = (value: string) => {
    if (value === 'all') {
      onBotsChange([]);
    } else {
      onBotsChange([value]);
    }
  };

  const handlePipelineChange = (value: string) => {
    if (value === 'all') {
      onPipelinesChange([]);
    } else {
      onPipelinesChange([value]);
    }
  };

  const handleTimeRangeChange = (value: string) => {
    onTimeRangeChange(value as TimeRangeOption);
  };

  return (
    <div className="flex flex-wrap items-center gap-6">
      {/* Bot Filter */}
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
          {t('monitoring.filters.bot')}
        </label>
        <Select
          value={selectedBots.length === 0 ? 'all' : selectedBots[0]}
          onValueChange={handleBotChange}
          disabled={loadingBots}
        >
          <SelectTrigger className="bg-white dark:bg-[#2a2a2e] h-9 w-[140px]">
            <SelectValue
              placeholder={
                loadingBots
                  ? t('monitoring.filters.loading')
                  : t('monitoring.filters.selectBot')
              }
            />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">
              {t('monitoring.filters.allBots')}
            </SelectItem>
            {bots.map((bot) => (
              <SelectItem key={bot.uuid} value={bot.uuid}>
                {bot.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Pipeline Filter */}
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
          {t('monitoring.filters.pipeline')}
        </label>
        <Select
          value={selectedPipelines.length === 0 ? 'all' : selectedPipelines[0]}
          onValueChange={handlePipelineChange}
          disabled={loadingPipelines}
        >
          <SelectTrigger className="bg-white dark:bg-[#2a2a2e] h-9 w-[140px]">
            <SelectValue
              placeholder={
                loadingPipelines
                  ? t('monitoring.filters.loading')
                  : t('monitoring.filters.selectPipeline')
              }
            />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">
              {t('monitoring.filters.allPipelines')}
            </SelectItem>
            {pipelines.map((pipeline) => (
              <SelectItem key={pipeline.uuid} value={pipeline.uuid}>
                {pipeline.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Time Range Filter */}
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
          {t('monitoring.filters.timeRange')}
        </label>
        <Select value={timeRange} onValueChange={handleTimeRangeChange}>
          <SelectTrigger className="bg-white dark:bg-[#2a2a2e] h-9 w-[150px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="lastHour">
              {t('monitoring.filters.lastHour')}
            </SelectItem>
            <SelectItem value="last6Hours">
              {t('monitoring.filters.last6Hours')}
            </SelectItem>
            <SelectItem value="last24Hours">
              {t('monitoring.filters.last24Hours')}
            </SelectItem>
            <SelectItem value="last7Days">
              {t('monitoring.filters.last7Days')}
            </SelectItem>
            <SelectItem value="last30Days">
              {t('monitoring.filters.last30Days')}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
