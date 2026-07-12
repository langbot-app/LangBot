import React, { Suspense, useState, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import {
  ChevronRight,
  ChevronDown,
  ExternalLink,
  RefreshCw,
  MessageSquare,
  Sparkles,
  CheckCircle2,
} from 'lucide-react';
import OverviewCards from './components/overview-cards/OverviewCards';
import MonitoringFilters from './components/filters/MonitoringFilters';
import TokenMonitoring from './components/TokenMonitoring';
import { ExportDropdown } from './components/ExportDropdown';
import { useMonitoringFilters } from './hooks/useMonitoringFilters';
import { useMonitoringData } from './hooks/useMonitoringData';
import { useFeedbackData } from './hooks/useFeedbackData';
import { ConversationTurnList } from './components/ConversationTurnList';
import { FeedbackStatsCards } from './components/FeedbackCard';
import { FeedbackList } from './components/FeedbackList';
import { buildConversationTurns } from './utils/conversationTurns';
import { LoadingSpinner, LoadingPage } from '@/components/ui/loading-spinner';

function MonitoringPageContent() {
  const { t } = useTranslation();
  const { filterState, setSelectedBots, setSelectedPipelines, setTimeRange } =
    useMonitoringFilters();
  const { data, loading, refetch } = useMonitoringData(filterState);

  // Counter to force feedbackTimeRange recomputation on manual refresh
  const [feedbackRefreshKey, setFeedbackRefreshKey] = useState(0);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterState.timeRange, filterState.customDateRange, feedbackRefreshKey]);

  // Feedback data hook
  const {
    feedback: feedbackList,
    stats: feedbackStats,
    loading: feedbackLoading,
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

  // Combined refresh handler for both monitoring and feedback data
  const handleRefresh = useCallback(() => {
    refetch();
    setFeedbackRefreshKey((k) => k + 1);
  }, [refetch]);

  const conversationTurns = useMemo(
    () =>
      buildConversationTurns(
        data?.messages || [],
        data?.llmCalls || [],
        data?.errors || [],
        data?.toolCalls || [],
      ),
    [data?.messages, data?.llmCalls, data?.errors, data?.toolCalls],
  );

  // State for expanded errors
  const [expandedErrorId, setExpandedErrorId] = useState<string | null>(null);
  const [expandedTurnId, setExpandedTurnId] = useState<string | null>(null);

  // State for controlled tabs
  const [activeTab, setActiveTab] = useState<string>('messages');

  // Function to jump to a message record
  const jumpToMessage = (messageId: string) => {
    setActiveTab('messages');
    setTimeout(() => {
      const turn = conversationTurns.find((item) =>
        item.messages.some((message) => message.id === messageId),
      );
      setExpandedTurnId(turn?.id ?? messageId);
    }, 100);
  };

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

  return (
    <div className="w-full h-full overflow-y-auto overflow-x-hidden">
      {/* Filters and Refresh Button - Sticky */}
      <div className="sticky top-0 z-10 -mt-1 pb-5 pt-1 bg-background">
        <div>
          <div className="flex flex-col gap-3 p-3 bg-card rounded-xl border sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-4 sm:p-4">
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
                onClick={handleRefresh}
                className="flex-1 shadow-sm sm:flex-shrink-0 sm:flex-none"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                {t('monitoring.refreshData')}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className="relative z-0 flex flex-col gap-6 pb-4 pt-3">
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
            <div className="px-3 pt-4 sm:px-6">
              <TabsList className="h-12 w-full justify-start gap-1 overflow-x-auto p-1 sm:w-auto">
                <TabsTrigger value="messages" className="px-3 py-2 sm:px-6">
                  {t('monitoring.tabs.messages')}
                </TabsTrigger>
                <TabsTrigger value="modelCalls" className="px-3 py-2 sm:px-6">
                  {t('monitoring.tabs.modelCalls')}
                </TabsTrigger>
                <TabsTrigger value="tokens" className="px-3 py-2 sm:px-6">
                  {t('monitoring.tabs.tokens')}
                </TabsTrigger>
                <TabsTrigger value="feedback" className="px-3 py-2 sm:px-6">
                  {t('monitoring.tabs.feedback')}
                </TabsTrigger>
                <TabsTrigger value="errors" className="px-3 py-2 sm:px-6">
                  {t('monitoring.tabs.errors')}
                </TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="messages" className="p-3 m-0 sm:p-6">
              <div>
                {loading && (
                  <div className="py-12 flex justify-center">
                    <LoadingSpinner
                      text={t('monitoring.messageList.loading')}
                    />
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
                  <div className="flex flex-col items-center justify-center text-muted-foreground py-16 gap-2">
                    <MessageSquare className="h-[3rem] w-[3rem]" />
                    <div className="text-sm">
                      {t('monitoring.messageList.noMessages')}
                    </div>
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="modelCalls" className="p-3 m-0 sm:p-6">
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
                          className="border rounded-xl p-3 transition-all duration-200 sm:p-5"
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
                      <Sparkles className="h-[3rem] w-[3rem]" />
                      <div className="text-sm">
                        {t('monitoring.modelCalls.noData')}
                      </div>
                    </div>
                  )}
              </div>
            </TabsContent>

            <TabsContent value="tokens" className="p-3 m-0 sm:p-6">
              <TokenMonitoring
                botIds={
                  filterState.selectedBots.length > 0
                    ? filterState.selectedBots
                    : undefined
                }
                pipelineIds={
                  filterState.selectedPipelines.length > 0
                    ? filterState.selectedPipelines
                    : undefined
                }
                startTime={feedbackTimeRange.startTime}
                endTime={feedbackTimeRange.endTime}
                refreshKey={feedbackRefreshKey}
              />
            </TabsContent>

            <TabsContent value="feedback" className="p-3 m-0 sm:p-6">
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

            <TabsContent value="errors" className="p-3 m-0 sm:p-6">
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
                          className="p-3 cursor-pointer hover:bg-red-50 dark:hover:bg-red-950/50 transition-colors bg-red-50/50 dark:bg-red-950/30 sm:p-5"
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
                      <CheckCircle2 className="h-[3rem] w-[3rem] text-green-500 dark:text-green-600" />
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
