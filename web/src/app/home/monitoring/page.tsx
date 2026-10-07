import React, {
  Suspense,
  useState,
  useEffect,
  useMemo,
  useCallback,
} from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  ChevronRight,
  ChevronDown,
  ExternalLink,
  RefreshCw,
  MessageSquare,
  Sparkles,
  CheckCircle2,
  Activity,
} from 'lucide-react';
import { TabState } from './components/TabState';
import SystemStatusCard from './components/overview-cards/SystemStatusCards';
import TrafficChart from './components/overview-cards/TrafficChart';
import MonitoringFilters from './components/filters/MonitoringFilters';
import TokenMonitoring from './components/TokenMonitoring';
import { ExportDropdown } from './components/ExportDropdown';
import { useMonitoringFilters } from './hooks/useMonitoringFilters';
import { useMonitoringData } from './hooks/useMonitoringData';
import { useFeedbackData } from './hooks/useFeedbackData';
import { ConversationTurnList } from './components/ConversationTurnList';
import { FeedbackStatsCards } from './components/FeedbackCard';
import { FeedbackList } from './components/FeedbackList';
import ExecutionOverviewCards from './components/overview-cards/ExecutionOverviewCards';
import ExecutionTable from './components/executions/ExecutionTable';
import ExecutionDetailSheet from './components/executions/ExecutionDetailSheet';
import { useExecutions } from './hooks/useExecutions';
import type {
  ExecutionModeFilter,
  ExecutionRow,
  ExecutionSourceFilter,
} from '@/app/infra/entities/api/monitoring-executions';
import { buildConversationTurns } from './utils/conversationTurns';
import { resolveCallTarget } from './utils/callLinks';
import { cn } from '@/lib/utils';
import { resolveMonitoringWindow } from './utils/dateUtils';
import { LoadingPage } from '@/components/ui/loading-spinner';
import { useCurrentWorkspace } from '@/app/infra/http';

