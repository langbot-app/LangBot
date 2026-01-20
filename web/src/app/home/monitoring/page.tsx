'use client';

import React, { Suspense, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { ChevronRight, ChevronDown } from 'lucide-react';
import OverviewCards from './components/overview-cards/OverviewCards';
import MonitoringFilters from './components/filters/MonitoringFilters';
import { useMonitoringFilters } from './hooks/useMonitoringFilters';
import { useMonitoringData } from './hooks/useMonitoringData';
import { MessageDetailsCard } from './components/MessageDetailsCard';
import { MessageContentRenderer } from './components/MessageContentRenderer';
import { MessageDetails } from './types/monitoring';
import { httpClient } from '@/app/infra/http/HttpClient';

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
            message: any;
            llm_calls: any[];
            llm_stats: any;
            errors: any[];
          }>(`/api/v1/monitoring/messages/${messageId}/details`);

          if (result) {
            setMessageDetails({
              ...messageDetails,
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
                    }
                  : undefined,
                llmCalls: result.llm_calls.map((call: any) => ({
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
                errors: result.errors.map((error: any) => ({
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
              },
            });
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
    <div className="flex flex-col gap-6 p-6">
      {/* Overview Section */}
      <div>
        {/* Filters and Refresh Button in one row */}
        <div className="flex items-center justify-between mb-4">
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
            className="bg-white dark:bg-[#2a2a2e] flex-shrink-0"
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

        <OverviewCards
          metrics={data?.overview || null}
          messages={data?.messages || []}
          llmCalls={data?.llmCalls || []}
          loading={loading}
        />
      </div>

      {/* Tabs Section */}
      <div>
        <Tabs defaultValue="messages" className="w-full">
          <TabsList className="bg-gray-100 dark:bg-[#2a2a2e]">
            <TabsTrigger value="messages">
              {t('monitoring.tabs.messages')}
            </TabsTrigger>
            <TabsTrigger value="llmCalls">
              {t('monitoring.tabs.llmCalls')}
            </TabsTrigger>
            <TabsTrigger value="errors">
              {t('monitoring.tabs.errors')}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="messages" className="mt-4">
            <div className="bg-white dark:bg-[#2a2a2e] rounded-lg border border-gray-200 dark:border-gray-700 p-6">
              {loading && (
                <div className="text-center text-gray-500 dark:text-gray-400">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-white"></div>
                  <p className="mt-2 text-sm">
                    {t('monitoring.messageList.loading')}
                  </p>
                </div>
              )}

              {!loading &&
                data &&
                data.messages &&
                data.messages.length > 0 && (
                  <div className="space-y-3">
                    {data.messages
                      .filter((msg) => {
                        // Filter out messages with empty content
                        const content = msg.messageContent?.trim();
                        return content && content !== '[]' && content !== '""';
                      })
                      .map((msg) => (
                      <div
                        key={msg.id}
                        className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
                      >
                        {/* Message Header - Always Visible */}
                        <div
                          className="p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
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
                                      <span className="text-gray-400">→</span>
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
                  <div className="text-center text-gray-500 dark:text-gray-400">
                    <p className="text-lg font-medium mb-2">
                      {t('monitoring.messageList.noMessages')}
                    </p>
                    <p className="text-sm">
                      {t('monitoring.messageList.noMessagesDescription')}
                    </p>
                  </div>
                )}
            </div>
          </TabsContent>

          <TabsContent value="llmCalls" className="mt-4">
            <div className="bg-white dark:bg-[#2a2a2e] rounded-lg border border-gray-200 dark:border-gray-700 p-6">
              {loading && (
                <div className="text-center text-gray-500 dark:text-gray-400">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-white"></div>
                  <p className="mt-2 text-sm">{t('common.loading')}</p>
                </div>
              )}

              {!loading &&
                data &&
                data.llmCalls &&
                data.llmCalls.length > 0 && (
                  <div className="space-y-3">
                    {data.llmCalls.map((call) => (
                      <div
                        key={call.id}
                        className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                      >
                        <div className="flex justify-between items-start mb-3">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="font-medium text-sm text-gray-700 dark:text-gray-300">
                                {call.modelName}
                              </span>
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
                            <div className="text-xs text-gray-600 dark:text-gray-400 space-y-1">
                              <div>
                                {call.botName} → {call.pipelineName}
                              </div>
                              <div className="flex gap-4">
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
                                <span>
                                  {t('monitoring.llmCalls.duration')}:{' '}
                                  {call.duration}
                                  ms
                                </span>
                                {call.cost && (
                                  <span>
                                    {t('monitoring.llmCalls.cost')}: $
                                    {call.cost.toFixed(4)}
                                  </span>
                                )}
                              </div>
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
                (!data || !data.llmCalls || data.llmCalls.length === 0) && (
                  <div className="text-center text-gray-500 dark:text-gray-400">
                    <p className="text-lg font-medium">
                      {t('monitoring.llmCalls.noData')}
                    </p>
                  </div>
                )}
            </div>
          </TabsContent>

          <TabsContent value="errors" className="mt-4">
            <div className="bg-white dark:bg-[#2a2a2e] rounded-lg border border-gray-200 dark:border-gray-700 p-6">
              {loading && (
                <div className="text-center text-gray-500 dark:text-gray-400">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-white"></div>
                  <p className="mt-2 text-sm">{t('common.loading')}</p>
                </div>
              )}

              {!loading && data && data.errors && data.errors.length > 0 && (
                <div className="space-y-3">
                  {data.errors.map((error) => (
                    <div
                      key={error.id}
                      className="border border-red-200 dark:border-red-900 rounded-lg overflow-hidden"
                    >
                      {/* Error Header - Always Visible */}
                      <div
                        className="p-4 cursor-pointer hover:bg-red-50 dark:hover:bg-red-950 transition-colors bg-red-50 dark:bg-red-950"
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
                        <div className="border-t border-red-200 dark:border-red-900 p-4 bg-white dark:bg-gray-900">
                          <div className="space-y-4 pl-8 border-l-2 border-red-200 dark:border-red-800 ml-4">
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
                  <div className="text-center text-gray-500 dark:text-gray-400">
                    <p className="text-lg font-medium">
                      {t('monitoring.errors.noErrors')}
                    </p>
                  </div>
                )}
            </div>
          </TabsContent>
        </Tabs>
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
