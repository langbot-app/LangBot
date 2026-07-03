import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  Bot,
  ChevronDown,
  ChevronRight,
  Clock,
  Cpu,
  Hash,
  User,
  Wrench,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { MessageContentRenderer } from './MessageContentRenderer';
import {
  ConversationTurn,
  hasRenderableMessageContent,
} from '../utils/conversationTurns';
import { MonitoringMessage } from '../types/monitoring';

interface ConversationTurnListProps {
  turns: ConversationTurn[];
  expandedTurnId: string | null;
  onToggleTurn: (turnId: string) => void;
}

function shortId(id?: string) {
  if (!id) return '-';
  if (id.length <= 12) return id;
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}

function formatDuration(ms: number) {
  if (!ms) return '0ms';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function truncateDetail(value?: string) {
  if (!value) return '';
  return value.length > 1200 ? `${value.slice(0, 1200)}...` : value;
}

function roleLabel(message: MonitoringMessage | undefined) {
  const role = message?.role?.toLowerCase();
  if (role === 'assistant') return 'assistant';
  if (role === 'user') return 'user';
  return 'message';
}

function statusClass(level: ConversationTurn['level']) {
  if (level === 'error') {
    return 'border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300';
  }
  if (level === 'warning') {
    return 'border-yellow-200 bg-yellow-50 text-yellow-700 dark:border-yellow-900 dark:bg-yellow-950/40 dark:text-yellow-300';
  }
  return 'border-green-200 bg-green-50 text-green-700 dark:border-green-900 dark:bg-green-950/40 dark:text-green-300';
}

function Metric({
  icon,
  label,
  tone = 'default',
}: {
  icon: React.ReactNode;
  label: string;
  tone?: 'default' | 'error';
}) {
  return (
    <span
      className={cn(
        'inline-flex h-7 items-center gap-1.5 rounded-md border px-2 text-xs font-medium',
        tone === 'error'
          ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300'
          : 'border-border bg-background text-muted-foreground',
      )}
    >
      {icon}
      {label}
    </span>
  );
}

function MetaItem({ label, value }: { label: string; value?: string }) {
  return (
    <div className="min-w-0 rounded-md bg-background px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="truncate text-sm font-medium text-foreground">
        {value || '-'}
      </div>
    </div>
  );
}

function MessageLane({
  label,
  icon,
  content,
  empty,
  maxLines,
}: {
  label: string;
  icon: React.ReactNode;
  content?: string;
  empty: string;
  maxLines: number;
}) {
  return (
    <div className="grid grid-cols-[5.25rem_minmax(0,1fr)] items-start gap-3 text-sm sm:grid-cols-[6rem_minmax(0,1fr)]">
      <div className="flex h-7 items-center gap-1.5 text-xs font-medium text-muted-foreground">
        {icon}
        <span>{label}</span>
      </div>
      <div className="min-w-0 rounded-md bg-muted/45 px-3 py-2 text-foreground">
        {content && hasRenderableMessageContent(content) ? (
          <MessageContentRenderer content={content} maxLines={maxLines} />
        ) : (
          <span className="italic text-muted-foreground">{empty}</span>
        )}
      </div>
    </div>
  );
}

function ExpandedMessage({
  message,
  label,
}: {
  message: MonitoringMessage;
  label: string;
}) {
  return (
    <div className="border-t border-border/70 py-3 first:border-t-0 first:pt-0 last:pb-0">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span className="rounded-md bg-muted px-2 py-1 font-medium text-foreground">
          {label}
        </span>
        <span>{message.timestamp.toLocaleString()}</span>
        <span className="font-mono">ID: {shortId(message.id)}</span>
      </div>
      <div className="text-sm leading-6 text-foreground">
        <MessageContentRenderer content={message.messageContent} maxLines={4} />
      </div>
    </div>
  );
}

export function ConversationTurnList({
  turns,
  expandedTurnId,
  onToggleTurn,
}: ConversationTurnListProps) {
  const { t } = useTranslation();
  const [expandedToolCallIds, setExpandedToolCallIds] = React.useState<
    Record<string, boolean>
  >({});

  const toggleToolCallDetails = (toolCallKey: string) => {
    setExpandedToolCallIds((previous) => ({
      ...previous,
      [toolCallKey]: !previous[toolCallKey],
    }));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span className="font-medium text-foreground">
          {t('monitoring.messageList.turns', {
            defaultValue: '{{count}} 轮对话',
            count: turns.length,
          })}
        </span>
      </div>

      {turns.map((turn) => {
        const expanded = expandedTurnId === turn.id;
        const firstAssistant = turn.assistantMessages[0];
        const assistantOverflow = Math.max(
          turn.assistantMessages.length - 1,
          0,
        );

        return (
          <div
            key={turn.id}
            className={cn(
              'overflow-hidden rounded-xl border bg-card transition-colors',
              turn.level === 'error' && 'border-red-200 dark:border-red-900',
            )}
          >
            <div
              role="button"
              tabIndex={0}
              className="cursor-pointer p-3 outline-none transition-colors hover:bg-accent/60 focus-visible:ring-2 focus-visible:ring-ring sm:p-5"
              onClick={() => onToggleTurn(turn.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  onToggleTurn(turn.id);
                }
              }}
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="mb-2 flex min-w-0 items-center gap-2">
                    {expanded ? (
                      <ChevronDown className="h-5 w-5 shrink-0 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-5 w-5 shrink-0 text-muted-foreground" />
                    )}
                    <span className="truncate font-mono text-xs text-muted-foreground">
                      Turn: {shortId(turn.id)}
                    </span>
                  </div>

                  <div className="mb-3 flex min-w-0 flex-wrap items-center gap-2">
                    <span className="truncate text-sm font-medium text-foreground">
                      {turn.botName}
                    </span>
                    <span className="text-muted-foreground">→</span>
                    <span className="truncate text-sm text-muted-foreground">
                      {turn.pipelineName}
                    </span>
                    {turn.runnerName && (
                      <>
                        <span className="text-muted-foreground">→</span>
                        <span className="truncate text-sm text-muted-foreground">
                          {turn.runnerName}
                        </span>
                      </>
                    )}
                  </div>

                  <div className="space-y-2">
                    <MessageLane
                      label={t('monitoring.messageList.userMessage', {
                        defaultValue: '用户',
                      })}
                      icon={<User className="h-3.5 w-3.5" />}
                      content={turn.userMessage?.messageContent}
                      empty={t('monitoring.messageList.noUserMessage', {
                        defaultValue: '未记录用户输入',
                      })}
                      maxLines={2}
                    />
                    <MessageLane
                      label={
                        assistantOverflow > 0
                          ? t('monitoring.messageList.assistantMessageCount', {
                              defaultValue: '助手 +{{count}}',
                              count: assistantOverflow,
                            })
                          : t('monitoring.messageList.assistantMessage', {
                              defaultValue: '助手',
                            })
                      }
                      icon={<Bot className="h-3.5 w-3.5" />}
                      content={firstAssistant?.messageContent}
                      empty={t('monitoring.messageList.noAssistantMessage', {
                        defaultValue: '未记录助手回复',
                      })}
                      maxLines={2}
                    />
                  </div>
                </div>

                <div className="flex shrink-0 flex-col gap-2 lg:items-end">
                  <div className="text-xs text-muted-foreground">
                    {turn.lastActivityAt.toLocaleString()}
                  </div>
                  <div
                    className={cn(
                      'inline-flex h-7 items-center rounded-md border px-2 text-xs font-medium',
                      statusClass(turn.level),
                    )}
                  >
                    {turn.level}
                  </div>
                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    <Metric
                      icon={<Cpu className="h-3.5 w-3.5" />}
                      label={`${turn.llmCalls.length} LLM`}
                    />
                    {turn.toolCalls.length > 0 && (
                      <Metric
                        icon={<Wrench className="h-3.5 w-3.5" />}
                        label={`${turn.toolCalls.length} tools`}
                      />
                    )}
                    <Metric
                      icon={<Hash className="h-3.5 w-3.5" />}
                      label={`${turn.totalTokens.toLocaleString()} tokens`}
                    />
                    <Metric
                      icon={<Clock className="h-3.5 w-3.5" />}
                      label={formatDuration(turn.totalDuration)}
                    />
                    {turn.errors.length > 0 && (
                      <Metric
                        icon={<AlertCircle className="h-3.5 w-3.5" />}
                        label={`${turn.errors.length} errors`}
                        tone="error"
                      />
                    )}
                  </div>
                </div>
              </div>
            </div>

            {expanded && (
              <div className="border-t bg-muted/40 p-3 sm:p-5">
                <div className="space-y-5 border-l-2 border-border pl-4 sm:pl-6">
                  <div className="grid grid-cols-2 gap-2 lg:grid-cols-5">
                    <MetaItem
                      label={t('monitoring.messageList.platform', {
                        defaultValue: '平台',
                      })}
                      value={turn.platform}
                    />
                    <MetaItem
                      label={t('monitoring.messageList.user', {
                        defaultValue: '用户',
                      })}
                      value={turn.userName || turn.userId}
                    />
                    <MetaItem
                      label={t('monitoring.messageList.runner', {
                        defaultValue: '执行器',
                      })}
                      value={turn.runnerName}
                    />
                    <MetaItem
                      label={t('monitoring.sessions.sessionId', {
                        defaultValue: '会话 ID',
                      })}
                      value={turn.sessionId}
                    />
                    <MetaItem
                      label={t('monitoring.messageList.messageCount', {
                        defaultValue: '消息数',
                      })}
                      value={String(turn.messages.length)}
                    />
                  </div>

                  <section>
                    <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                      <Bot className="h-4 w-4" />
                      {t('monitoring.messageList.conversationTrace', {
                        defaultValue: '消息链路',
                      })}
                    </h4>
                    <div className="rounded-lg bg-background px-3 py-3">
                      {turn.messages.map((message) => (
                        <ExpandedMessage
                          key={message.id}
                          message={message}
                          label={t(
                            `monitoring.messageList.roles.${roleLabel(message)}`,
                            {
                              defaultValue:
                                roleLabel(message) === 'assistant'
                                  ? '助手'
                                  : roleLabel(message) === 'user'
                                    ? '用户'
                                    : '消息',
                            },
                          )}
                        />
                      ))}
                    </div>
                  </section>

                  <section>
                    <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                      <Cpu className="h-4 w-4" />
                      {t('monitoring.llmCalls.title', {
                        defaultValue: 'LLM 调用',
                      })}{' '}
                      ({turn.llmCalls.length})
                    </h4>

                    <div className="grid grid-cols-3 gap-2">
                      <MetaItem
                        label={t('monitoring.llmCalls.totalTokens', {
                          defaultValue: '总 Token',
                        })}
                        value={turn.totalTokens.toLocaleString()}
                      />
                      <MetaItem
                        label={t('monitoring.llmCalls.inputTokens', {
                          defaultValue: '输入 Token',
                        })}
                        value={turn.inputTokens.toLocaleString()}
                      />
                      <MetaItem
                        label={t('monitoring.llmCalls.duration', {
                          defaultValue: '耗时',
                        })}
                        value={formatDuration(turn.totalDuration)}
                      />
                    </div>

                    <div className="mt-3 rounded-lg bg-background px-3 py-3">
                      {turn.llmCalls.length > 0 ? (
                        turn.llmCalls.map((call, index) => (
                          <div
                            key={call.id}
                            className="border-t border-border/70 py-3 first:border-t-0 first:pt-0 last:pb-0"
                          >
                            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                              <div className="flex min-w-0 flex-wrap items-center gap-2">
                                <span className="text-sm font-medium text-foreground">
                                  #{index + 1} {call.modelName}
                                </span>
                                <span
                                  className={cn(
                                    'rounded-md px-2 py-1 text-xs font-medium',
                                    call.status === 'success'
                                      ? 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300'
                                      : 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300',
                                  )}
                                >
                                  {call.status}
                                </span>
                              </div>
                              <span className="text-xs text-muted-foreground">
                                {formatDuration(call.duration)}
                              </span>
                            </div>
                            <div className="flex flex-wrap gap-x-8 gap-y-1 text-xs text-muted-foreground">
                              <span>In: {call.tokens.input}</span>
                              <span>Out: {call.tokens.output}</span>
                              <span>Total: {call.tokens.total}</span>
                              <span className="font-mono">
                                ID: {shortId(call.id)}
                              </span>
                            </div>
                            {call.errorMessage && (
                              <div className="mt-2 whitespace-pre-wrap break-words text-xs text-red-600 dark:text-red-400">
                                {call.errorMessage}
                              </div>
                            )}
                          </div>
                        ))
                      ) : (
                        <div className="py-4 text-center text-sm text-muted-foreground">
                          {t('monitoring.messageList.noLlmCalls', {
                            defaultValue: '未记录模型调用',
                          })}
                        </div>
                      )}
                    </div>
                  </section>

                  <section>
                    <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                      <Wrench className="h-4 w-4" />
                      {t('monitoring.toolCalls.title', {
                        defaultValue: '工具调用',
                      })}{' '}
                      ({turn.toolCalls.length})
                    </h4>

                    <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
                      <MetaItem
                        label={t('monitoring.toolCalls.totalCalls', {
                          defaultValue: '调用次数',
                        })}
                        value={String(turn.toolCalls.length)}
                      />
                      <MetaItem
                        label={t('monitoring.toolCalls.duration', {
                          defaultValue: '工具耗时',
                        })}
                        value={formatDuration(turn.totalToolDuration)}
                      />
                      <MetaItem
                        label={t('monitoring.toolCalls.errorCalls', {
                          defaultValue: '失败次数',
                        })}
                        value={String(
                          turn.toolCalls.filter(
                            (call) => call.status === 'error',
                          ).length,
                        )}
                      />
                    </div>

                    <div className="mt-3 rounded-lg bg-background px-3 py-3">
                      {turn.toolCalls.length > 0 ? (
                        turn.toolCalls.map((call, index) => {
                          const toolCallKey = `${turn.id}:${call.id}`;
                          const hasToolDetails = Boolean(
                            call.arguments || call.result || call.errorMessage,
                          );
                          const expandedToolCall = Boolean(
                            expandedToolCallIds[toolCallKey],
                          );
                          const detailsId = `monitoring-tool-call-details-${call.id}`;

                          return (
                            <div
                              key={call.id}
                              className="border-t border-border/70 py-2 first:border-t-0 first:pt-0 last:pb-0"
                            >
                              <button
                                type="button"
                                className={cn(
                                  'flex w-full items-start justify-between gap-3 rounded-md px-2 py-2 text-left outline-none transition-colors',
                                  hasToolDetails &&
                                    'cursor-pointer hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring',
                                )}
                                aria-expanded={
                                  hasToolDetails ? expandedToolCall : undefined
                                }
                                aria-controls={
                                  hasToolDetails ? detailsId : undefined
                                }
                                aria-disabled={!hasToolDetails}
                                onClick={() =>
                                  hasToolDetails &&
                                  toggleToolCallDetails(toolCallKey)
                                }
                              >
                                <div className="flex min-w-0 flex-wrap items-center gap-2">
                                  {hasToolDetails &&
                                    (expandedToolCall ? (
                                      <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                                    ) : (
                                      <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                                    ))}
                                  <span className="min-w-0 truncate text-sm font-medium text-foreground">
                                    #{index + 1} {call.toolName}
                                  </span>
                                  <span className="rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
                                    {call.toolSource}
                                  </span>
                                  <span
                                    className={cn(
                                      'rounded-md px-2 py-1 text-xs font-medium',
                                      call.status === 'success'
                                        ? 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300'
                                        : 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300',
                                    )}
                                  >
                                    {call.status}
                                  </span>
                                  <span className="font-mono text-xs text-muted-foreground">
                                    ID: {shortId(call.id)}
                                  </span>
                                </div>
                                <span className="shrink-0 text-xs text-muted-foreground">
                                  {formatDuration(call.duration)}
                                </span>
                              </button>

                              {hasToolDetails && expandedToolCall && (
                                <div
                                  id={detailsId}
                                  className="mt-1 grid gap-2 px-2 pb-2 text-xs lg:grid-cols-2"
                                >
                                  {call.arguments && (
                                    <div className="min-w-0 rounded-md bg-muted/50 p-2">
                                      <div className="mb-1 font-medium text-foreground">
                                        {t('monitoring.toolCalls.arguments', {
                                          defaultValue: '参数',
                                        })}
                                      </div>
                                      <pre className="whitespace-pre-wrap break-words font-mono text-muted-foreground">
                                        {truncateDetail(call.arguments)}
                                      </pre>
                                    </div>
                                  )}
                                  {call.result && (
                                    <div className="min-w-0 rounded-md bg-muted/50 p-2">
                                      <div className="mb-1 font-medium text-foreground">
                                        {t('monitoring.toolCalls.result', {
                                          defaultValue: '结果',
                                        })}
                                      </div>
                                      <pre className="whitespace-pre-wrap break-words font-mono text-muted-foreground">
                                        {truncateDetail(call.result)}
                                      </pre>
                                    </div>
                                  )}
                                  {call.errorMessage && (
                                    <div className="min-w-0 whitespace-pre-wrap break-words rounded-md bg-red-50 p-2 text-red-600 dark:bg-red-950/40 dark:text-red-400 lg:col-span-2">
                                      {call.errorMessage}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })
                      ) : (
                        <div className="py-4 text-center text-sm text-muted-foreground">
                          {t('monitoring.toolCalls.noToolCalls', {
                            defaultValue: '未记录工具调用',
                          })}
                        </div>
                      )}
                    </div>
                  </section>

                  {turn.errors.length > 0 && (
                    <section>
                      <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-red-700 dark:text-red-300">
                        <AlertCircle className="h-4 w-4" />
                        {t('monitoring.errors.title', {
                          defaultValue: '错误日志',
                        })}{' '}
                        ({turn.errors.length})
                      </h4>
                      <div className="rounded-lg bg-background px-3 py-3">
                        {turn.errors.map((error) => (
                          <div
                            key={error.id}
                            className="border-t border-red-200/80 py-3 first:border-t-0 first:pt-0 last:pb-0 dark:border-red-900"
                          >
                            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                              <span className="text-sm font-medium text-red-700 dark:text-red-300">
                                {error.errorType}
                              </span>
                              <span className="text-xs text-muted-foreground">
                                {error.timestamp.toLocaleString()}
                              </span>
                            </div>
                            <div className="whitespace-pre-wrap break-words text-sm text-red-600 dark:text-red-400">
                              {error.errorMessage}
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
