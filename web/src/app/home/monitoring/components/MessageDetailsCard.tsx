'use client';

import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageDetails } from '../types/monitoring';

interface MessageDetailsCardProps {
  details: MessageDetails;
}

export function MessageDetailsCard({ details }: MessageDetailsCardProps) {
  const { t } = useTranslation();

  // Parse query variables JSON string
  const queryVariables = useMemo(() => {
    if (!details.message?.variables) return null;
    try {
      return JSON.parse(details.message.variables);
    } catch {
      return null;
    }
  }, [details.message?.variables]);

  return (
    <div className="space-y-4 pl-8 border-l-2 border-gray-200 dark:border-gray-700 ml-4">
      {/* Context Info Section */}
      {details.message && (
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center">
            <svg
              className="w-4 h-4 mr-2"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22ZM12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM11 7H13V9H11V7ZM11 11H13V17H11V11Z"></path>
            </svg>
            {t('monitoring.messageList.viewDetails')}
          </h4>

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            {details.message.platform && (
              <div className="bg-white dark:bg-gray-900 rounded p-2">
                <div className="text-gray-500 dark:text-gray-400">
                  {t('monitoring.messageList.platform')}
                </div>
                <div className="font-medium text-gray-900 dark:text-white">
                  {details.message.platform}
                </div>
              </div>
            )}
            {details.message.userId && (
              <div className="bg-white dark:bg-gray-900 rounded p-2">
                <div className="text-gray-500 dark:text-gray-400">
                  {t('monitoring.messageList.user')}
                </div>
                <div className="font-medium text-gray-900 dark:text-white truncate">
                  {details.message.userId}
                </div>
              </div>
            )}
            {details.message.runnerName && (
              <div className="bg-white dark:bg-gray-900 rounded p-2">
                <div className="text-gray-500 dark:text-gray-400">
                  {t('monitoring.messageList.runner')}
                </div>
                <div className="font-medium text-gray-900 dark:text-white">
                  {details.message.runnerName}
                </div>
              </div>
            )}
            <div className="bg-white dark:bg-gray-900 rounded p-2">
              <div className="text-gray-500 dark:text-gray-400">
                {t('monitoring.messageList.level')}
              </div>
              <div
                className={`font-medium ${
                  details.message.level === 'error'
                    ? 'text-red-600 dark:text-red-400'
                    : details.message.level === 'warning'
                      ? 'text-yellow-600 dark:text-yellow-400'
                      : 'text-gray-900 dark:text-white'
                }`}
              >
                {details.message.level.toUpperCase()}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* LLM Calls Section */}
      {details.llmCalls && details.llmCalls.length > 0 && (
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center">
            <svg
              className="w-4 h-4 mr-2"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12 2C17.52 2 22 6.48 22 12C22 17.52 17.52 22 12 22C6.48 22 2 17.52 2 12C2 6.48 6.48 2 12 2ZM12 20C16.42 20 20 16.42 20 12C20 7.58 16.42 4 12 4C7.58 4 4 7.58 4 12C4 16.42 7.58 20 12 20ZM13 12V7H11V14H17V12H13Z"></path>
            </svg>
            {t('monitoring.llmCalls.title')} ({details.llmCalls.length})
          </h4>

          {/* LLM Stats Summary */}
          <div className="grid grid-cols-3 gap-2 mb-3">
            <div className="bg-blue-50 dark:bg-blue-900/30 rounded p-2">
              <div className="text-xs text-blue-600 dark:text-blue-400">
                {t('monitoring.llmCalls.totalTokens')}
              </div>
              <div className="text-lg font-semibold text-blue-900 dark:text-blue-100">
                {details.llmStats.totalTokens.toLocaleString()}
              </div>
            </div>
            <div className="bg-green-50 dark:bg-green-900/30 rounded p-2">
              <div className="text-xs text-green-600 dark:text-green-400">
                {t('monitoring.llmCalls.avgDuration')}
              </div>
              <div className="text-lg font-semibold text-green-900 dark:text-green-100">
                {details.llmStats.averageDurationMs}ms
              </div>
            </div>
            <div className="bg-purple-50 dark:bg-purple-900/30 rounded p-2">
              <div className="text-xs text-purple-600 dark:text-purple-400">
                {t('monitoring.llmCalls.calls')}
              </div>
              <div className="text-lg font-semibold text-purple-900 dark:text-purple-100">
                {details.llmStats.totalCalls}
              </div>
            </div>
          </div>

          {/* Individual LLM Calls */}
          <div className="space-y-2">
            {details.llmCalls.map((call, index) => (
              <div
                key={call.id}
                className="bg-white dark:bg-gray-900 rounded p-2 text-sm"
              >
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <span className="font-medium text-gray-900 dark:text-white">
                      #{index + 1} {call.modelName}
                    </span>
                    <span
                      className={`ml-2 text-xs px-2 py-0.5 rounded ${
                        call.status === 'success'
                          ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                          : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                      }`}
                    >
                      {call.status}
                    </span>
                  </div>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {call.duration}ms
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs text-gray-600 dark:text-gray-400">
                  <div>
                    <span className="text-gray-500 dark:text-gray-500">
                      In:
                    </span>{' '}
                    {call.tokens.input.toLocaleString()}
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-500">
                      Out:
                    </span>{' '}
                    {call.tokens.output.toLocaleString()}
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-500">
                      Total:
                    </span>{' '}
                    {call.tokens.total.toLocaleString()}
                  </div>
                </div>
                {call.errorMessage && (
                  <div className="mt-2 text-xs text-red-600 dark:text-red-400">
                    {call.errorMessage}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Errors Section */}
      {details.errors && details.errors.length > 0 && (
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
          <h4 className="text-sm font-semibold text-red-700 dark:text-red-400 mb-3 flex items-center">
            <svg
              className="w-4 h-4 mr-2"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22ZM12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM11 15H13V17H11V15ZM11 7H13V13H11V7Z"></path>
            </svg>
            {t('monitoring.errors.title')} ({details.errors.length})
          </h4>
          <div className="space-y-2">
            {details.errors.map((error) => (
              <div
                key={error.id}
                className="bg-red-50 dark:bg-red-900/20 rounded p-2 text-sm"
              >
                <div className="font-medium text-red-900 dark:text-red-300 mb-1">
                  {error.errorType}
                </div>
                <div className="text-red-700 dark:text-red-400 text-xs mb-2">
                  {error.errorMessage}
                </div>
                {error.stackTrace && (
                  <details className="text-xs">
                    <summary className="cursor-pointer text-red-600 dark:text-red-500 hover:text-red-800 dark:hover:text-red-300">
                      {t('monitoring.errors.stackTrace')}
                    </summary>
                    <pre className="mt-2 p-2 bg-red-100 dark:bg-red-900/40 rounded overflow-x-auto text-xs">
                      {error.stackTrace}
                    </pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Query Variables Section - Only show for non-local-agent runners */}
      {queryVariables && Object.keys(queryVariables).length > 0 && details.message?.runnerName !== 'local-agent' && (
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center">
            <svg
              className="w-4 h-4 mr-2"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M4 18V14.3C4 13.4716 3.32843 12.8 2.5 12.8H2V11.2H2.5C3.32843 11.2 4 10.5284 4 9.7V6C4 4.34315 5.34315 3 7 3H8V5H7C6.44772 5 6 5.44772 6 6V9.7C6 10.7065 5.41099 11.5849 4.55132 12C5.41099 12.4151 6 13.2935 6 14.3V18C6 18.5523 6.44772 19 7 19H8V21H7C5.34315 21 4 19.6569 4 18ZM20 14.3V18C20 19.6569 18.6569 21 17 21H16V19H17C17.5523 19 18 18.5523 18 18V14.3C18 13.2935 18.589 12.4151 19.4487 12C18.589 11.5849 18 10.7065 18 9.7V6C18 5.44772 17.5523 5 17 5H16V3H17C18.6569 3 20 4.34315 20 6V9.7C20 10.5284 20.6716 11.2 21.5 11.2H22V12.8H21.5C20.6716 12.8 20 13.4716 20 14.3Z"></path>
            </svg>
            {t('monitoring.queryVariables.title')}
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            {Object.entries(queryVariables).map(([key, value]) => (
              <div key={key} className="bg-white dark:bg-gray-900 rounded p-2">
                <div className="text-gray-500 dark:text-gray-400">
                  {key}
                </div>
                <div className="font-medium text-gray-900 dark:text-white truncate" title={typeof value === 'string' ? value : JSON.stringify(value)}>
                  {value === null || value === undefined
                    ? <span className="text-gray-400 italic">null</span>
                    : typeof value === 'string'
                      ? (value || <span className="text-gray-400 italic">empty</span>)
                      : JSON.stringify(value)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No data message */}
      {(!details.llmCalls || details.llmCalls.length === 0) &&
        (!details.errors || details.errors.length === 0) &&
        (details.message?.runnerName === 'local-agent' || !queryVariables || Object.keys(queryVariables).length === 0) && (
          <div className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
            {t('monitoring.messageDetails.noData')}
          </div>
        )}
    </div>
  );
}
