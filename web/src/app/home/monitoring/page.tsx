'use client';

import React, { Suspense, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { ChevronRight, ChevronDown, ExternalLink } from 'lucide-react';
import OverviewCards from './components/overview-cards/OverviewCards';
import MonitoringFilters from './components/filters/MonitoringFilters';
import { useMonitoringFilters } from './hooks/useMonitoringFilters';
import { useMonitoringData } from './hooks/useMonitoringData';
import { MessageDetailsCard } from './components/MessageDetailsCard';
import { MessageContentRenderer } from './components/MessageContentRenderer';
import { MessageDetails } from './types/monitoring';
import { httpClient } from '@/app/infra/http/HttpClient';

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
    <div className="w-full h-full">
      {/* Filters and Refresh Button - Sticky */}
      <div className="sticky top-[-1.5rem] z-10 -ml-[2rem] -mr-[1.5rem] -mt-[1.5rem] pt-[1.5rem] pb-4 bg-[#fafafa] dark:bg-[#151518]">
        <div className="ml-[2rem] mr-[1.5rem] px-[0.8rem]">
          <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-white dark:bg-[#2a2a2e] rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
            <MonitoringFilters
              selectedBots={filterState.selectedBots}
              selectedPipelines={filterState.selectedPipelines}
              timeRange={filterState.timeRange}
              onBotsChange={setSelectedBots}
              onPipelinesChange={setSelectedPipelines}
              onTimeRangeChange={setTimeRange}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={refetch}
              className="bg-white dark:bg-[#2a2a2e] hover:bg-gray-50 dark:hover:bg-gray-800 border-gray-300 dark:border-gray-600 shadow-sm flex-shrink-0"
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
        <div className="bg-white dark:bg-[#2a2a2e] rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="w-full"
          >
            <div className="px-6 pt-4">
              <TabsList className="bg-gray-100 dark:bg-[#1a1a1e] h-12 p-1">
                <TabsTrigger
                  value="messages"
                  className="px-6 py-2 text-sm font-medium cursor-pointer data-[state=active]:bg-white dark:data-[state=active]:bg-[#2a2a2e] data-[state=active]:shadow-sm"
                >
                  {t('monitoring.tabs.messages')}
                </TabsTrigger>
                <TabsTrigger
                  value="modelCalls"
                  className="px-6 py-2 text-sm font-medium cursor-pointer data-[state=active]:bg-white dark:data-[state=active]:bg-[#2a2a2e] data-[state=active]:shadow-sm"
                >
                  {t('monitoring.tabs.modelCalls')}
                </TabsTrigger>
                <TabsTrigger
                  value="errors"
                  className="px-6 py-2 text-sm font-medium cursor-pointer data-[state=active]:bg-white dark:data-[state=active]:bg-[#2a2a2e] data-[state=active]:shadow-sm"
                >
                  {t('monitoring.tabs.errors')}
                </TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="messages" className="p-6 m-0">
              <div>
                {loading && (
                  <div className="text-center text-gray-500 dark:text-gray-400 py-12">
                    <div className="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 dark:border-blue-400 mb-4"></div>
                    <p className="text-sm font-medium">
                      {t('monitoring.messageList.loading')}
                    </p>
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
                            className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden hover:shadow-md transition-all duration-200"
                          >
                            {/* Message Header - Always Visible */}
                            <div
                              className="p-5 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                              onClick={() => toggleMessageExpand(msg.id)}
                            >
                              <div className="flex items-start justify-between">
                                <div className="flex items-start flex-1">
                                  {/* Expand Icon */}
                                  <div className="mr-3 mt-0.5">
                                    {expandedMessageId === msg.id ? (
                                      <ChevronDown className="w-5 h-5 text-gray-500" />
                                    ) : (
                                      <ChevronRight className="w-5 h-5 text-gray-500" />
                                    )}
                                  </div>

                                  {/* Message Info */}
                                  <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-1">
                                      <span className="text-xs text-gray-400 dark:text-gray-500 font-mono">
                                        ID: {msg.id}
                                      </span>
                                    </div>
                                    <div className="flex items-center gap-2 mb-2">
                                      <span className="font-medium text-sm text-gray-700 dark:text-gray-300">
                                        {msg.botName}
                                      </span>
                                      <span className="text-gray-400">→</span>
                                      <span className="text-sm text-gray-600 dark:text-gray-400">
                                        {msg.pipelineName}
                                      </span>
                                      {msg.runnerName && (
                                        <>
                                          <span className="text-gray-400">
                                            →
                                          </span>
                                          <span className="text-sm text-gray-600 dark:text-gray-400">
                                            {msg.runnerName}
                                          </span>
                                        </>
                                      )}
                                    </div>
                                    <div className="text-base text-gray-800 dark:text-gray-200">
                                      <MessageContentRenderer
                                        content={msg.messageContent}
                                        maxLines={3}
                                      />
                                    </div>
                                  </div>
                                </div>

                                {/* Status and Timestamp */}
                                <div className="flex flex-col items-end gap-2 ml-4">
                                  <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
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
                              <div className="border-t border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-900">
                                {loadingDetails[msg.id] && (
                                  <div className="text-center text-gray-500 dark:text-gray-400 py-4">
                                    <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-gray-900 dark:border-white"></div>
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
                    <div className="text-center text-gray-500 dark:text-gray-400 py-16">
                      <svg
                        className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                        />
                      </svg>
                      <p className="text-base font-medium mb-2">
                        {t('monitoring.messageList.noMessages')}
                      </p>
                      <p className="text-sm">
                        {t('monitoring.messageList.noMessagesDescription')}
                      </p>
                    </div>
                  )}
              </div>
            </TabsContent>

            <TabsContent value="modelCalls" className="p-6 m-0">
              <div>
                {loading && (
                  <div className="text-center text-gray-500 dark:text-gray-400 py-12">
                    <div className="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 dark:border-blue-400 mb-4"></div>
                    <p className="text-sm font-medium">{t('common.loading')}</p>
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
                          className="border border-gray-200 dark:border-gray-700 rounded-xl p-5 hover:shadow-md transition-all duration-200"
                        >
                          <div className="flex justify-between items-start mb-3">
                            <div className="flex-1">
                              {/* Query ID - only show if messageId exists */}
                              {call.messageId && (
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="text-xs text-gray-400 dark:text-gray-500 font-mono">
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
                              <div className="font-medium text-sm text-gray-700 dark:text-gray-300 mb-2">
                                {call.modelName}
                              </div>
                              {/* Context Info - only for LLM calls */}
                              {call.modelType === 'llm' &&
                                call.botName &&
                                call.pipelineName && (
                                  <div className="text-xs text-gray-600 dark:text-gray-400 mb-1">
                                    {call.botName} → {call.pipelineName}
                                  </div>
                                )}
                              {/* Token Info */}
                              <div className="text-xs text-gray-600 dark:text-gray-400 space-y-1">
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
                                    <div className="mt-2 p-2 bg-gray-50 dark:bg-gray-800 rounded text-sm">
                                      <span className="text-gray-500 dark:text-gray-400">
                                        {t(
                                          'monitoring.embeddingCalls.queryText',
                                        )}
                                        :{' '}
                                      </span>
                                      <span className="text-gray-700 dark:text-gray-300">
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
                            <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap ml-4">
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
                    <div className="text-center text-gray-500 dark:text-gray-400 py-16">
                      <svg
                        className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                        />
                      </svg>
                      <p className="text-base font-medium">
                        {t('monitoring.modelCalls.noData')}
                      </p>
                    </div>
                  )}
              </div>
            </TabsContent>

            <TabsContent value="errors" className="p-6 m-0">
              <div>
                {loading && (
                  <div className="text-center text-gray-500 dark:text-gray-400 py-12">
                    <div className="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 dark:border-blue-400 mb-4"></div>
                    <p className="text-sm font-medium">{t('common.loading')}</p>
                  </div>
                )}

                {!loading && data && data.errors && data.errors.length > 0 && (
                  <div className="space-y-4">
                    {data.errors.map((error) => (
                      <div
                        key={error.id}
                        className="border border-red-200 dark:border-red-900 rounded-xl overflow-hidden hover:shadow-md transition-all duration-200"
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
                                  <span className="text-xs text-gray-400 dark:text-gray-500 font-mono">
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
                                  <span className="text-sm text-gray-600 dark:text-gray-400">
                                    {error.botName}
                                  </span>
                                  <span className="text-red-400">→</span>
                                  <span className="text-sm text-gray-600 dark:text-gray-400">
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
                              <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                                {error.timestamp.toLocaleString()}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Expanded Details */}
                        {expandedErrorId === error.id && (
                          <div className="border-t border-red-200 dark:border-red-900 p-5 bg-white dark:bg-gray-900">
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
                              <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                                  {t('monitoring.messageList.viewDetails')}
                                </h4>
                                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                                  <div className="bg-white dark:bg-gray-900 rounded p-2">
                                    <div className="text-gray-500 dark:text-gray-400">
                                      {t('monitoring.messageList.bot')}
                                    </div>
                                    <div className="font-medium text-gray-900 dark:text-white">
                                      {error.botName}
                                    </div>
                                  </div>
                                  <div className="bg-white dark:bg-gray-900 rounded p-2">
                                    <div className="text-gray-500 dark:text-gray-400">
                                      {t('monitoring.messageList.pipeline')}
                                    </div>
                                    <div className="font-medium text-gray-900 dark:text-white">
                                      {error.pipelineName}
                                    </div>
                                  </div>
                                  {error.sessionId && (
                                    <div className="bg-white dark:bg-gray-900 rounded p-2">
                                      <div className="text-gray-500 dark:text-gray-400">
                                        {t('monitoring.sessions.sessionId')}
                                      </div>
                                      <div className="font-medium text-gray-900 dark:text-white truncate">
                                        {error.sessionId}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </div>

                              {/* Stack Trace */}
                              {error.stackTrace && (
                                <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                                    {t('monitoring.errors.stackTrace')}
                                  </h4>
                                  <pre className="text-xs text-gray-600 dark:text-gray-400 overflow-auto max-h-60 bg-white dark:bg-gray-900 p-3 rounded whitespace-pre-wrap break-words">
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
                    <div className="text-center text-gray-500 dark:text-gray-400 py-16">
                      <svg
                        className="w-16 h-16 mx-auto mb-4 text-green-300 dark:text-green-600"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                      <p className="text-base font-medium text-green-600 dark:text-green-400">
                        {t('monitoring.errors.noErrors')}
                      </p>
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
    <Suspense fallback={<div>Loading...</div>}>
      <MonitoringPageContent />
    </Suspense>
  );
}
