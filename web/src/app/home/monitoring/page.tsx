'use client';

import React, { Suspense, useState, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { ChevronRight, ChevronDown, ExternalLink } from 'lucide-react';
import OverviewCards from './components/overview-cards/OverviewCards';
import MonitoringFilters from './components/filters/MonitoringFilters';
import { ExportDropdown } from './components/ExportDropdown';
import { useMonitoringFilters } from './hooks/useMonitoringFilters';
import { useMonitoringData } from './hooks/useMonitoringData';
import { useFeedbackData } from './hooks/useFeedbackData';
import { MessageDetailsCard } from './components/MessageDetailsCard';
import { MessageContentRenderer } from './components/MessageContentRenderer';
import { FeedbackStatsCards } from './components/FeedbackCard';
import { FeedbackList } from './components/FeedbackList';
import { MessageDetails } from './types/monitoring';
import { httpClient } from '@/app/infra/http/HttpClient';
import { LoadingSpinner, LoadingPage } from '@/components/ui/loading-spinner';

interface RawMessageData {
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
  platform: string;
  user_id: string;
  runner_name: string;
  variables: Record<string, unknown>;
}

interface RawLLMCallData {
  id: string;
  timestamp: string;
  model_name: string;
  status: string;
  duration: number;
  error_message: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

interface RawLLMStatsData {
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_duration_ms: number;
  average_duration_ms: number;
}

interface RawErrorData {
  id: string;
  timestamp: string;
  error_type: string;
  error_message: string;
  stack_trace: string | null;
}

function MonitoringPageContent() {
  const { t } = useTranslation();
  const { filterState, setSelectedBots, setSelectedPipelines, setTimeRange } =
    useMonitoringFilters();
  const { data, loading, refetch } = useMonitoringData(filterState);

  // Get time range for feedback data
  const feedbackTimeRange = useMemo(() => {
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

  // Feedback data hook
  const {
    feedback: feedbackList,
    stats: feedbackStats,
    total: feedbackTotal,
    loading: feedbackLoading,
    refetch: refetchFeedback,
  } = useFeedbackData({
    botIds:
      filterState.selectedBots.length > 0
        ? filterState.selectedBots
        : undefined,
    pipelineIds:
      filterState.selectedPipelines.length > 0
        ? filterState.selectedPipelines
        : undefined,
    startTime: feedbackTimeRange.startTime,
    endTime: feedbackTimeRange.endTime,
    limit: 50,
  });

  const [expandedMessageId, setExpandedMessageId] = useState<string | null>(
    null,
  );
  const [messageDetails, setMessageDetails] = useState<
    Record<string, MessageDetails>
  >({});
  const [loadingDetails, setLoadingDetails] = useState<Record<string, boolean>>(
    {},
  );

  // State for expanded errors
  const [expandedErrorId, setExpandedErrorId] = useState<string | null>(null);

  // State for controlled tabs
  const [activeTab, setActiveTab] = useState<string>('messages');

  // Function to jump to a message record
  const jumpToMessage = async (messageId: string) => {
    setActiveTab('messages');
    // Small delay to ensure tab switch completes
    setTimeout(() => {
      toggleMessageExpand(messageId);
    }, 100);
  };

  const toggleMessageExpand = async (messageId: string) => {
    if (expandedMessageId === messageId) {
      // Collapse
      setExpandedMessageId(null);
    } else {
      // Expand
      setExpandedMessageId(messageId);

      // Fetch details if not already loaded
      if (!messageDetails[messageId]) {
        setLoadingDetails({ ...loadingDetails, [messageId]: true });
        try {
          // httpClient.get() returns the inner data directly (response.data.data)
          const result = await httpClient.get<{
            message_id: string;
            found: boolean;
            message: RawMessageData | null;
            llm_calls: RawLLMCallData[];
            llm_stats: RawLLMStatsData;
            errors: RawErrorData[];
          }>(`/api/v1/monitoring/messages/${messageId}/details`);

          if (result) {
            setMessageDetails((prev) => ({
              ...prev,
              [messageId]: {
                messageId: result.message_id,
                found: result.found,
                message: result.message
                  ? {
                      id: result.message.id,
                      timestamp: new Date(result.message.timestamp),
                      botId: result.message.bot_id,
                      botName: result.message.bot_name,
                      pipelineId: result.message.pipeline_id,
                      pipelineName: result.message.pipeline_name,
                      messageContent: result.message.message_content,
                      sessionId: result.message.session_id,
                      status: result.message.status,
                      level: result.message.level,
                      platform: result.message.platform,
                      userId: result.message.user_id,
                      runnerName: result.message.runner_name,
                      variables: result.message.variables,
                    }
                  : undefined,
                llmCalls: result.llm_calls.map((call: RawLLMCallData) => ({
                  id: call.id,
                  timestamp: new Date(call.timestamp),
                  modelName: call.model_name,
                  status: call.status,
                  duration: call.duration,
                  errorMessage: call.error_message,
                  tokens: {
                    input: call.input_tokens || 0,
                    output: call.output_tokens || 0,
                    total: call.total_tokens || 0,
                  },
                })),
                errors: result.errors.map((error: RawErrorData) => ({
                  id: error.id,
                  timestamp: new Date(error.timestamp),
                  errorType: error.error_type,
                  errorMessage: error.error_message,
                  stackTrace: error.stack_trace,
                })),
                llmStats: {
                  totalCalls: result.llm_stats.total_calls,
                  totalInputTokens: result.llm_stats.total_input_tokens,
                  totalOutputTokens: result.llm_stats.total_output_tokens,
                  totalTokens: result.llm_stats.total_tokens,
                  totalDurationMs: result.llm_stats.total_duration_ms,
                  averageDurationMs: result.llm_stats.average_duration_ms,
                },
              } as MessageDetails,
            }));
          }
        } catch (error) {
          console.error('Failed to fetch message details:', error);
        } finally {
          setLoadingDetails({ ...loadingDetails, [messageId]: false });
        }
      }
    }
  };

  const toggleErrorExpand = (errorId: string) => {
    if (expandedErrorId === errorId) {
      setExpandedErrorId(null);
    } else {
      setExpandedErrorId(errorId);
    }
  };

  return (
    <div className="w-full h-full overflow-y-auto overflow-x-hidden">
      {/* Filters and Refresh Button - Sticky */}
      <div className="sticky top-[-1.5rem] z-10 -ml-[2rem] -mr-[1.5rem] -mt-[1.5rem] pt-[1.5rem] pb-4 bg-background">
        <div className="ml-[2rem] mr-[1.5rem] px-[0.8rem]">
          <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-card rounded-xl border">
            <MonitoringFilters
              selectedBots={filterState.selectedBots}
              selectedPipelines={filterState.selectedPipelines}
              timeRange={filterState.timeRange}
              onBotsChange={setSelectedBots}
              onPipelinesChange={setSelectedPipelines}
              onTimeRangeChange={setTimeRange}
            />
            <div className="flex items-center gap-2">
              <ExportDropdown filterState={filterState} />
              <Button
                variant="outline"
                size="sm"
                onClick={refetch}
                className="shadow-sm flex-shrink-0"
              >
                <svg
                  className="w-4 h-4 mr-2"
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M5.46257 4.43262C7.21556 2.91688 9.5007 2 12 2C17.5228 2 22 6.47715 22 12C22 14.1361 21.3302 16.1158 20.1892 17.7406L17 12H20C20 7.58172 16.4183 4 12 4C9.84982 4 7.89777 4.84827 6.46023 6.22842L5.46257 4.43262ZM18.5374 19.5674C16.7844 21.0831 14.4993 22 12 22C6.47715 22 2 17.5228 2 12C2 9.86386 2.66979 7.88416 3.8108 6.25944L7 12H4C4 16.4183 7.58172 20 12 20C14.1502 20 16.1022 19.1517 17.5398 17.7716L18.5374 19.5674Z"></path>
                </svg>
                {t('monitoring.refreshData')}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex flex-col gap-6 px-[0.8rem] pb-4">
        {/* Overview Section */}
        <OverviewCards
          metrics={data?.overview || null}
          messages={data?.messages || []}
          llmCalls={data?.llmCalls || []}
          loading={loading}
        />

        {/* Tabs Section */}
        <div className="bg-card rounded-xl border overflow-hidden">
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="w-full"
          >
            <div className="px-6 pt-4">
              <TabsList className="h-12 p-1">
                <TabsTrigger value="messages" className="px-6 py-2">
                  {t('monitoring.tabs.messages')}
                </TabsTrigger>
                <TabsTrigger value="modelCalls" className="px-6 py-2">
                  {t('monitoring.tabs.modelCalls')}
                </TabsTrigger>
                <TabsTrigger value="feedback" className="px-6 py-2">
                  {t('monitoring.tabs.feedback')}
                </TabsTrigger>
                <TabsTrigger value="errors" className="px-6 py-2">
                  {t('monitoring.tabs.errors')}
                </TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="messages" className="p-6 m-0">
              <div>
                {loading && (
                  <div className="py-12 flex justify-center">
                    <LoadingSpinner
                      text={t('monitoring.messageList.loading')}
                    />
                  </div>
                )}

                {!loading &&
                  data &&
                  data.messages &&
                  data.messages.length > 0 && (
                    <div className="space-y-4">
                      {data.messages
                        .filter((msg) => {
                          // Filter out messages with empty content
                          const content = msg.messageContent?.trim();
                          return (
                            content && content !== '[]' && content !== '""'
                          );
                        })
                        .map((msg) => (
                          <div
                            key={msg.id}
                            className="border rounded-xl overflow-hidden transition-all duration-200"
                          >
                            {/* Message Header - Always Visible */}
                            <div
                              className="p-5 cursor-pointer hover:bg-accent transition-colors"
                              onClick={() => toggleMessageExpand(msg.id)}
                            >
                              <div className="flex items-start justify-between">
                                <div className="flex items-start flex-1">
                                  {/* Expand Icon */}
                                  <div className="mr-3 mt-0.5">
                                    {expandedMessageId === msg.id ? (
                                      <ChevronDown className="w-5 h-5 text-muted-foreground" />
                                    ) : (
                                      <ChevronRight className="w-5 h-5 text-muted-foreground" />
                                    )}
                                  </div>

                                  {/* Message Info */}
                                  <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-1">
                                      <span className="text-xs text-muted-foreground font-mono">
                                        ID: {msg.id}
                                      </span>
                                    </div>
                                    <div className="flex items-center gap-2 mb-2">
                                      <span className="font-medium text-sm text-foreground">
                                        {msg.botName}
                                      </span>
                                      <span className="text-muted-foreground">
                                        →
                                      </span>
                                      <span className="text-sm text-muted-foreground">
                                        {msg.pipelineName}
                                      </span>
                                      {msg.runnerName && (
                                        <>
                                          <span className="text-muted-foreground">
                                            →
                                          </span>
                                          <span className="text-sm text-muted-foreground">
                                            {msg.runnerName}
                                          </span>
                                        </>
                                      )}
                                    </div>
                                    <div className="text-base text-foreground">
                                      <MessageContentRenderer
                                        content={msg.messageContent}
                                        maxLines={3}
                                      />
                                    </div>
                                  </div>
                                </div>

                                {/* Status and Timestamp */}
                                <div className="flex flex-col items-end gap-2 ml-4">
                                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                                    {msg.timestamp.toLocaleString()}
                                  </span>
                                  <span
                                    className={`text-xs px-2 py-1 rounded ${
                                      msg.level === 'error'
                                        ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                                        : msg.level === 'warning'
                                          ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                                          : 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                    }`}
                                  >
                                    {msg.level}
                                  </span>
                                </div>
                              </div>
                            </div>

                            {/* Expanded Details */}
                            {expandedMessageId === msg.id && (
                              <div className="border-t p-4 bg-muted">
                                {loadingDetails[msg.id] && (
                                  <div className="py-4 flex justify-center">
                                    <LoadingSpinner size="sm" text="" />
                                  </div>
                                )}
                                {!loadingDetails[msg.id] &&
                                  messageDetails[msg.id] && (
                                    <MessageDetailsCard
                                      details={messageDetails[msg.id]}
                                    />
                                  )}
                              </div>
                            )}
                          </div>
                        ))}
                    </div>
                  )}

                {!loading &&
                  (!data || !data.messages || data.messages.length === 0) && (
                    <div className="flex flex-col items-center justify-center text-muted-foreground py-16 gap-2">
                      <svg
                        className="h-[3rem] w-[3rem]"
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                      >
                        <path d="M6.45455 19L2 22.5V4C2 3.44772 2.44772 3 3 3H21C21.5523 3 22 3.44772 22 4V18C22 18.5523 21.5523 19 21 19H6.45455ZM4 18.3851L5.76282 17H20V5H4V18.3851Z"></path>
                      </svg>
                      <div className="text-sm">
                        {t('monitoring.messageList.noMessages')}
                      </div>
                    </div>
                  )}
              </div>
            </TabsContent>

            <TabsContent value="modelCalls" className="p-6 m-0">
              <div>
                {loading && (
                  <div className="py-12 flex justify-center">
                    <LoadingSpinner text={t('common.loading')} />
                  </div>
                )}

                {!loading &&
                  data &&
                  data.modelCalls &&
                  data.modelCalls.length > 0 && (
                    <div className="space-y-4">
                      {data.modelCalls.map((call) => (
                        <div
                          key={call.id}
                          className="border rounded-xl p-5 transition-all duration-200"
                        >
                          <div className="flex justify-between items-start mb-3">
                            <div className="flex-1">
                              {/* Query ID - only show if messageId exists */}
                              {call.messageId && (
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="text-xs text-muted-foreground font-mono">
                                    Query ID: {call.messageId}
                                  </span>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-5 px-1.5 text-xs"
                                    onClick={() =>
                                      jumpToMessage(call.messageId!)
                                    }
                                  >
                                    <ExternalLink className="w-3 h-3 mr-1" />
                                    {t(
                                      'monitoring.messageList.viewConversation',
                                    )}
                                  </Button>
                                </div>
                              )}
                              <div className="flex items-center gap-2 mb-2">
                                {/* Model Type Badge */}
                                <span
                                  className={`text-xs px-2 py-1 rounded ${
                                    call.modelType === 'llm'
                                      ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                                      : 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
                                  }`}
                                >
                                  {call.modelType === 'llm'
                                    ? t('monitoring.modelCalls.llmModel')
                                    : t('monitoring.modelCalls.embeddingModel')}
                                </span>
                                {/* Call Type Badge for Embedding */}
                                {call.modelType === 'embedding' &&
                                  call.callType && (
                                    <span
                                      className={`text-xs px-2 py-1 rounded ${
                                        call.callType === 'retrieve'
                                          ? 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200'
                                          : 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'
                                      }`}
                                    >
                                      {call.callType === 'retrieve'
                                        ? t(
                                            'monitoring.modelCalls.retrieveCall',
                                          )
                                        : t(
                                            'monitoring.modelCalls.embeddingCall',
                                          )}
                                    </span>
                                  )}
                                {/* Status Badge */}
                                <span
                                  className={`text-xs px-2 py-1 rounded ${
                                    call.status === 'success'
                                      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                      : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                                  }`}
                                >
                                  {call.status}
                                </span>
                              </div>
                              {/* Model Name */}
                              <div className="font-medium text-sm text-foreground mb-2">
                                {call.modelName}
                              </div>
                              {/* Context Info - only for LLM calls */}
                              {call.modelType === 'llm' &&
                                call.botName &&
                                call.pipelineName && (
                                  <div className="text-xs text-muted-foreground mb-1">
                                    {call.botName} → {call.pipelineName}
                                  </div>
                                )}
                              {/* Token Info */}
                              <div className="text-xs text-muted-foreground space-y-1">
                                <div className="flex flex-wrap gap-4">
                                  {call.modelType === 'llm' && call.tokens && (
                                    <>
                                      <span>
                                        {t('monitoring.llmCalls.inputTokens')}:{' '}
                                        {call.tokens.input}
                                      </span>
                                      <span>
                                        {t('monitoring.llmCalls.outputTokens')}:{' '}
                                        {call.tokens.output}
                                      </span>
                                      <span>
                                        {t('monitoring.llmCalls.totalTokens')}:{' '}
                                        {call.tokens.total}
                                      </span>
                                    </>
                                  )}
                                  {call.modelType === 'embedding' && (
                                    <>
                                      <span>
                                        {t(
                                          'monitoring.embeddingCalls.promptTokens',
                                        )}
                                        : {call.promptTokens}
                                      </span>
                                      <span>
                                        {t(
                                          'monitoring.embeddingCalls.totalTokens',
                                        )}
                                        : {call.totalTokens}
                                      </span>
                                      <span>
                                        {t(
                                          'monitoring.embeddingCalls.inputCount',
                                        )}
                                        : {call.inputCount}
                                      </span>
                                    </>
                                  )}
                                  <span>
                                    {t('monitoring.llmCalls.duration')}:{' '}
                                    {call.duration}ms
                                  </span>
                                  {call.cost && (
                                    <span>
                                      {t('monitoring.llmCalls.cost')}: $
                                      {call.cost.toFixed(4)}
                                    </span>
                                  )}
                                </div>
                                {/* Knowledge Base Info for Embedding */}
                                {call.modelType === 'embedding' &&
                                  call.knowledgeBaseId && (
                                    <div>
                                      {t(
                                        'monitoring.embeddingCalls.knowledgeBase',
                                      )}
                                      : {call.knowledgeBaseId}
                                    </div>
                                  )}
                                {/* Query Text for Embedding Retrieve */}
                                {call.modelType === 'embedding' &&
                                  call.queryText && (
                                    <div className="mt-2 p-2 bg-muted rounded text-sm">
                                      <span className="text-muted-foreground">
                                        {t(
                                          'monitoring.embeddingCalls.queryText',
                                        )}
                                        :{' '}
                                      </span>
                                      <span className="text-foreground">
                                        {call.queryText.length > 100
                                          ? call.queryText.substring(0, 100) +
                                            '...'
                                          : call.queryText}
                                      </span>
                                    </div>
                                  )}
                              </div>
                              {call.errorMessage && (
                                <div className="mt-2 text-xs text-red-600 dark:text-red-400">
                                  Error: {call.errorMessage}
                                </div>
                              )}
                            </div>
                            <span className="text-xs text-muted-foreground whitespace-nowrap ml-4">
                              {call.timestamp.toLocaleString()}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                {!loading &&
                  (!data ||
                    !data.modelCalls ||
                    data.modelCalls.length === 0) && (
                    <div className="flex flex-col items-center justify-center text-muted-foreground py-16 gap-2">
                      <svg
                        className="h-[3rem] w-[3rem]"
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                      >
                        <path d="M10.6144 17.7956C10.277 18.5682 9.20776 18.5682 8.8704 17.7956L7.99275 15.7854C7.21171 13.9966 5.80589 12.5726 4.0523 11.7942L1.63658 10.7219C.868536 10.381.868537 9.26368 1.63658 8.92276L3.97685 7.88394C5.77553 7.08552 7.20657 5.60881 7.97427 3.75892L8.8633 1.61673C9.19319.821767 10.2916.821765 10.6215 1.61673L11.5105 3.75894C12.2782 5.60881 13.7092 7.08552 15.5079 7.88394L17.8482 8.92276C18.6162 9.26368 18.6162 10.381 17.8482 10.7219L15.4325 11.7942C13.6789 12.5726 12.2731 13.9966 11.492 15.7854L10.6144 17.7956ZM19.4014 22.6899 19.6482 22.1242C20.0882 21.1156 20.8807 20.3125 21.8695 19.8732L22.6299 19.5353C23.0412 19.3526 23.0412 18.7549 22.6299 18.5722L21.9121 18.2532C20.8978 17.8026 20.0911 16.9698 19.6586 15.9269L19.4052 15.3156C19.2285 14.8896 18.6395 14.8896 18.4628 15.3156L18.2094 15.9269C17.777 16.9698 16.9703 17.8026 15.956 18.2532L15.2381 18.5722C14.8269 18.7549 14.8269 19.3526 15.2381 19.5353L15.9985 19.8732C16.9874 20.3125 17.7798 21.1156 18.2198 22.1242L18.4667 22.6899C18.6473 23.104 19.2207 23.104 19.4014 22.6899Z"></path>
                      </svg>
                      <div className="text-sm">
                        {t('monitoring.modelCalls.noData')}
                      </div>
                    </div>
                  )}
              </div>
            </TabsContent>

            <TabsContent value="feedback" className="p-6 m-0">
              <div>
                {loading && (
                  <div className="py-12 flex justify-center">
                    <LoadingSpinner text={t('common.loading')} />
                  </div>
                )}

                {!loading && (
                  <>
                    {/* Feedback Stats Cards */}
                    <div className="mb-6">
                      <FeedbackStatsCards
                        stats={feedbackStats}
                        loading={feedbackLoading}
                      />
                    </div>

                    {/* Feedback List */}
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                      {t('monitoring.feedback.feedbackList')}
                    </h3>
                    <FeedbackList
                      feedback={feedbackList}
                      loading={feedbackLoading}
                      onViewMessage={jumpToMessage}
                    />
                  </>
                )}
              </div>
            </TabsContent>

            <TabsContent value="errors" className="p-6 m-0">
              <div>
                {loading && (
                  <div className="py-12 flex justify-center">
                    <LoadingSpinner text={t('common.loading')} />
                  </div>
                )}

                {!loading && data && data.errors && data.errors.length > 0 && (
                  <div className="space-y-4">
                    {data.errors.map((error) => (
                      <div
                        key={error.id}
                        className="border border-red-200 dark:border-red-900 rounded-xl overflow-hidden transition-all duration-200"
                      >
                        {/* Error Header - Always Visible */}
                        <div
                          className="p-5 cursor-pointer hover:bg-red-50 dark:hover:bg-red-950/50 transition-colors bg-red-50/50 dark:bg-red-950/30"
                          onClick={() => toggleErrorExpand(error.id)}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex items-start flex-1">
                              {/* Expand Icon */}
                              <div className="mr-3 mt-0.5">
                                {expandedErrorId === error.id ? (
                                  <ChevronDown className="w-5 h-5 text-red-500" />
                                ) : (
                                  <ChevronRight className="w-5 h-5 text-red-500" />
                                )}
                              </div>

                              {/* Error Info */}
                              <div className="flex-1">
                                {/* Query ID */}
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="text-xs text-muted-foreground font-mono">
                                    Query ID: {error.messageId || '-'}
                                  </span>
                                  {error.messageId && (
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-5 px-1.5 text-xs"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        jumpToMessage(error.messageId!);
                                      }}
                                    >
                                      <ExternalLink className="w-3 h-3 mr-1" />
                                      {t(
                                        'monitoring.messageList.viewConversation',
                                      )}
                                    </Button>
                                  )}
                                </div>
                                <div className="flex items-center gap-2 mb-2">
                                  <span className="font-medium text-sm text-red-700 dark:text-red-300">
                                    {error.errorType}
                                  </span>
                                  <span className="text-red-400">→</span>
                                  <span className="text-sm text-muted-foreground">
                                    {error.botName}
                                  </span>
                                  <span className="text-red-400">→</span>
                                  <span className="text-sm text-muted-foreground">
                                    {error.pipelineName}
                                  </span>
                                </div>
                                <p className="text-sm text-red-600 dark:text-red-400 line-clamp-2">
                                  {error.errorMessage}
                                </p>
                              </div>
                            </div>

                            {/* Timestamp */}
                            <div className="flex flex-col items-end gap-2 ml-4">
                              <span className="text-xs text-muted-foreground whitespace-nowrap">
                                {error.timestamp.toLocaleString()}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Expanded Details */}
                        {expandedErrorId === error.id && (
                          <div className="border-t border-red-200 dark:border-red-900 p-5 bg-background">
                            <div className="space-y-4 pl-8 border-l-2 border-red-300 dark:border-red-800 ml-4">
                              {/* Error Details */}
                              <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
                                <h4 className="text-sm font-semibold text-red-700 dark:text-red-400 mb-3">
                                  {t('monitoring.errors.errorMessage')}
                                </h4>
                                <div className="text-sm text-red-600 dark:text-red-400 whitespace-pre-wrap break-words">
                                  {error.errorMessage}
                                </div>
                              </div>

                              {/* Context Info */}
                              <div className="bg-muted rounded-lg p-3">
                                <h4 className="text-sm font-semibold text-foreground mb-3">
                                  {t('monitoring.messageList.viewDetails')}
                                </h4>
                                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                                  <div className="bg-background rounded p-2">
                                    <div className="text-muted-foreground">
                                      {t('monitoring.messageList.bot')}
                                    </div>
                                    <div className="font-medium text-foreground">
                                      {error.botName}
                                    </div>
                                  </div>
                                  <div className="bg-background rounded p-2">
                                    <div className="text-muted-foreground">
                                      {t('monitoring.messageList.pipeline')}
                                    </div>
                                    <div className="font-medium text-foreground">
                                      {error.pipelineName}
                                    </div>
                                  </div>
                                  {error.sessionId && (
                                    <div className="bg-background rounded p-2">
                                      <div className="text-muted-foreground">
                                        {t('monitoring.sessions.sessionId')}
                                      </div>
                                      <div className="font-medium text-foreground truncate">
                                        {error.sessionId}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </div>

                              {/* Stack Trace */}
                              {error.stackTrace && (
                                <div className="bg-muted rounded-lg p-3">
                                  <h4 className="text-sm font-semibold text-foreground mb-3">
                                    {t('monitoring.errors.stackTrace')}
                                  </h4>
                                  <pre className="text-xs text-muted-foreground overflow-auto max-h-60 bg-background p-3 rounded whitespace-pre-wrap break-words">
                                    {error.stackTrace}
                                  </pre>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {!loading &&
                  (!data || !data.errors || data.errors.length === 0) && (
                    <div className="flex flex-col items-center justify-center text-muted-foreground py-16 gap-2">
                      <svg
                        className="h-[3rem] w-[3rem] text-green-500 dark:text-green-600"
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                      >
                        <path d="M12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22ZM12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM11.0026 16L6.75999 11.7574L8.17421 10.3431L11.0026 13.1716L16.6595 7.51472L18.0737 8.92893L11.0026 16Z"></path>
                      </svg>
                      <div className="text-sm text-green-600 dark:text-green-400">
                        {t('monitoring.errors.noErrors')}
                      </div>
                    </div>
                  )}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}

export default function MonitoringPage() {
  return (
    <Suspense fallback={<LoadingPage />}>
      <MonitoringPageContent />
    </Suspense>
  );
}
