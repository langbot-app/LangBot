import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  FilterState,
  MonitoringData,
  ModelCall,
  LLMCall,
  EmbeddingCall,
} from '../types/monitoring';
import { backendClient } from '@/app/infra/http';

/**
 * Custom hook for fetching and managing monitoring data
 */
export function useMonitoringData(filterState: FilterState) {
  const [data, setData] = useState<MonitoringData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Memoize filter parameters to prevent unnecessary re-renders
  const selectedBotsStr = useMemo(
    () => JSON.stringify(filterState.selectedBots),
    [filterState.selectedBots],
  );
  const selectedPipelinesStr = useMemo(
    () => JSON.stringify(filterState.selectedPipelines),
    [filterState.selectedPipelines],
  );
  const customDateRangeStr = useMemo(
    () => JSON.stringify(filterState.customDateRange),
    [filterState.customDateRange],
  );

  // Convert time range to datetime strings
  const getTimeRange = useCallback(() => {
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
  }, [filterState.timeRange, filterState.customDateRange]);

  // Fetch data based on filters
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const { startTime, endTime } = getTimeRange();

      const response = await backendClient.getMonitoringData({
        botId:
          filterState.selectedBots.length > 0
            ? filterState.selectedBots
            : undefined,
        pipelineId:
          filterState.selectedPipelines.length > 0
            ? filterState.selectedPipelines
            : undefined,
        startTime,
        endTime,
        limit: 50,
      });

      // Transform the response to match MonitoringData interface
      const transformedData: MonitoringData = {
        overview: {
          totalMessages: response.overview.total_messages,
          llmCalls: response.overview.llm_calls,
          embeddingCalls: response.overview.embedding_calls || 0,
          modelCalls:
            response.overview.model_calls || response.overview.llm_calls,
          successRate: response.overview.success_rate,
          activeSessions: response.overview.active_sessions,
        },
        messages: response.messages.map(
          (msg: {
            id: string;
            timestamp: string;
            bot_id: string;
            bot_name: string;
            pipeline_id: string;
            pipeline_name: string;
            message_content: string;
            session_id: string;
            status: string;
            level: string;
            platform?: string;
            user_id?: string;
            runner_name?: string;
            variables?: string;
          }) => ({
            id: msg.id,
            timestamp: new Date(msg.timestamp),
            botId: msg.bot_id,
            botName: msg.bot_name,
            pipelineId: msg.pipeline_id,
            pipelineName: msg.pipeline_name,
            messageContent: msg.message_content,
            sessionId: msg.session_id,
            status: msg.status as 'success' | 'error' | 'pending',
            level: msg.level as 'info' | 'warning' | 'error' | 'debug',
            platform: msg.platform,
            userId: msg.user_id,
            runnerName: msg.runner_name,
            variables: msg.variables,
          }),
        ),
        llmCalls: response.llmCalls.map(
          (call: {
            id: string;
            timestamp: string;
            model_name: string;
            input_tokens: number;
            output_tokens: number;
            total_tokens: number;
            duration: number;
            cost?: number;
            status: string;
            bot_id: string;
            bot_name: string;
            pipeline_id: string;
            pipeline_name: string;
            error_message?: string;
            message_id?: string;
          }) => ({
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
            status: call.status as 'success' | 'error',
            botId: call.bot_id,
            botName: call.bot_name,
            pipelineId: call.pipeline_id,
            pipelineName: call.pipeline_name,
            errorMessage: call.error_message,
            messageId: call.message_id,
          }),
        ),
        embeddingCalls: (response.embeddingCalls || []).map(
          (call: {
            id: string;
            timestamp: string;
            model_name: string;
            prompt_tokens: number;
            total_tokens: number;
            duration: number;
            input_count: number;
            status: string;
            error_message?: string;
            knowledge_base_id?: string;
            query_text?: string;
            session_id?: string;
            message_id?: string;
            call_type?: string;
          }) => ({
            id: call.id,
            timestamp: new Date(call.timestamp),
            modelName: call.model_name,
            promptTokens: call.prompt_tokens,
            totalTokens: call.total_tokens,
            duration: call.duration,
            inputCount: call.input_count,
            status: call.status as 'success' | 'error',
            errorMessage: call.error_message,
            knowledgeBaseId: call.knowledge_base_id,
            queryText: call.query_text,
            sessionId: call.session_id,
            messageId: call.message_id,
            callType: call.call_type as 'embedding' | 'retrieve' | undefined,
          }),
        ),
        // Create merged modelCalls array from llmCalls and embeddingCalls
        modelCalls: [] as ModelCall[], // Will be populated after transform
        sessions: response.sessions.map(
          (session: {
            session_id: string;
            bot_id: string;
            bot_name: string;
            pipeline_id: string;
            pipeline_name: string;
            message_count: number;
            last_activity: string;
            start_time: string;
            platform?: string;
            user_id?: string;
          }) => ({
            sessionId: session.session_id,
            botId: session.bot_id,
            botName: session.bot_name,
            pipelineId: session.pipeline_id,
            pipelineName: session.pipeline_name,
            messageCount: session.message_count,
            duration:
              new Date(session.last_activity).getTime() -
              new Date(session.start_time).getTime(),
            lastActivity: new Date(session.last_activity),
            startTime: new Date(session.start_time),
            platform: session.platform,
            userId: session.user_id,
          }),
        ),
        errors: response.errors.map(
          (error: {
            id: string;
            timestamp: string;
            error_type: string;
            error_message: string;
            bot_id: string;
            bot_name: string;
            pipeline_id: string;
            pipeline_name: string;
            session_id?: string;
            stack_trace?: string;
            message_id?: string;
          }) => ({
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
            messageId: error.message_id,
          }),
        ),
        totalCount: {
          messages: response.totalCount.messages,
          llmCalls: response.totalCount.llmCalls,
          embeddingCalls: response.totalCount.embeddingCalls || 0,
          sessions: response.totalCount.sessions,
          errors: response.totalCount.errors,
        },
      };

      // Merge LLM calls and embedding calls into modelCalls
      const llmModelCalls: ModelCall[] = transformedData.llmCalls.map(
        (call: LLMCall): ModelCall => ({
          id: call.id,
          timestamp: call.timestamp,
          modelName: call.modelName,
          modelType: 'llm',
          status: call.status,
          duration: call.duration,
          errorMessage: call.errorMessage,
          messageId: call.messageId,
          tokens: call.tokens,
          cost: call.cost,
          botId: call.botId,
          botName: call.botName,
          pipelineId: call.pipelineId,
          pipelineName: call.pipelineName,
        }),
      );

      const embeddingModelCalls: ModelCall[] =
        transformedData.embeddingCalls.map(
          (call: EmbeddingCall): ModelCall => ({
            id: call.id,
            timestamp: call.timestamp,
            modelName: call.modelName,
            modelType: 'embedding',
            status: call.status,
            duration: call.duration,
            errorMessage: call.errorMessage,
            messageId: call.messageId,
            callType: call.callType,
            promptTokens: call.promptTokens,
            totalTokens: call.totalTokens,
            inputCount: call.inputCount,
            knowledgeBaseId: call.knowledgeBaseId,
            queryText: call.queryText,
            sessionId: call.sessionId,
          }),
        );

      // Combine and sort by timestamp (newest first)
      transformedData.modelCalls = [
        ...llmModelCalls,
        ...embeddingModelCalls,
      ].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());

      setData(transformedData);
    } catch (err) {
      setError(err as Error);
      console.error('Failed to fetch monitoring data:', err);
    } finally {
      setLoading(false);
    }
  }, [getTimeRange, filterState.selectedBots, filterState.selectedPipelines]);

  // Fetch data when filter state changes
  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    selectedBotsStr,
    selectedPipelinesStr,
    filterState.timeRange,
    customDateRangeStr,
  ]);

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
