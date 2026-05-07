import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Info, Clock, AlertCircle, Braces } from 'lucide-react';
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
    <div className="space-y-4 pl-8 border-l-2 border-border ml-4">
      {/* Context Info Section */}
      {details.message && (
        <div className="bg-muted rounded-lg p-3">
          <h4 className="text-sm font-semibold text-foreground mb-3 flex items-center">
            <Info className="w-4 h-4 mr-2" />
            {t('monitoring.messageList.viewDetails')}
          </h4>

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            {details.message.platform && (
              <div className="bg-background rounded p-2">
                <div className="text-muted-foreground">
                  {t('monitoring.messageList.platform')}
                </div>
                <div className="font-medium text-foreground">
                  {details.message.platform}
                </div>
              </div>
            )}
            {details.message.userId && (
              <div className="bg-background rounded p-2">
                <div className="text-muted-foreground">
                  {t('monitoring.messageList.user')}
                </div>
                <div className="font-medium text-foreground truncate">
                  {details.message.userId}
                </div>
              </div>
            )}
            {details.message.runnerName && (
              <div className="bg-background rounded p-2">
                <div className="text-muted-foreground">
                  {t('monitoring.messageList.runner')}
                </div>
                <div className="font-medium text-foreground">
                  {details.message.runnerName}
                </div>
              </div>
            )}
            <div className="bg-background rounded p-2">
              <div className="text-muted-foreground">
                {t('monitoring.messageList.level')}
              </div>
              <div
                className={`font-medium ${
                  details.message.level === 'error'
                    ? 'text-red-600 dark:text-red-400'
                    : details.message.level === 'warning'
                      ? 'text-yellow-600 dark:text-yellow-400'
                      : 'text-foreground'
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
        <div className="bg-muted rounded-lg p-3">
          <h4 className="text-sm font-semibold text-foreground mb-3 flex items-center">
            <Clock className="w-4 h-4 mr-2" />
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
              <div key={call.id} className="bg-background rounded p-2 text-sm">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <span className="font-medium text-foreground">
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
                  <span className="text-xs text-muted-foreground">
                    {call.duration}ms
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                  <div>
                    <span className="text-muted-foreground">In:</span>{' '}
                    {call.tokens.input.toLocaleString()}
                  </div>
                  <div>
                    <span className="text-muted-foreground">Out:</span>{' '}
                    {call.tokens.output.toLocaleString()}
                  </div>
                  <div>
                    <span className="text-muted-foreground">Total:</span>{' '}
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
        <div className="bg-muted rounded-lg p-3">
          <h4 className="text-sm font-semibold text-red-700 dark:text-red-400 mb-3 flex items-center">
            <AlertCircle className="w-4 h-4 mr-2" />
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
      {queryVariables &&
        Object.keys(queryVariables).length > 0 &&
        details.message?.runnerName !== 'local-agent' && (
          <div className="bg-muted rounded-lg p-3">
            <h4 className="text-sm font-semibold text-foreground mb-3 flex items-center">
              <Braces className="w-4 h-4 mr-2" />
              {t('monitoring.queryVariables.title')}
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              {Object.entries(queryVariables).map(([key, value]) => (
                <div key={key} className="bg-background rounded p-2">
                  <div className="text-muted-foreground">{key}</div>
                  <div
                    className="font-medium text-foreground truncate"
                    title={
                      typeof value === 'string' ? value : JSON.stringify(value)
                    }
                  >
                    {value === null || value === undefined ? (
                      <span className="text-muted-foreground italic">null</span>
                    ) : typeof value === 'string' ? (
                      value || (
                        <span className="text-muted-foreground italic">
                          empty
                        </span>
                      )
                    ) : (
                      JSON.stringify(value)
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

      {/* No data message */}
      {(!details.llmCalls || details.llmCalls.length === 0) &&
        (!details.errors || details.errors.length === 0) &&
        (details.message?.runnerName === 'local-agent' ||
          !queryVariables ||
          Object.keys(queryVariables).length === 0) && (
          <div className="text-sm text-muted-foreground text-center py-4">
            {t('monitoring.messageDetails.noData')}
          </div>
        )}
    </div>
  );
}
