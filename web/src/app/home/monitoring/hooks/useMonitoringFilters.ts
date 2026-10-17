import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useCurrentWorkspace } from '@/app/infra/http';
import { FilterState, TimeRangeOption, DateRange } from '../types/monitoring';
import { getPresetDateRange } from '../utils/dateUtils';
import type { ExecutionModeFilter } from '@/app/infra/entities/api/monitoring-executions';

const defaults = (): FilterState => ({
  selectedBots: [],
  selectedPipelines: [],
  timeRange: 'last24Hours',
  customDateRange: null,
  mode: 'all',
  statusGroup: 'all',
});
const timeRanges = [
  'lastHour',
  'last6Hours',
  'last24Hours',
  'last7Days',
  'last30Days',
  'last90Days',
  'last180Days',
  'last365Days',
  'custom',
];
const statuses = [
  'all',
  'completed',
  'failed',
  'running',
  'queued',
  'cancelled',
  'ignored',
];

function restore(key: string): FilterState {
  const state = defaults();
  try {
    const saved = JSON.parse(localStorage.getItem(key) || 'null');
    if (!saved || typeof saved !== 'object') return state;
    for (const name of ['selectedBots', 'selectedPipelines'] as const) {
      if (Array.isArray(saved[name]))
        state[name] = saved[name].filter(
          (id: unknown) => typeof id === 'string' && id.length > 0,
        );
    }
    if (timeRanges.includes(saved.timeRange)) state.timeRange = saved.timeRange;
    if (['all', 'real', 'debug'].includes(saved.mode)) state.mode = saved.mode;
    if (statuses.includes(saved.statusGroup))
      state.statusGroup = saved.statusGroup;
    if (saved.customDateRange) {
      const from = new Date(saved.customDateRange.from);
      const to = new Date(saved.customDateRange.to);
      if (
        Number.isFinite(from.getTime()) &&
        Number.isFinite(to.getTime()) &&
        from < to &&
        to.getTime() - from.getTime() <= 365 * 86400000
      )
        state.customDateRange = { from, to };
    }
    if (state.timeRange === 'custom' && !state.customDateRange)
      state.timeRange = 'last24Hours';
  } catch {
    // Invalid or unavailable browser storage must not prevent monitoring.
  }
  return state;
}

/** The page is keyed by Workspace so saved resource IDs never cross scopes. */
export function useMonitoringFilters() {
  const workspace = useCurrentWorkspace()?.workspace.uuid;
  const key = `monitoring.filters.v1:${workspace ?? 'pending'}`;
  const [searchParams, setSearchParams] = useSearchParams();
  const [filterState, setFilters] = useState<FilterState>(() => {
    const state = workspace ? restore(key) : defaults();
    // Explicit links take precedence over saved resource filters.
    if (searchParams.has('botId'))
      state.selectedBots = searchParams.getAll('botId').filter(Boolean);
    if (searchParams.has('pipelineId'))
      state.selectedPipelines = searchParams
        .getAll('pipelineId')
        .filter(Boolean);
    return state;
  });
  useEffect(() => {
    if (!workspace) return;
    try {
      localStorage.setItem(key, JSON.stringify(filterState));
    } catch {
      /* Storage may be disabled. */
    }
  }, [key, workspace, filterState]);
  const update = (value: Partial<FilterState>) =>
    setFilters((current) => ({ ...current, ...value }));
  const clearLinkedFilter = (name: string) => {
    if (!searchParams.has(name)) return;
    const next = new URLSearchParams(searchParams);
    next.delete(name);
    setSearchParams(next, { replace: true });
  };
  const resetFilters = () => {
    setFilters(defaults());
    const next = new URLSearchParams(searchParams);
    next.delete('botId');
    next.delete('pipelineId');
    setSearchParams(next, { replace: true });
  };
  return {
    ...filterState,
    filterState,
    setSelectedBots: (selectedBots: string[]) => {
      update({ selectedBots });
      clearLinkedFilter('botId');
    },
    setSelectedPipelines: (selectedPipelines: string[]) => {
      update({ selectedPipelines });
      clearLinkedFilter('pipelineId');
    },
    setTimeRange: (timeRange: TimeRangeOption) => update({ timeRange }),
    setCustomDateRange: (customDateRange: DateRange | null) =>
      update({ customDateRange }),
    setExecutionMode: (mode: ExecutionModeFilter) => update({ mode }),
    setExecutionStatus: (statusGroup: string) => update({ statusGroup }),
    getActiveDateRange: () =>
      filterState.timeRange === 'custom'
        ? filterState.customDateRange
        : getPresetDateRange(filterState.timeRange),
    resetFilters,
  };
}
