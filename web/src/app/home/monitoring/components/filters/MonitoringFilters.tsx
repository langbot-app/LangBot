import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { backendClient } from '@/app/infra/http';
import { TimeRangeOption } from '../../types/monitoring';
import type {
  ExecutionModeFilter,
  ExecutionSourceFilter,
} from '@/app/infra/entities/api/monitoring-executions';

interface MonitoringFiltersProps {
  selectedBots: string[];
  selectedPipelines: string[];
  timeRange: TimeRangeOption;
  onBotsChange: (bots: string[]) => void;
  onPipelinesChange: (pipelines: string[]) => void;
  onTimeRangeChange: (timeRange: TimeRangeOption) => void;
  source?: ExecutionSourceFilter;
  onSourceChange?: (value: ExecutionSourceFilter) => void;
  mode?: ExecutionModeFilter;
  onModeChange?: (value: ExecutionModeFilter) => void;
  statusGroup?: string;
  onStatusGroupChange?: (value: string) => void;
}

const STATUS_GROUP_OPTIONS = [
  'completed',
  'failed',
  'running',
  'queued',
  'cancelled',
  'ignored',
];

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
  source,
  onSourceChange,
  mode,
  onModeChange,
  statusGroup,
  onStatusGroupChange,
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
    <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:flex-wrap sm:items-center sm:gap-6">
      {/* Source Filter */}
      {onSourceChange && (
        <div className="flex items-center gap-2">
          <Label className="w-20 shrink-0 text-sm font-medium sm:w-auto sm:whitespace-nowrap">
            {t('monitoring.execution.filters.source')}
          </Label>
          <Select
            value={source ?? 'all'}
            onValueChange={(value) =>
              onSourceChange(value as ExecutionSourceFilter)
            }
          >
            <SelectTrigger className="h-9 w-full sm:w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t('monitoring.execution.filters.sourceAll')}
              </SelectItem>
              <SelectItem value="agent">
                {t('monitoring.execution.filters.sourceAgent')}
              </SelectItem>
              <SelectItem value="pipeline">
                {t('monitoring.execution.filters.sourcePipeline')}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Mode Filter */}
      {onModeChange && (
        <div className="flex items-center gap-2">
          <Label className="w-20 shrink-0 text-sm font-medium sm:w-auto sm:whitespace-nowrap">
            {t('monitoring.execution.filters.mode')}
          </Label>
          <Select
            value={mode ?? 'all'}
            onValueChange={(value) =>
              onModeChange(value as ExecutionModeFilter)
            }
          >
            <SelectTrigger className="h-9 w-full sm:w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t('monitoring.execution.filters.modeAll')}
              </SelectItem>
              <SelectItem value="real">
                {t('monitoring.execution.filters.modeLive')}
              </SelectItem>
              <SelectItem value="debug">
                {t('monitoring.execution.filters.modeDebug')}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Status Filter */}
      {onStatusGroupChange && (
        <div className="flex items-center gap-2">
          <Label className="w-20 shrink-0 text-sm font-medium sm:w-auto sm:whitespace-nowrap">
            {t('monitoring.execution.filters.status')}
          </Label>
          <Select
            value={statusGroup ?? 'all'}
            onValueChange={(value) => onStatusGroupChange(value)}
          >
            <SelectTrigger className="h-9 w-full sm:w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t('monitoring.execution.filters.statusAll')}
              </SelectItem>
              {STATUS_GROUP_OPTIONS.map((group) => (
                <SelectItem key={group} value={group}>
                  {t(`monitoring.execution.status.${group}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Bot Filter */}
      <div className="flex items-center gap-2">
        <Label className="w-20 shrink-0 text-sm font-medium sm:w-auto sm:whitespace-nowrap">
          {t('monitoring.filters.bot')}
        </Label>
        <Select
          value={selectedBots.length === 0 ? 'all' : selectedBots[0]}
          onValueChange={handleBotChange}
          disabled={loadingBots}
        >
          <SelectTrigger className="h-9 w-full sm:w-[140px]">
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
        <Label className="w-20 shrink-0 text-sm font-medium sm:w-auto sm:whitespace-nowrap">
          {t('monitoring.filters.pipeline')}
        </Label>
        <Select
          value={selectedPipelines.length === 0 ? 'all' : selectedPipelines[0]}
          onValueChange={handlePipelineChange}
          disabled={loadingPipelines}
        >
          <SelectTrigger className="h-9 w-full sm:w-[140px]">
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
        <Label className="w-20 shrink-0 text-sm font-medium sm:w-auto sm:whitespace-nowrap">
          {t('monitoring.filters.timeRange')}
        </Label>
        <Select value={timeRange} onValueChange={handleTimeRangeChange}>
          <SelectTrigger className="h-9 w-full sm:w-[150px]">
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
