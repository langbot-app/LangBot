import { useState, useEffect, useCallback } from 'react';
import { FilterState, MonitoringData } from '../types/monitoring';
import { backendClient } from '@/app/infra/http';

/**
 * Custom hook for fetching and managing monitoring data
 */
export function useMonitoringData(filterState: FilterState) {
  const [data, setData] = useState<MonitoringData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Convert time range to datetime strings
  const getTimeRange = () => {
    const now = new Date();
    let startTime: Date | null = null;

    switch (filterState.timeRange) {
      case 'lastHour':
        startTime = new Date(now.getTime() - 60 * 60 * 1000);
        break;
      case 'last6Hours':
        startTime = new Date(now.getTime() - 6 * 60 * 60 * 1000);
        break;
      case 'last24Hours':
        startTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        break;
      case 'last7Days':
        startTime = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case 'last30Days':
        startTime = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        break;
      case 'custom':
        if (filterState.customDateRange) {
          startTime = filterState.customDateRange.from;
        }
        break;
    }

    const endTime =
      filterState.timeRange === 'custom' && filterState.customDateRange
        ? filterState.customDateRange.to
        : now;

    return {
      startTime: startTime?.toISOString(),
      endTime: endTime.toISOString(),
    };
  };

  // Fetch data based on filters
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const { startTime, endTime } = getTimeRange();

      const response = await backendClient.getMonitoringData({
        botId: filterState.selectedBots.length > 0 ? filterState.selectedBots : undefined,
        pipelineId: filterState.selectedPipelines.length > 0 ? filterState.selectedPipelines : undefined,
        startTime,
        endTime,
        limit: 50,
      });

      // Transform the response to match MonitoringData interface
      const transformedData: MonitoringData = {
        overview: {
          totalMessages: response.overview.total_messages,
          llmCalls: response.overview.llm_calls,
          successRate: response.overview.success_rate,
          activeSessions: response.overview.active_sessions,
        },
        messages: response.messages.map((msg: any) => ({
          id: msg.id,
          timestamp: new Date(msg.timestamp),
          botId: msg.bot_id,
          botName: msg.bot_name,
          pipelineId: msg.pipeline_id,
          pipelineName: msg.pipeline_name,
          messageContent: msg.message_content,
          sessionId: msg.session_id,
          status: msg.status,
          level: msg.level,
          platform: msg.platform,
          userId: msg.user_id,
        })),
        llmCalls: response.llmCalls.map((call: any) => ({
          id: call.id,
          timestamp: new Date(call.timestamp),
          modelName: call.model_name,
          tokens: {
            input: call.input_tokens,
            output: call.output_tokens,
            total: call.total_tokens,
          },
          duration: call.duration,
          cost: call.cost,
          status: call.status,
          botId: call.bot_id,
          botName: call.bot_name,
          pipelineId: call.pipeline_id,
          pipelineName: call.pipeline_name,
          errorMessage: call.error_message,
        })),
        sessions: response.sessions.map((session: any) => ({
          sessionId: session.session_id,
          botId: session.bot_id,
          botName: session.bot_name,
          pipelineId: session.pipeline_id,
          pipelineName: session.pipeline_name,
          messageCount: session.message_count,
          duration: new Date(session.last_activity).getTime() - new Date(session.start_time).getTime(),
          lastActivity: new Date(session.last_activity),
          startTime: new Date(session.start_time),
          platform: session.platform,
          userId: session.user_id,
        })),
        errors: response.errors.map((error: any) => ({
          id: error.id,
          timestamp: new Date(error.timestamp),
          errorType: error.error_type,
          errorMessage: error.error_message,
          botId: error.bot_id,
          botName: error.bot_name,
          pipelineId: error.pipeline_id,
          pipelineName: error.pipeline_name,
          sessionId: error.session_id,
          stackTrace: error.stack_trace,
        })),
        totalCount: {
          messages: response.totalCount.messages,
          llmCalls: response.totalCount.llmCalls,
          sessions: response.totalCount.sessions,
          errors: response.totalCount.errors,
        },
      };

      setData(transformedData);
    } catch (err) {
      setError(err as Error);
      console.error('Failed to fetch monitoring data:', err);
    } finally {
      setLoading(false);
    }
  }, [filterState]);

  // Fetch data when filter state changes
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Manual refetch function
  const refetch = () => {
    fetchData();
  };

  return {
    data,
    loading,
    error,
    refetch,
  };
}
