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
import { backendClient, useCurrentWorkspace } from '@/app/infra/http';
import { TimeRangeOption } from '../../types/monitoring';
import type { ExecutionModeFilter } from '@/app/infra/entities/api/monitoring-executions';

interface MonitoringFiltersProps {
  selectedBots: string[];
  selectedPipelines: string[];
  timeRange: TimeRangeOption;
  onBotsChange: (bots: string[]) => void;
  onPipelinesChange: (pipelines: string[]) => void;
  onTimeRangeChange: (timeRange: TimeRangeOption) => void;
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

const STATUS_COLORS: Record<string, string> = {
  completed: 'text-emerald-700 dark:text-emerald-400',
  failed: 'text-red-600 dark:text-red-400',
  running: 'text-blue-600 dark:text-blue-400',
  queued: 'text-amber-700 dark:text-amber-400',
  cancelled: 'text-slate-600 dark:text-slate-400',
  ignored: 'text-muted-foreground',
};

interface Bot {
  uuid: string;
  name: string;
  iconURL: string;
}

interface Processor {
  uuid: string;
  name: string;
  emoji?: string;
}

export default function MonitoringFilters({
  selectedBots,
  selectedPipelines,
  timeRange,
  onBotsChange,
  onPipelinesChange,
  onTimeRangeChange,
  mode,
  onModeChange,
  statusGroup,
  onStatusGroupChange,
}: MonitoringFiltersProps) {
  const { t } = useTranslation();
  const workspace = useCurrentWorkspace()?.workspace.uuid;
  const [bots, setBots] = useState<Bot[]>([]);
  const [processors, setProcessors] = useState<Processor[]>([]);
  const [loadingBots, setLoadingBots] = useState(false);
  const [loadingProcessors, setLoadingProcessors] = useState(false);

  // Fetch bots list
  useEffect(() => {
    let active = true;
    setBots([]);
    const fetchBots = async () => {
      setLoadingBots(true);
      try {
        const response = await backendClient.getBots();
        // Filter out bots without uuid and map to local Bot interface
        const validBots = (response.bots || [])
          .filter((bot): bot is typeof bot & { uuid: string } => !!bot.uuid)
          .map((bot) => ({
            uuid: bot.uuid,
            name: bot.name,
            iconURL: backendClient.getAdapterIconURL(bot.adapter),
          }));
        if (active) setBots(validBots);
      } catch (error) {
        console.error('Failed to fetch bots:', error);
      } finally {
        if (active) setLoadingBots(false);
      }
    };

    fetchBots();
    return () => {
      active = false;
    };
  }, [workspace]);

  // Fetch all processor kinds from the same catalog as the sidebar
  useEffect(() => {
    let active = true;
    setProcessors([]);
    const fetchProcessors = async () => {
      setLoadingProcessors(true);
      try {
        const response = await backendClient.getAgents();
        // Preserve the custom icon displayed to the left of the sidebar name.
        const validProcessors = (response.agents || [])
          .filter(
            (pipeline): pipeline is typeof pipeline & { uuid: string } =>
              !!pipeline.uuid,
          )
          .map((pipeline) => ({
            uuid: pipeline.uuid,
            name: pipeline.name,
            emoji: pipeline.emoji,
          }));
        if (active) setProcessors(validProcessors);
      } catch (error) {
        console.error('Failed to fetch processors:', error);
      } finally {
        if (active) setLoadingProcessors(false);
      }
    };

    fetchProcessors();
    return () => {
      active = false;
    };
  }, [workspace]);

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
    <div className="grid min-w-0 flex-1 grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {/* Bot Filter */}
      <div className="min-w-0 space-y-1.5">
        <Label
          htmlFor="monitoring-filter-bot"
          className="text-xs font-medium text-muted-foreground"
        >
          {t('monitoring.filters.bot')}
        </Label>
        <Select
          value={selectedBots.length === 0 ? 'all' : selectedBots[0]}
          onValueChange={handleBotChange}
          disabled={loadingBots}
        >
          <SelectTrigger
            id="monitoring-filter-bot"
            className="h-9 w-full min-w-0"
          >
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
                <span className="flex min-w-0 items-center gap-2">
                  <img
                    src={bot.iconURL}
                    alt=""
                    className="size-4 shrink-0 rounded"
                  />
                  <span className="truncate">{bot.name}</span>
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Processor Filter */}
      <div className="min-w-0 space-y-1.5">
        <Label
          htmlFor="monitoring-filter-processor"
          className="text-xs font-medium text-muted-foreground"
        >
          {t('monitoring.filters.processor')}
        </Label>
        <Select
          value={selectedPipelines.length === 0 ? 'all' : selectedPipelines[0]}
          onValueChange={handlePipelineChange}
          disabled={loadingProcessors}
        >
          <SelectTrigger
            id="monitoring-filter-processor"
            className="h-9 w-full min-w-0"
          >
            <SelectValue
              placeholder={
                loadingProcessors
                  ? t('monitoring.filters.loading')
                  : t('monitoring.filters.selectProcessor')
              }
            />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">
              {t('monitoring.filters.allProcessors')}
            </SelectItem>
            {processors.map((pipeline) => (
              <SelectItem key={pipeline.uuid} value={pipeline.uuid}>
                <span className="flex min-w-0 items-center gap-2">
                  {pipeline.emoji && (
                    <span className="shrink-0 text-sm" aria-hidden="true">
                      {pipeline.emoji}
                    </span>
                  )}
                  <span className="truncate">{pipeline.name}</span>
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Mode Filter */}
      {onModeChange && (
        <div className="min-w-0 space-y-1.5">
          <Label
            htmlFor="monitoring-filter-mode"
            className="text-xs font-medium text-muted-foreground"
          >
            {t('monitoring.execution.filters.mode')}
          </Label>
          <Select
            value={mode ?? 'all'}
            onValueChange={(value) =>
              onModeChange(value as ExecutionModeFilter)
            }
          >
            <SelectTrigger
              id="monitoring-filter-mode"
              className="h-9 w-full min-w-0"
            >
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
        <div className="min-w-0 space-y-1.5">
          <Label
            htmlFor="monitoring-filter-status"
            className="text-xs font-medium text-muted-foreground"
          >
            {t('monitoring.execution.filters.status')}
          </Label>
          <Select
            value={statusGroup ?? 'all'}
            onValueChange={(value) => onStatusGroupChange(value)}
          >
            <SelectTrigger
              id="monitoring-filter-status"
              className="h-9 w-full min-w-0"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t('monitoring.execution.filters.statusAll')}
              </SelectItem>
              {STATUS_GROUP_OPTIONS.map((group) => (
                <SelectItem key={group} value={group}>
                  <span
                    className={`flex items-center gap-2 ${STATUS_COLORS[group]}`}
                  >
                    <span
                      aria-hidden="true"
                      className="size-2 shrink-0 rounded-full bg-current"
                    />
                    {t(`monitoring.execution.status.${group}`)}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Time Range Filter */}
      <div className="min-w-0 space-y-1.5">
        <Label
          htmlFor="monitoring-filter-time"
          className="text-xs font-medium text-muted-foreground"
        >
          {t('monitoring.filters.timeRange')}
        </Label>
        <Select value={timeRange} onValueChange={handleTimeRangeChange}>
          <SelectTrigger
            id="monitoring-filter-time"
            className="h-9 w-full min-w-0"
          >
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