function MonitoringPageContent() {
  const { t } = useTranslation();
  const currentWorkspace = useCurrentWorkspace();
  const canExport =
    currentWorkspace?.permissions.includes('data.export') ?? false;
  const { filterState, setSelectedBots, setSelectedPipelines, setTimeRange } =
    useMonitoringFilters();
  const { data, loading, error, refetch } = useMonitoringData(filterState);

  // Unified execution view (agent runs + pipeline queries). Its filters are
  // independent of the legacy message/model tabs.
  const [executionSource, setExecutionSource] =
    useState<ExecutionSourceFilter>('all');
  const [executionMode, setExecutionMode] =
    useState<ExecutionModeFilter>('all');
  const [executionStatus, setExecutionStatus] = useState<string>('all');
  const [executionOffset, setExecutionOffset] = useState(0);
  const [selectedExecution, setSelectedExecution] =
    useState<ExecutionRow | null>(null);
  const EXECUTIONS_PAGE_SIZE = 50;

  const {
    result: executionResult,
    loading: executionLoading,
    error: executionError,
    refetch: refetchExecutions,
  } = useExecutions({
    selectedBots: filterState.selectedBots,
    selectedPipelines: filterState.selectedPipelines,
    selectedAgents: [],
    source: executionSource,
    mode: executionMode,
    statusGroup: executionStatus,
    timeRange: filterState.timeRange,
    customDateRange: filterState.customDateRange,
    limit: EXECUTIONS_PAGE_SIZE,
    offset: executionOffset,
  });

  // Reset paging whenever the execution filters narrow the result set.
  useEffect(() => {
    setExecutionOffset(0);
  }, [
    executionSource,
    executionMode,
    executionStatus,
    filterState.selectedBots,
    filterState.selectedPipelines,
    filterState.timeRange,
    filterState.customDateRange,
  ]);

  // Counter to force feedbackTimeRange recomputation on manual refresh
  const [feedbackRefreshKey, setFeedbackRefreshKey] = useState(0);

  // Get time range for feedback data
  const feedbackTimeRange = useMemo(
    () =>
      resolveMonitoringWindow(
        filterState.timeRange,
        filterState.customDateRange,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [filterState.timeRange, filterState.customDateRange, feedbackRefreshKey],
  );

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
    refetchExecutions();
    setFeedbackRefreshKey((k) => k + 1);
  }, [refetch, refetchExecutions]);

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
  const [activeTab, setActiveTab] = useState<string>('executions');

  // Ids the message list actually holds: a call may name a record that the
  // current window does not contain, and a dead link is worse than no link.
  const messageIds = useMemo(
    () => new Set(data?.messages.map((message) => message.id) ?? []),
    [data?.messages],
  );

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
          <Card className="flex flex-col gap-3 p-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-4 sm:p-4">
            <MonitoringFilters
              selectedBots={filterState.selectedBots}
              selectedPipelines={filterState.selectedPipelines}
              timeRange={filterState.timeRange}
              onBotsChange={setSelectedBots}
              onPipelinesChange={setSelectedPipelines}
              onTimeRangeChange={setTimeRange}
              source={executionSource}
              onSourceChange={setExecutionSource}
              mode={executionMode}
              onModeChange={setExecutionMode}
              statusGroup={executionStatus}
              onStatusGroupChange={setExecutionStatus}
            />
            <div className="flex items-center gap-2">
              {canExport && <ExportDropdown filterState={filterState} />}
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
          </Card>
        </div>
      </div>

      {/* Content Area */}
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>{t('monitoring.loadError')}</AlertTitle>
          <AlertDescription className="mt-2">
            <Button variant="outline" size="sm" onClick={handleRefresh}>
              {t('common.retry')}
            </Button>
          </AlertDescription>
        </Alert>
      ) : (
        <div className="relative z-0 flex flex-col gap-6 pb-4 pt-3">
          {/* Overview Section: the execution metrics and the runtime status share
              one grid, so a card always lands in the same row regardless of how
              many metrics reported. */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
            <ExecutionOverviewCards
              summary={executionResult?.summary ?? null}
              loading={executionLoading}
              activeSessions={data?.overview?.activeSessions ?? null}
            />
            <SystemStatusCard refreshKey={feedbackRefreshKey} />
          </div>

          {/* Traffic Chart */}
          <TrafficChart traffic={data?.traffic} loading={loading} />

          {/* Tabs Section */}
          {!loading && data && (
            <div
              className="text-sm text-muted-foreground space-y-1"
              role="status"
            >
              {data.totalCount.messages > data.messages.length && (
                <p>
                  {t('monitoring.partialMessages', {
                    shown: data.messages.length,
                    total: data.totalCount.messages,
                  })}
                </p>
              )}
              {data.totalCount.llmCalls + data.totalCount.embeddingCalls >
                data.modelCalls.length && (
                <p>
                  {t('monitoring.partialModelCalls', {
                    shown: data.modelCalls.length,
                    total:
                      data.totalCount.llmCalls + data.totalCount.embeddingCalls,
                  })}
                </p>
              )}
              {(data.totalCount.toolCalls ?? 0) > data.toolCalls.length && (
                <p>
                  {t('monitoring.partialToolCalls', {
                    shown: data.toolCalls.length,
                    total: data.totalCount.toolCalls,
                  })}
                </p>
              )}
              {data.totalCount.errors > data.errors.length && (
                <p>
                  {t('monitoring.partialErrors', {
                    shown: data.errors.length,
                    total: data.totalCount.errors,
                  })}
                </p>
              )}
            </div>
          )}
          {/* Detail records region: one fixed-height surface for every tab. Tab
              switches and expanded records scroll inside it, so the page never
              resizes and nothing below the fold is pushed out of view. */}
          <div className="bg-card flex h-[min(72vh,48rem)] min-h-[24rem] flex-col overflow-hidden rounded-xl border">
            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className="flex h-full min-h-0 w-full flex-col gap-0"
            >
              <div className="border-b px-3 pt-4 pb-3 sm:px-6">
                <TabsList className="h-12 w-full justify-start gap-1 overflow-x-auto p-1 sm:w-auto">
                  <TabsTrigger value="executions" className="px-3 py-2 sm:px-6">
                    {t('monitoring.execution.tabs.executions')}
                  </TabsTrigger>
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

              <TabsContent
                value="executions"
                className="m-0 flex min-h-0 flex-1 flex-col"
              >
                <p className="px-3 pt-4 text-sm text-muted-foreground sm:px-6">
                  {t('monitoring.execution.subtitle')}
                </p>

                {executionError ? (
                  <div className="px-3 pt-4 sm:px-6">
                    <Alert variant="destructive">
                      <AlertTitle>
                        {t('monitoring.execution.detail.loadError')}
                      </AlertTitle>
                      <AlertDescription className="mt-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleRefresh}
                        >
                          {t('common.retry')}
                        </Button>
                      </AlertDescription>
                    </Alert>
                  </div>
                ) : (
                  <>
                    <div className="min-h-0 flex-1 overflow-hidden px-3 pt-4 pb-4 sm:px-6">
                      {executionLoading ? (
                        <TabState loading rows={6} />
                      ) : (executionResult?.items.length ?? 0) === 0 ? (
                        <TabState
                          icon={<Activity className="h-12 w-12" />}
                          title={t('monitoring.execution.empty')}
                        />
                      ) : (
                        <ExecutionTable
                          rows={executionResult?.items ?? []}
                          selectedId={selectedExecution?.id}
                          onSelect={setSelectedExecution}
                        />
                      )}
                    </div>
                    {executionResult &&
                      executionResult.total > EXECUTIONS_PAGE_SIZE && (
                        <div className="flex flex-wrap items-center justify-between gap-2 border-t px-3 py-3 sm:px-6">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={executionOffset === 0}
                            onClick={() =>
                              setExecutionOffset(
                                Math.max(
                                  0,
                                  executionOffset - EXECUTIONS_PAGE_SIZE,
                                ),
                              )
                            }
                          >
                            {t('common.previous')}
                          </Button>
                          <span className="text-xs text-muted-foreground">
                            {executionOffset + 1}–
                            {Math.min(
                              executionOffset + EXECUTIONS_PAGE_SIZE,
                              executionResult.total,
                            )}{' '}
                            / {executionResult.total}
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={!executionResult.has_more}
                            onClick={() =>
                              setExecutionOffset(
                                executionOffset + EXECUTIONS_PAGE_SIZE,
                              )
                            }
                          >
                            {t('common.next')}
                          </Button>
                        </div>
                      )}
                  </>
                )}
              </TabsContent>

              <TabsContent
                value="messages"
                className="m-0 min-h-0 flex-1 overflow-y-auto p-3 sm:p-6"
              >
                <div>
                  {loading && <TabState loading rows={6} />}

                  {!loading && data && conversationTurns.length > 0 && (
                    <ConversationTurnList
                      turns={conversationTurns}
                      expandedTurnId={expandedTurnId}
                      onToggleTurn={toggleTurnExpand}
                    />
                  )}

                  {!loading && (!data || conversationTurns.length === 0) && (
                    <TabState
                      icon={<MessageSquare className="h-12 w-12" />}
                      title={t('monitoring.messageList.noMessages')}
                    />
                  )}
                </div>
              </TabsContent>

              <TabsContent
                value="modelCalls"
                className="m-0 min-h-0 flex-1 overflow-y-auto p-3 sm:p-6"
              >
                <div>
                  {loading && <TabState loading rows={6} />}

                  {!loading &&
                    data &&
                    data.modelCalls &&
                    data.modelCalls.length > 0 && (
                      <div className="space-y-4">
                        {data.modelCalls.map((call) => {
                          // A recorded call names the record it belongs to, so
                          // the whole card opens it; without a match the card
                          // stays static instead of pretending to be a link.
                          const target = resolveCallTarget(
                            call,
                            executionResult?.items ?? [],
                            messageIds,
                          );
                          const openTarget = () => {
                            if (!target) return;
                            if (target.kind === 'execution') {
                              setActiveTab('executions');
                              setSelectedExecution(target.row);
                              return;
                            }
                            jumpToMessage(target.id);
                          };
                          return (
                            <Card
                              key={call.id}
                              role={target ? 'button' : undefined}
                              tabIndex={target ? 0 : undefined}
                              aria-label={
                                target
                                  ? t('monitoring.execution.detail.openObject')
                                  : undefined
                              }
                              onClick={target ? openTarget : undefined}
                              onKeyDown={
                                target
                                  ? (
                                      event: React.KeyboardEvent<HTMLDivElement>,
                                    ) => {
                                      if (
                                        event.key === 'Enter' ||
                                        event.key === ' '
                                      ) {
                                        event.preventDefault();
                                        openTarget();
                                      }
                                    }
                                  : undefined
                              }
                              className={cn(
                                'gap-0 px-4 py-4 transition-all duration-200 sm:px-5 sm:py-5',
                                target &&
                                  'cursor-pointer hover:bg-muted/40 focus-visible:ring-ring/50 focus-visible:ring-[3px] focus-visible:outline-none',
                              )}
                            >
                              <div className="flex justify-between items-start mb-3">
                                <div className="flex-1">
                                  {/* The stored id is the owning record: a
                                      Pipeline's message, or an Agent run's id
                                      that the card itself opens. */}
                                  {call.messageId &&
                                    messageIds.has(call.messageId) && (
                                      <div className="flex items-center gap-2 mb-1">
                                        <span className="text-xs text-muted-foreground font-mono">
                                          Query ID: {call.messageId}
                                        </span>
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          className="h-5 px-1.5 text-xs"
                                          onClick={(event) => {
                                            // The card itself opens the call's
                                            // record; this button is the more
                                            // specific message target.
                                            event.stopPropagation();
                                            jumpToMessage(call.messageId!);
                                          }}
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
                                    <Badge
                                      variant="outline"
                                      className={
                                        call.modelType === 'llm'
                                          ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                                          : 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
                                      }
                                    >
                                      {call.modelType === 'llm'
                                        ? t('monitoring.modelCalls.llmModel')
                                        : t(
                                            'monitoring.modelCalls.embeddingModel',
                                          )}
                                    </Badge>
                                    {/* Call Type Badge for Embedding */}
                                    {call.modelType === 'embedding' &&
                                      call.callType && (
                                        <Badge
                                          variant="outline"
                                          className={
                                            call.callType === 'retrieve'
                                              ? 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200'
                                              : 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'
                                          }
                                        >
                                          {call.callType === 'retrieve'
                                            ? t(
                                                'monitoring.modelCalls.retrieveCall',
                                              )
                                            : t(
                                                'monitoring.modelCalls.embeddingCall',
                                              )}
                                        </Badge>
                                      )}
                                    {/* Status Badge */}
                                    <Badge
                                      variant="outline"
                                      className={
                                        call.status === 'success'
                                          ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                          : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                                      }
                                    >
                                      {call.status}
                                    </Badge>
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
                                      {call.modelType === 'llm' &&
                                        call.tokens && (
                                          <>
                                            <span>
                                              {t(
                                                'monitoring.llmCalls.inputTokens',
                                              )}
                                              : {call.tokens.input}
                                            </span>
                                            <span>
                                              {t(
                                                'monitoring.llmCalls.outputTokens',
                                              )}
                                              : {call.tokens.output}
                                            </span>
                                            <span>
                                              {t(
                                                'monitoring.llmCalls.totalTokens',
                                              )}
                                              : {call.tokens.total}
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
                                              ? call.queryText.substring(
                                                  0,
                                                  100,
                                                ) + '...'
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
                                <span className="ml-4 flex items-center gap-1 text-xs text-muted-foreground whitespace-nowrap">
                                  {call.timestamp.toLocaleString()}
                                  {target && (
                                    <ChevronRight className="h-4 w-4" />
                                  )}
                                </span>
                              </div>
                            </Card>
                          );
                        })}
                      </div>
                    )}

                  {!loading &&
                    (!data ||
                      !data.modelCalls ||
                      data.modelCalls.length === 0) && (
                      <TabState
                        icon={<Sparkles className="h-12 w-12" />}
                        title={t('monitoring.modelCalls.noData')}
                      />
                    )}
                </div>
              </TabsContent>

              <TabsContent
                value="tokens"
                className="m-0 min-h-0 flex-1 overflow-y-auto p-3 sm:p-6"
              >
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

              <TabsContent
                value="feedback"
                className="m-0 min-h-0 flex-1 overflow-y-auto p-3 sm:p-6"
              >
                <div>
                  {loading && <TabState loading rows={6} />}

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
                      <h3 className="text-lg font-semibold text-foreground mb-4">
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

              <TabsContent
                value="errors"
                className="m-0 min-h-0 flex-1 overflow-y-auto p-3 sm:p-6"
              >
                <div>
                  {loading && <TabState loading rows={6} />}

                  {!loading &&
                    data &&
                    data.errors &&
                    data.errors.length > 0 && (
                      <div className="space-y-4">
                        {data.errors.map((error) => (
                          <Card
                            key={error.id}
                            className="gap-0 overflow-hidden border-red-200 py-0 transition-all duration-200 dark:border-red-900"
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
                          </Card>
                        ))}
                      </div>
                    )}

                  {!loading &&
                    (!data || !data.errors || data.errors.length === 0) && (
                      <TabState
                        icon={
                          <CheckCircle2 className="h-12 w-12 text-green-500 dark:text-green-600" />
                        }
                        title={t('monitoring.errors.noErrors')}
                      />
                    )}
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      )}

      {/* Execution trace drawer */}
      <ExecutionDetailSheet
        row={selectedExecution}
        onClose={() => setSelectedExecution(null)}
      />
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
