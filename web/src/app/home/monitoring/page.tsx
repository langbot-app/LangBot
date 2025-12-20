'use client';

import React, { Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import OverviewCards from './components/overview-cards/OverviewCards';
import MonitoringFilters from './components/filters/MonitoringFilters';
import { useMonitoringFilters } from './hooks/useMonitoringFilters';
import { useMonitoringData } from './hooks/useMonitoringData';

function MonitoringPageContent() {
  const { t } = useTranslation();
  const { filterState, setSelectedBots, setSelectedPipelines, setTimeRange } =
    useMonitoringFilters();
  const { data, loading, refetch } = useMonitoringData(filterState);

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Overview Section */}
      <div>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            {t('monitoring.overview')}
          </h2>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={refetch}
              className="bg-white dark:bg-[#2a2a2e]"
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

        {/* Filters */}
        <MonitoringFilters
          selectedBots={filterState.selectedBots}
          selectedPipelines={filterState.selectedPipelines}
          timeRange={filterState.timeRange}
          onBotsChange={setSelectedBots}
          onPipelinesChange={setSelectedPipelines}
          onTimeRangeChange={setTimeRange}
        />

        <OverviewCards metrics={data?.overview || null} loading={loading} />
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
            <TabsTrigger value="sessions">
              {t('monitoring.tabs.sessions')}
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
                  <div className="space-y-2">
                    {data.messages.map((msg) => (
                      <div
                        key={msg.id}
                        className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                      >
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <span className="font-medium text-sm text-gray-700 dark:text-gray-300">
                              {msg.botName}
                            </span>
                            <span className="mx-2 text-gray-400">→</span>
                            <span className="text-sm text-gray-600 dark:text-gray-400">
                              {msg.pipelineName}
                            </span>
                          </div>
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {msg.timestamp.toLocaleString()}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-300">
                          {msg.messageContent}
                        </p>
                        <div className="mt-2 flex gap-2">
                          <span
                            className={`text-xs px-2 py-1 rounded ${
                              msg.status === 'success'
                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                : msg.status === 'error'
                                  ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                                  : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                            }`}
                          >
                            {msg.status}
                          </span>
                          <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300">
                            {msg.level}
                          </span>
                        </div>
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
                  <div className="space-y-2">
                    {data.llmCalls.map((call) => (
                      <div
                        key={call.id}
                        className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                      >
                        <div className="flex justify-between items-start">
                          <div>
                            <span className="font-medium text-sm text-gray-700 dark:text-gray-300">
                              {call.modelName}
                            </span>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                              {call.tokens.total} tokens • {call.duration}ms
                              {call.cost && ` • $${call.cost.toFixed(4)}`}
                            </p>
                          </div>
                          <span className="text-xs text-gray-500 dark:text-gray-400">
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

          <TabsContent value="sessions" className="mt-4">
            <div className="bg-white dark:bg-[#2a2a2e] rounded-lg border border-gray-200 dark:border-gray-700 p-6">
              {loading && (
                <div className="text-center text-gray-500 dark:text-gray-400">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-white"></div>
                  <p className="mt-2 text-sm">{t('common.loading')}</p>
                </div>
              )}

              {!loading &&
                data &&
                data.sessions &&
                data.sessions.length > 0 && (
                  <div className="space-y-2">
                    {data.sessions.map((session) => (
                      <div
                        key={session.sessionId}
                        className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                      >
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <span className="font-medium text-sm text-gray-700 dark:text-gray-300">
                              {session.botName}
                            </span>
                            <span className="mx-2 text-gray-400">→</span>
                            <span className="text-sm text-gray-600 dark:text-gray-400">
                              {session.pipelineName}
                            </span>
                          </div>
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {session.lastActivity.toLocaleString()}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {session.messageCount} messages • Session ID:{' '}
                          {session.sessionId.substring(0, 8)}...
                        </p>
                      </div>
                    ))}
                  </div>
                )}

              {!loading &&
                (!data || !data.sessions || data.sessions.length === 0) && (
                  <div className="text-center text-gray-500 dark:text-gray-400">
                    <p className="text-lg font-medium">
                      {t('monitoring.sessions.noSessions')}
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
                <div className="space-y-2">
                  {data.errors.map((error) => (
                    <div
                      key={error.id}
                      className="border border-red-200 dark:border-red-700 rounded-lg p-4 bg-red-50 dark:bg-red-900/10"
                    >
                      <div className="flex justify-between items-start mb-2">
                        <div>
                          <span className="font-medium text-sm text-red-700 dark:text-red-300">
                            {error.errorType}
                          </span>
                          <span className="mx-2 text-gray-400">•</span>
                          <span className="text-sm text-gray-600 dark:text-gray-400">
                            {error.botName} → {error.pipelineName}
                          </span>
                        </div>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {error.timestamp.toLocaleString()}
                        </span>
                      </div>
                      <p className="text-sm text-gray-700 dark:text-gray-300">
                        {error.errorMessage}
                      </p>
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
