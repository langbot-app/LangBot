import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import {
  ChevronRight,
  ChevronDown,
  ExternalLink,
  RefreshCw,
  MessageCircle,
  CheckCircle2,
  Monitor,
} from 'lucide-react';
import { useMonitoringData } from '@/app/home/monitoring/hooks/useMonitoringData';
import { ConversationTurnList } from '@/app/home/monitoring/components/ConversationTurnList';
import { buildConversationTurns } from '@/app/home/monitoring/utils/conversationTurns';
import { LoadingSpinner } from '@/components/ui/loading-spinner';

interface PipelineMonitoringTabProps {
  pipelineId: string;
  onNavigateToMonitoring?: () => void;
}

export default function PipelineMonitoringTab({
  pipelineId,
  onNavigateToMonitoring,
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

  const conversationTurns = useMemo(
    () =>
      data
        ? buildConversationTurns(
            data.messages,
            data.llmCalls,
            data.errors,
            data.toolCalls,
          )
        : [],
    [data],
  );
  const [expandedTurnId, setExpandedTurnId] = useState<string | null>(null);
  const [expandedErrorId, setExpandedErrorId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('messages');

  const toggleTurnExpand = (turnId: string) => {
    setExpandedTurnId((current) => (current === turnId ? null : turnId));
  };

  const toggleErrorExpand = (errorId: string) => {
    if (expandedErrorId === errorId) {
      setExpandedErrorId(null);
    } else {
      setExpandedErrorId(errorId);
    }
  };

  const jumpToMessage = (messageId: string) => {
    setActiveTab('messages');

    const turn = conversationTurns.find((item) =>
      item.messages.some((message) => message.id === messageId),
    );

    if (turn) {
      setExpandedTurnId(turn.id);
    }
  };

  return (
    <div className="w-full h-full flex flex-col">
      {/* Header with refresh button */}
      <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-200 dark:border-gray-700">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {t('pipelines.monitoring.description')}
        </p>
        <div className="flex items-center gap-2">
          {onNavigateToMonitoring && (
            <Button
              variant="outline"
              size="sm"
              onClick={onNavigateToMonitoring}
              className="bg-white dark:bg-[#2a2a2e] hover:bg-gray-50 dark:hover:bg-gray-800 border-gray-300 dark:border-gray-600"
            >
              <ExternalLink className="w-4 h-4 mr-2" />
              {t('pipelines.monitoring.detailedLogs')}
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={refetch}
            className="bg-white dark:bg-[#2a2a2e] hover:bg-gray-50 dark:hover:bg-gray-800 border-gray-300 dark:border-gray-600"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            {t('monitoring.refreshData')}
          </Button>
        </div>
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
              {data.overview.successRate.toFixed(1)}%
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

            {!loading && data && conversationTurns.length > 0 && (
              <ConversationTurnList
                turns={conversationTurns}
                expandedTurnId={expandedTurnId}
                onToggleTurn={toggleTurnExpand}
              />
            )}

            {!loading && (!data || conversationTurns.length === 0) && (
              <div className="text-center text-gray-500 dark:text-gray-400 py-16">
                <MessageCircle className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
                <p className="text-base font-medium">
                  {t('monitoring.messageList.noMessages')}
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
                  <CheckCircle2 className="w-16 h-16 mx-auto mb-4 text-green-300 dark:text-green-600" />
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
                  <Monitor className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
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
