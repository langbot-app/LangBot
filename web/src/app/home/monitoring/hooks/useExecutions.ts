import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { TimeRangeOption, DateRange } from '../types/monitoring';
import { backendClient, useCurrentWorkspace } from '@/app/infra/http';
import { getCurrentWorkspaceSnapshot } from '@/app/infra/http/currentWorkspaceStore';
import { resolveMonitoringWindow } from '../utils/dateUtils';
import type {
  ExecutionListResult,
  ExecutionModeFilter,
  ExecutionSourceFilter,
} from '@/app/infra/entities/api/monitoring-executions';

/**
 * Custom hook for fetching the unified execution list
 */
export function useExecutions(params: {
  selectedBots: string[];
  selectedPipelines: string[];
  selectedAgents: string[];
  source: ExecutionSourceFilter;
  mode: ExecutionModeFilter;
  statusGroup: string;
  timeRange: TimeRangeOption;
  customDateRange: DateRange | null;
  limit: number;
  offset: number;
  refreshKey?: number;
}) {
  const [result, setResult] = useState<ExecutionListResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [nonce, setNonce] = useState(0);
  const workspaceUuid = useCurrentWorkspace()?.workspace.uuid;
  const requestIdRef = useRef(0);
  const scope = JSON.stringify([
    workspaceUuid,
    { ...params, refreshKey: undefined },
  ]);
  const [requestScope, setRequestScope] = useState<string | null>(null);

  // Memoize filter parameters to prevent unnecessary re-renders
  const selectedBotsStr = useMemo(
    () => JSON.stringify(params.selectedBots),
    [params.selectedBots],
  );
  const selectedPipelinesStr = useMemo(
    () => JSON.stringify(params.selectedPipelines),
    [params.selectedPipelines],
  );
  const selectedAgentsStr = useMemo(
    () => JSON.stringify(params.selectedAgents),
    [params.selectedAgents],
  );
  const customDateRangeStr = useMemo(
    () => JSON.stringify(params.customDateRange),
    [params.customDateRange],
  );

  // Fetch data based on filters
  const fetchData = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    const isCurrent = () =>
      requestId === requestIdRef.current &&
      getCurrentWorkspaceSnapshot()?.workspace.uuid === workspaceUuid;
    setLoading(true);
    setError(null);

    try {
      const { startTime, endTime } = resolveMonitoringWindow(
        params.timeRange,
        params.customDateRange,
      );

      const response = await backendClient.getExecutions({
        botId: params.selectedBots.length > 0 ? params.selectedBots : undefined,
        pipelineId:
          params.selectedPipelines.length > 0
            ? params.selectedPipelines
            : undefined,
        agentId:
          params.selectedAgents.length > 0 ? params.selectedAgents : undefined,
        status: params.statusGroup === 'all' ? undefined : [params.statusGroup],
        source: params.source,
        mode: params.mode,
        startTime,
        endTime,
        limit: params.limit,
        offset: params.offset,
      });
      if (!isCurrent()) return;

      setResult(response);
      setRequestScope(scope);
    } catch (err) {
      if (!isCurrent()) return;
      setRequestScope(scope);
      setResult((current) => (requestScope === scope ? current : null));
      setError(err as Error);
      console.error('Failed to fetch executions:', err);
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [
    params.selectedBots,
    params.selectedPipelines,
    params.selectedAgents,
    params.source,
    params.mode,
    params.statusGroup,
    params.timeRange,
    params.customDateRange,
    params.limit,
    params.offset,
    scope,
    requestScope,
    workspaceUuid,
  ]);

  // Fetch data when filter state changes
  useEffect(() => {
    fetchData();
    return () => {
      requestIdRef.current += 1;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    selectedBotsStr,
    selectedPipelinesStr,
    selectedAgentsStr,
    params.source,
    params.mode,
    params.statusGroup,
    params.timeRange,
    customDateRangeStr,
    params.limit,
    params.offset,
    params.refreshKey,
    nonce,
    workspaceUuid,
  ]);

  // Manual refetch function
  const refetch = () => {
    setNonce((value) => value + 1);
  };

  return {
    result: requestScope === scope ? result : null,
    loading: requestScope !== scope || loading,
    error: requestScope === scope ? error : null,
    refetch,
  };
}
