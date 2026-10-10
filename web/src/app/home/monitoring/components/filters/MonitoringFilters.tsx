import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ChevronDown } from 'lucide-react';
import { DateRange } from '../../types/monitoring';
import { Label } from '@/components/ui/label';
import { backendClient, useCurrentWorkspace } from '@/app/infra/http';
import { TimeRangeOption } from '../../types/monitoring';
import type { ExecutionModeFilter } from '@/app/infra/entities/api/monitoring-executions';

interface MonitoringFiltersProps {
  selectedBots: string[];
  selectedPipelines: string[];
  timeRange: TimeRangeOption;
  customDateRange?: DateRange | null;
  onCustomDateRangeChange?: (range: DateRange) => void;
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
  kind: string;
}

export default function MonitoringFilters({
  selectedBots,
  selectedPipelines,
  timeRange,
  customDateRange,
  onCustomDateRangeChange,
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
            kind: pipeline.kind,
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

  const customPending = useRef(false);
  const [dateOpen, setDateOpen] = useState(false);
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const localDate = (date: Date) =>
    new Date(date.getTime() - date.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
  const openCustom = () => {
    setFromDate(
      localDate(customDateRange?.from ?? new Date(Date.now() - 86400000)),
    );
    setToDate(localDate(customDateRange?.to ?? new Date()));
    setDateOpen(true);
  };
  const from = new Date(fromDate);
  const to = new Date(toDate);
  const validDates =
    Number.isFinite(from.getTime()) &&
    Number.isFinite(to.getTime()) &&
    from < to &&
    to.getTime() - from.getTime() <= 365 * 86400000 &&
    to.getTime() <= Date.now();
  const handleTimeRangeChange = (value: string) => {
    if (value === 'custom') customPending.current = true;
    else onTimeRangeChange(value as TimeRangeOption);
  };
  const toggleProcessors = (ids: string[], checked: boolean) => {
    const next = new Set(selectedPipelines);
    ids.forEach((id) => (checked ? next.add(id) : next.delete(id)));
    onPipelinesChange([...next]);
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
        <Popover>
          <PopoverTrigger asChild>
            <Button
              id="monitoring-filter-processor"
              variant="outline"
              disabled={loadingProcessors}
              className="h-9 w-full justify-between font-normal"
            >
              <span className="truncate">
                {selectedPipelines.length
                  ? t('agents.apiToolsSelected', {
                      count: selectedPipelines.length,
                    })
                  : t('monitoring.filters.allProcessors')}
              </span>
              <ChevronDown className="ml-2 size-4 shrink-0 text-muted-foreground" />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            align="start"
            className="max-h-96 w-72 overflow-y-auto p-2"
          >
            <Button
              variant="ghost"
              size="sm"
              className="mb-1 w-full justify-start"
              onClick={() => onPipelinesChange([])}
            >
              {t('monitoring.filters.allProcessors')}
            </Button>
            {['pipeline', 'agent', 'event_processor'].map((kind) => {
              const group = processors.filter((item) => item.kind === kind);
              if (!group.length) return null;
              const selected = group.filter((item) =>
                selectedPipelines.includes(item.uuid),
              ).length;
              return (
                <div key={kind} className="border-t py-2">
                  <label className="mb-1 flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted">
                    <Checkbox
                      checked={
                        selected === group.length
                          ? true
                          : selected
                            ? 'indeterminate'
                            : false
                      }
                      onCheckedChange={(checked) =>
                        toggleProcessors(
                          group.map((item) => item.uuid),
                          checked === true,
                        )
                      }
                    />
                    <span className="flex-1">
                      {t(
                        `monitoring.execution.kind.${kind === 'event_processor' ? 'processor' : kind}`,
                      )}
                    </span>
                    <span>{t('agents.apiToolsSelectAll')}</span>
                  </label>
                  {group.map((item) => (
                    <label
                      key={item.uuid}
                      className="flex cursor-pointer items-center gap-2 rounded px-2 py-2 text-sm hover:bg-muted"
                    >
                      <Checkbox
                        checked={selectedPipelines.includes(item.uuid)}
                        onCheckedChange={(checked) =>
                          toggleProcessors([item.uuid], checked === true)
                        }
                      />
                      <span aria-hidden="true">{item.emoji}</span>
                      <span className="truncate">{item.name}</span>
                    </label>
                  ))}
                </div>
              );
            })}
          </PopoverContent>
        </Popover>
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
        <Select
          value={timeRange === 'custom' ? '' : timeRange}
          onValueChange={handleTimeRangeChange}
        >
          <SelectTrigger
            id="monitoring-filter-time"
            className="h-9 w-full min-w-0 gap-2 [&>svg]:shrink-0"
            title={
              timeRange === 'custom' && customDateRange
                ? `${customDateRange.from.toLocaleString()} – ${customDateRange.to.toLocaleString()}`
                : undefined
            }
          >
            {timeRange === 'custom' && customDateRange ? (
              <span className="min-w-0 truncate text-xs tabular-nums">
                {customDateRange.from.toLocaleDateString(undefined, {
                  month: '2-digit',
                  day: '2-digit',
                })}
                {' – '}
                {customDateRange.to.toLocaleDateString(undefined, {
                  month: '2-digit',
                  day: '2-digit',
                })}
              </span>
            ) : (
              <SelectValue />
            )}
          </SelectTrigger>
          <SelectContent
            onCloseAutoFocus={(event) => {
              if (customPending.current) {
                event.preventDefault();
                customPending.current = false;
                openCustom();
              }
            }}
          >
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
            {[30, 90, 180, 365].map((days) => (
              <SelectItem key={days} value={`last${days}Days`}>
                {t('monitoring.rangeDays', { days })}
              </SelectItem>
            ))}
            {onCustomDateRangeChange && (
              <SelectItem value="custom">
                {t('monitoring.customRange')}
              </SelectItem>
            )}{' '}
          </SelectContent>
        </Select>{' '}
        {onCustomDateRangeChange && (
          <>
            <Dialog open={dateOpen} onOpenChange={setDateOpen}>
              <DialogContent className="sm:max-w-md space-y-3">
                <DialogHeader>
                  <DialogTitle>{t('monitoring.customRange')}</DialogTitle>
                  <DialogDescription>
                    {t('monitoring.rangeHint')}
                  </DialogDescription>
                </DialogHeader>
                <label className="block space-y-1 text-xs">
                  {t('monitoring.rangeStart')}
                  <Input
                    type="datetime-local"
                    value={fromDate}
                    max={toDate}
                    onChange={(event) => setFromDate(event.target.value)}
                  />
                </label>
                <label className="block space-y-1 text-xs">
                  {t('monitoring.rangeEnd')}
                  <Input
                    type="datetime-local"
                    value={toDate}
                    min={fromDate}
                    max={localDate(new Date())}
                    onChange={(event) => setToDate(event.target.value)}
                  />
                </label>

                <Button
                  size="sm"
                  className="w-full"
                  disabled={!validDates}
                  onClick={() => {
                    onCustomDateRangeChange({ from, to });
                    onTimeRangeChange('custom');
                    setDateOpen(false);
                  }}
                >
                  {t('common.confirm')}
                </Button>
              </DialogContent>
            </Dialog>
          </>
        )}
      </div>
    </div>
  );
}
