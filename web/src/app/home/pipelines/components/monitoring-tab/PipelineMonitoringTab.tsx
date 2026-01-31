'use client';

import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { ChevronRight, ChevronDown, ExternalLink } from 'lucide-react';
import { useMonitoringData } from '@/app/home/monitoring/hooks/useMonitoringData';
import { MessageContentRenderer } from '@/app/home/monitoring/components/MessageContentRenderer';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { httpClient } from '@/app/infra/http/HttpClient';
import { MessageDetails } from '@/app/home/monitoring/types/monitoring';

interface PipelineMonitoringTabProps {
  pipelineId: string;
}

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

export default function PipelineMonitoringTab({
  pipelineId,
}: PipelineMonitoringTabProps) {
  const { t } = useTranslation();

  // Filter state - only show data for this pipeline, last 24 hours
  const filterState = useMemo(
    () => ({
      selectedBots: [],
      selectedPipelines: [pipelineId],
      timeRange: 'last24Hours' as const,
      customDateRange: null,
    }),
    [pipelineId],
  );

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
  const [expandedErrorId, setExpandedErrorId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('messages');

  const toggleMessageExpand = async (messageId: string) => {
    if (expandedMessageId === messageId) {
      setExpandedMessageId(null);
    } else {
      setExpandedMessageId(messageId);

      if (!messageDetails[messageId]) {
        setLoadingDetails((prev) => ({ ...prev, [messageId]: true }));
        try {
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
          setLoadingDetails((prev) => ({ ...prev, [messageId]: false }));
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

  const jumpToMessage = async (messageId: string) => {
    setActiveTab('messages');
    // Small delay to ensure tab transition completes before expanding
    setTimeout(() => {
      toggleMessageExpand(messageId);
    }, 100);
  };

  return (
    <div className="w-full h-full flex flex-col">
      {/* Header with refresh button */}
      <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {t('pipelines.monitoring.title')}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {t('pipelines.monitoring.description')}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={refetch}
          className="bg-white dark:bg-[#2a2a2e] hover:bg-gray-50 dark:hover:bg-gray-800 border-gray-300 dark:border-gray-600"
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

      {/* Overview Stats */}
      {data && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white dark:bg-[#2a2a2e] rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="text-sm text-gray-500 dark:text-gray-400">
              {t('monitoring.totalMessages')}
            </div>
            <div className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
              {data.overview.totalMessages}
            </div>
          </div>
          <div className="bg-white dark:bg-[#2a2a2e] rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="text-sm text-gray-500 dark:text-gray-400">
              {t('monitoring.successRate')}
            </div>
            <div className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
              {(data.overview.successRate * 100).toFixed(1)}%
            </div>
          </div>
          <div className="bg-white dark:bg-[#2a2a2e] rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="text-sm text-gray-500 dark:text-gray-400">
              {t('monitoring.tabs.errors')}
            </div>
            <div className="text-2xl font-bold text-red-600 dark:text-red-400 mt-1">
              {data.errors.length}
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="flex-1 flex flex-col min-h-0"
      >
        <TabsList className="bg-gray-100 dark:bg-[#1a1a1e] h-10 p-1 mb-4">
          <TabsTrigger
            value="messages"
            className="px-4 py-1.5 text-sm font-medium cursor-pointer data-[state=active]:bg-white dark:data-[state=active]:bg-[#2a2a2e] data-[state=active]:shadow-sm"
          >
            {t('monitoring.tabs.messages')}
          </TabsTrigger>
          <TabsTrigger
            value="errors"
            className="px-4 py-1.5 text-sm font-medium cursor-pointer data-[state=active]:bg-white dark:data-[state=active]:bg-[#2a2a2e] data-[state=active]:shadow-sm"
          >
            {t('monitoring.tabs.errors')}
          </TabsTrigger>
          <TabsTrigger
            value="llmCalls"
            className="px-4 py-1.5 text-sm font-medium cursor-pointer data-[state=active]:bg-white dark:data-[state=active]:bg-[#2a2a2e] data-[state=active]:shadow-sm"
          >
            {t('monitoring.tabs.modelCalls')}
          </TabsTrigger>
        </TabsList>

        <div className="flex-1 overflow-y-auto min-h-0">
          {/* Messages Tab */}
          <TabsContent value="messages" className="m-0 h-full">
            {loading && (
              <div className="py-12 flex justify-center">
                <LoadingSpinner text={t('monitoring.messageList.loading')} />
              </div>
            )}

            {!loading && data && data.messages && data.messages.length > 0 && (
              <div className="space-y-3">
                {data.messages
                  .filter((msg) => {
                    const content = msg.messageContent?.trim();
                    return content && content !== '[]' && content !== '""';
                  })
                  .map((msg) => (
                    <div
                      key={msg.id}
                      className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden hover:shadow-md transition-all duration-200"
                    >
                      <div
                        className="p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                        onClick={() => toggleMessageExpand(msg.id)}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-start flex-1">
                            <div className="mr-2 mt-0.5">
                              {expandedMessageId === msg.id ? (
                                <ChevronDown className="w-4 h-4 text-gray-500" />
                              ) : (
                                <ChevronRight className="w-4 h-4 text-gray-500" />
                              )}
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <span
                                  className={`text-xs px-2 py-0.5 rounded ${
                                    msg.status === 'success'
                                      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                      : msg.status === 'error'
                                        ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                                        : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                                  }`}
                                >
                                  {msg.status}
                                </span>
                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                  {msg.botName}
                                </span>
                              </div>
                              <div className="text-sm text-gray-700 dark:text-gray-300 line-clamp-2">
                                <MessageContentRenderer
                                  content={msg.messageContent}
                                />
                              </div>
                            </div>
                          </div>
                          <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap ml-4">
                            {msg.timestamp.toLocaleString()}
                          </span>
                        </div>
                      </div>

                      {expandedMessageId === msg.id && (
                        <div className="border-t border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-900">
                          {loadingDetails[msg.id] && (
                            <div className="flex justify-center py-8">
                              <LoadingSpinner
                                text={t('monitoring.messageList.loading')}
                              />
                            </div>
                          )}

                          {!loadingDetails[msg.id] &&
                            messageDetails[msg.id] && (
                              <div className="space-y-4">
                                {messageDetails[msg.id].errors.length > 0 && (
                                  <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
                                    <h4 className="text-sm font-semibold text-red-700 dark:text-red-400 mb-2">
                                      {t('monitoring.errors.errorMessage')}
                                    </h4>
                                    {messageDetails[msg.id].errors.map(
                                      (error) => (
                                        <div
                                          key={error.id}
                                          className="text-sm space-y-2"
                                        >
                                          <div className="text-red-600 dark:text-red-400">
                                            {error.errorType}:{' '}
                                            {error.errorMessage}
                                          </div>
                                          {error.stackTrace && (
                                            <pre className="text-xs text-gray-600 dark:text-gray-400 overflow-auto max-h-40 bg-white dark:bg-gray-900 p-2 rounded whitespace-pre-wrap break-words">
                                              {error.stackTrace}
                                            </pre>
                                          )}
                                        </div>
                                      ),
                                    )}
                                  </div>
                                )}

                                {messageDetails[msg.id].llmCalls.length > 0 && (
                                  <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
                                    <h4 className="text-sm font-semibold text-blue-700 dark:text-blue-400 mb-2">
                                      {t('monitoring.tabs.modelCalls')} (
                                      {messageDetails[msg.id].llmCalls.length})
                                    </h4>
                                    <div className="text-xs text-gray-600 dark:text-gray-400 space-y-1">
                                      <div>
                                        {t('monitoring.llmCalls.totalTokens')}:{' '}
                                        {
                                          messageDetails[msg.id].llmStats
                                            .totalTokens
                                        }
                                      </div>
                                      <div>
                                        {t('monitoring.llmCalls.duration')}:{' '}
                                        {messageDetails[
                                          msg.id
                                        ].llmStats.totalDurationMs.toFixed(0)}
                                        ms
                                      </div>
                                    </div>
                                  </div>
                                )}
                              </div>
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
                  <p className="text-base font-medium">
                    {t('monitoring.messageList.noData')}
                  </p>
                </div>
              )}
          </TabsContent>

          {/* Errors Tab */}
          <TabsContent value="errors" className="m-0 h-full">
            {loading && (
              <div className="py-12 flex justify-center">
                <LoadingSpinner text={t('common.loading')} />
              </div>
            )}

            {!loading && data && data.errors && data.errors.length > 0 && (
              <div className="space-y-3">
                {data.errors.map((error) => (
                  <div
                    key={error.id}
                    className="border border-red-200 dark:border-red-900 rounded-lg overflow-hidden hover:shadow-md transition-all duration-200"
                  >
                    <div
                      className="p-4 cursor-pointer hover:bg-red-50 dark:hover:bg-red-950/50 transition-colors bg-red-50/50 dark:bg-red-950/30"
                      onClick={() => toggleErrorExpand(error.id)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start flex-1">
                          <div className="mr-2 mt-0.5">
                            {expandedErrorId === error.id ? (
                              <ChevronDown className="w-4 h-4 text-red-500" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-red-500" />
                            )}
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
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
                                  {t('monitoring.messageList.viewConversation')}
                                </Button>
                              )}
                            </div>
                            <div className="font-medium text-sm text-red-700 dark:text-red-300 mb-1">
                              {error.errorType}
                            </div>
                            <p className="text-sm text-red-600 dark:text-red-400 line-clamp-2">
                              {error.errorMessage}
                            </p>
                          </div>
                        </div>
                        <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap ml-4">
                          {error.timestamp.toLocaleString()}
                        </span>
                      </div>
                    </div>

                    {expandedErrorId === error.id && (
                      <div className="border-t border-red-200 dark:border-red-900 p-4 bg-white dark:bg-gray-900">
                        <div className="space-y-3">
                          <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
                            <h4 className="text-sm font-semibold text-red-700 dark:text-red-400 mb-2">
                              {t('monitoring.errors.errorMessage')}
                            </h4>
                            <div className="text-sm text-red-600 dark:text-red-400 whitespace-pre-wrap break-words">
                              {error.errorMessage}
                            </div>
                          </div>

                          {error.stackTrace && (
                            <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                                {t('monitoring.errors.stackTrace')}
                              </h4>
                              <pre className="text-xs text-gray-600 dark:text-gray-400 overflow-auto max-h-60 bg-white dark:bg-gray-900 p-2 rounded whitespace-pre-wrap break-words">
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
          </TabsContent>

          {/* LLM Calls Tab */}
          <TabsContent value="llmCalls" className="m-0 h-full">
            {loading && (
              <div className="py-12 flex justify-center">
                <LoadingSpinner text={t('common.loading')} />
              </div>
            )}

            {!loading && data && data.llmCalls && data.llmCalls.length > 0 && (
              <div className="space-y-3">
                {data.llmCalls.map((call) => (
                  <div
                    key={call.id}
                    className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:shadow-md transition-all duration-200"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span
                            className={`text-xs px-2 py-0.5 rounded ${
                              call.status === 'success'
                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                            }`}
                          >
                            {call.status}
                          </span>
                        </div>
                        <div className="font-medium text-sm text-gray-700 dark:text-gray-300 mb-2">
                          {call.modelName}
                        </div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 space-y-1">
                          <div className="flex flex-wrap gap-4">
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
                              {call.duration}ms
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
                <div className="text-center text-gray-500 dark:text-gray-400 py-16">
                  <p className="text-base font-medium">
                    {t('monitoring.llmCalls.noData')}
                  </p>
                </div>
              )}
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
