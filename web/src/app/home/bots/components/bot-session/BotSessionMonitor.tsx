import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  forwardRef,
  useImperativeHandle,
} from 'react';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { Ban, Bot, Copy, Check, Workflow, UserCheck, Send } from 'lucide-react';
import {
  MessageChainComponent,
  Plain,
  At,
  Image,
  Quote,
  Voice,
} from '@/app/infra/entities/message';
import { PIPELINE_DISCARD } from '@/app/home/bots/components/bot-form/RoutingRulesEditor';

interface SessionInfo {
  session_id: string;
  bot_id: string;
  bot_name: string;
  pipeline_id: string;
  pipeline_name: string;
  message_count: number;
  start_time: string;
  last_activity: string;
  is_active: boolean;
  platform?: string | null;
  user_id?: string | null;
  user_name?: string | null;
}

interface SessionMessage {
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
  platform?: string | null;
  user_id?: string | null;
  runner_name?: string | null;
  variables?: string | null;
  role?: string | null;
}

export interface BotSessionMonitorHandle {
  refreshSessions: () => Promise<void>;
}

interface BotSessionMonitorProps {
  botId: string;
}

const BotSessionMonitor = forwardRef<
  BotSessionMonitorHandle,
  BotSessionMonitorProps
>(function BotSessionMonitor({ botId }, ref) {
  const { t } = useTranslation();
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    null,
  );
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [copiedUserId, setCopiedUserId] = useState(false);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // Human takeover state
  const [isTakenOver, setIsTakenOver] = useState(false);
  const [takeoverLoading, setTakeoverLoading] = useState(false);
  const [operatorMessage, setOperatorMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  // Track which sessions are taken over for showing badges in the list
  const [takenOverSessions, setTakenOverSessions] = useState<Set<string>>(
    new Set(),
  );

  const parseSessionType = (sessionId: string): string | null => {
    const idx = sessionId.indexOf('_');
    if (idx === -1) return null;
    const type = sessionId.slice(0, idx);
    if (type === 'person' || type === 'group') return type;
    return null;
  };

  const abbreviateId = (id: string): string => {
    if (id.length <= 10) return id;
    return `${id.slice(0, 4)}..${id.slice(-4)}`;
  };

  const copyUserId = (userId: string) => {
    navigator.clipboard.writeText(userId).then(() => {
      setCopiedUserId(true);
      setTimeout(() => setCopiedUserId(false), 2000);
    });
  };

  const loadSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const response = await httpClient.getBotSessions(botId);
      setSessions(response.sessions ?? []);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    } finally {
      setLoadingSessions(false);
    }
  }, [botId]);

  // Load active takeover sessions to know which ones show a badge
  const loadTakeoverStatus = useCallback(async () => {
    try {
      const response = await httpClient.getHumanTakeoverSessions({
        botUuid: botId,
      });
      const activeIds = new Set<string>();
      for (const session of response.sessions ?? []) {
        if (session.status === 'active') {
          activeIds.add(session.session_id);
        }
      }
      setTakenOverSessions(activeIds);
    } catch {
      // Silently ignore — takeover feature may not be available
    }
  }, [botId]);

  useImperativeHandle(
    ref,
    () => ({
      refreshSessions: loadSessions,
    }),
    [loadSessions],
  );

  const loadMessages = useCallback(async (sessionId: string) => {
    setLoadingMessages(true);
    try {
      const response = await httpClient.getSessionMessages(sessionId);
      const sorted = (response.messages ?? []).sort(
        (a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
      );
      setMessages(sorted);
    } catch (error) {
      console.error('Failed to load session messages:', error);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  // Check takeover status for selected session
  const checkTakeoverStatus = useCallback(
    async (sessionId: string) => {
      try {
        const response =
          await httpClient.getHumanTakeoverSessionDetail(sessionId);
        const isActive =
          response.found && response.session?.status === 'active';
        setIsTakenOver(isActive);
      } catch {
        setIsTakenOver(false);
      }
    },
    [],
  );

  useEffect(() => {
    loadSessions();
    loadTakeoverStatus();
  }, [loadSessions, loadTakeoverStatus]);

  useEffect(() => {
    if (selectedSessionId) {
      loadMessages(selectedSessionId);
      checkTakeoverStatus(selectedSessionId);
    } else {
      setMessages([]);
      setIsTakenOver(false);
    }
  }, [selectedSessionId, loadMessages, checkTakeoverStatus]);

  // Auto-refresh messages when session is taken over (polling)
  useEffect(() => {
    if (!selectedSessionId || !isTakenOver) return;
    const interval = setInterval(() => {
      loadMessages(selectedSessionId);
    }, 3000);
    return () => clearInterval(interval);
  }, [selectedSessionId, isTakenOver, loadMessages]);

  useEffect(() => {
    if (messages.length === 0) return;
    // Wait for DOM to render the new messages before scrolling
    requestAnimationFrame(() => {
      const container = messagesContainerRef.current;
      if (container) {
        const viewport = container.querySelector(
          '[data-radix-scroll-area-viewport]',
        );
        const scrollTarget = viewport || container;
        scrollTarget.scrollTop = scrollTarget.scrollHeight;
      }
    });
  }, [messages]);

  const handleTakeover = async () => {
    if (!selectedSessionId || !selectedSession) return;
    if (!confirm(t('bots.sessionMonitor.takeoverConfirm'))) return;

    setTakeoverLoading(true);
    try {
      await httpClient.takeoverSession(selectedSessionId, {
        bot_uuid: botId,
        platform: selectedSession.platform ?? undefined,
        user_id: selectedSession.user_id ?? undefined,
        user_name: selectedSession.user_name ?? undefined,
      });
      setIsTakenOver(true);
      setTakenOverSessions((prev) => new Set(prev).add(selectedSessionId));
    } catch (error) {
      console.error('Takeover failed:', error);
      alert(t('bots.sessionMonitor.takeoverFailed'));
    } finally {
      setTakeoverLoading(false);
    }
  };

  const handleRelease = async () => {
    if (!selectedSessionId) return;
    if (!confirm(t('bots.sessionMonitor.releaseConfirm'))) return;

    setTakeoverLoading(true);
    try {
      await httpClient.releaseSession(selectedSessionId);
      setIsTakenOver(false);
      setTakenOverSessions((prev) => {
        const next = new Set(prev);
        next.delete(selectedSessionId);
        return next;
      });
    } catch (error) {
      console.error('Release failed:', error);
      alert(t('bots.sessionMonitor.releaseFailed'));
    } finally {
      setTakeoverLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!selectedSessionId || !operatorMessage.trim()) return;

    setSendingMessage(true);
    try {
      await httpClient.sendTakeoverMessage(
        selectedSessionId,
        operatorMessage.trim(),
      );
      setOperatorMessage('');
      // Reload messages to show the sent one
      await loadMessages(selectedSessionId);
    } catch (error) {
      console.error('Send message failed:', error);
      alert(t('bots.sessionMonitor.sendFailed'));
    } finally {
      setSendingMessage(false);
    }
  };

  const handleMessageKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const parseMessageChain = (content: string): MessageChainComponent[] => {
    try {
      const parsed = JSON.parse(content);
      if (Array.isArray(parsed)) {
        return parsed as MessageChainComponent[];
      }
    } catch {
      // Not JSON, return as plain text
    }
    return [{ type: 'Plain', text: content } as Plain];
  };

  const isUserMessage = (msg: SessionMessage): boolean => {
    if (msg.role === 'operator') return false;
    if (msg.role === 'assistant') return false;
    if (msg.role === 'user') return true;
    return !msg.runner_name;
  };

  const isOperatorMessage = (msg: SessionMessage): boolean => {
    return msg.role === 'operator';
  };

  const renderMessageComponent = (
    component: MessageChainComponent,
    index: number,
  ) => {
    switch (component.type) {
      case 'Plain':
        return <span key={index}>{(component as Plain).text}</span>;

      case 'At': {
        const atComponent = component as At;
        const displayName =
          atComponent.display || atComponent.target?.toString() || '';
        return (
          <span
            key={index}
            className="inline-flex align-middle mx-0.5 px-1.5 py-0.5 bg-blue-200/60 dark:bg-blue-800/60 text-blue-700 dark:text-blue-300 rounded-md text-xs font-medium"
          >
            @{displayName}
          </span>
        );
      }

      case 'AtAll':
        return (
          <span
            key={index}
            className="inline-flex align-middle mx-0.5 px-1.5 py-0.5 bg-blue-200/60 dark:bg-blue-800/60 text-blue-700 dark:text-blue-300 rounded-md text-xs font-medium"
          >
            @All
          </span>
        );

      case 'Image': {
        const img = component as Image;
        const imageUrl = img.url || (img.base64 ? img.base64 : '');
        if (!imageUrl) {
          return (
            <span
              key={index}
              className="inline-flex items-center gap-1 text-muted-foreground text-xs"
            >
              [Image]
            </span>
          );
        }
        return (
          <div key={index} className="my-1.5">
            <img
              src={imageUrl}
              alt="Image"
              className="max-w-full max-h-52 rounded-lg"
            />
          </div>
        );
      }

      case 'Voice': {
        const voice = component as Voice;
        const voiceUrl = voice.url || (voice.base64 ? voice.base64 : '');
        if (!voiceUrl) {
          return (
            <span
              key={index}
              className="inline-flex items-center gap-1 text-muted-foreground text-xs"
            >
              [Voice]
            </span>
          );
        }
        return (
          <div key={index} className="my-1">
            <audio controls src={voiceUrl} className="h-8 max-w-[220px]" />
          </div>
        );
      }

      case 'Quote': {
        const quote = component as Quote;
        return (
          <div
            key={index}
            className="mb-2 pl-2.5 border-l-2 border-muted-foreground/50 opacity-80"
          >
            <div className="text-sm">
              {quote.origin?.map((comp, idx) =>
                renderMessageComponent(comp as MessageChainComponent, idx),
              )}
            </div>
          </div>
        );
      }

      case 'Source':
        return null;

      case 'File': {
        const file = component as MessageChainComponent & { name?: string };
        return (
          <span key={index} className="text-muted-foreground text-xs">
            [{file.name || 'File'}]
          </span>
        );
      }

      default:
        return (
          <span key={index} className="text-muted-foreground text-xs">
            [{component.type}]
          </span>
        );
    }
  };

  const renderMessageContent = (msg: SessionMessage) => {
    const chain = parseMessageChain(msg.message_content);
    return (
      <div className="whitespace-pre-wrap break-words">
        {chain.map((component, index) =>
          renderMessageComponent(component, index),
        )}
      </div>
    );
  };

  // Backend timestamps may lack timezone indicator; treat as UTC
  const parseTimestamp = (timestamp: string): Date => {
    if (!timestamp) return new Date(0);
    const hasTimezone =
      timestamp.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(timestamp);
    return new Date(hasTimezone ? timestamp : timestamp + 'Z');
  };

  const formatTime = (timestamp: string): string => {
    if (!timestamp) return '';
    const date = parseTimestamp(timestamp);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
  };

  const formatRelativeTime = (timestamp: string): string => {
    if (!timestamp) return '';
    const date = parseTimestamp(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return '<1m';
    if (diffMins < 60) return `${diffMins}m`;
    if (diffHours < 24) return `${diffHours}h`;
    return `${diffDays}d`;
  };

  const selectedSession = sessions.find(
    (s) => s.session_id === selectedSessionId,
  );

  const getMessageRoleLabel = (msg: SessionMessage): string => {
    if (isOperatorMessage(msg)) {
      return t('bots.sessionMonitor.operatorMessage', {
        defaultValue: 'Operator',
      });
    }
    if (isUserMessage(msg)) {
      return t('bots.sessionMonitor.userMessage', {
        defaultValue: 'User',
      });
    }
    return t('bots.sessionMonitor.botMessage', {
      defaultValue: 'Assistant',
    });
  };

  return (
    <div className="flex flex-col md:flex-row h-full min-h-0 rounded-lg border overflow-hidden">
      {/* Left Panel: Session List */}
      <div className="max-h-48 md:max-h-none md:w-60 flex-shrink-0 border-b md:border-b-0 md:border-r flex flex-col min-h-0">
        {/* Session List */}
        <ScrollArea className="flex-1 min-h-0">
          {loadingSessions && sessions.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
              {t('bots.sessionMonitor.loading')}
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center text-muted-foreground py-12 text-sm">
              {t('bots.sessionMonitor.noSessions')}
            </div>
          ) : (
            <div className="p-1.5">
              {sessions.map((session) => {
                const isSelected = selectedSessionId === session.session_id;
                const sessionTakenOver = takenOverSessions.has(
                  session.session_id,
                );
                return (
                  <button
                    key={session.session_id}
                    type="button"
                    className={cn(
                      'w-full text-left px-2.5 py-2 rounded-md transition-colors',
                      isSelected ? 'bg-accent' : 'hover:bg-accent/50',
                    )}
                    onClick={() => setSelectedSessionId(session.session_id)}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-sm font-medium truncate mr-2">
                        {session.user_name ||
                          session.user_id ||
                          session.session_id.slice(0, 12)}
                      </span>
                      <span className="text-[11px] text-muted-foreground tabular-nums flex-shrink-0">
                        {formatRelativeTime(session.last_activity)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      {parseSessionType(session.session_id) && (
                        <span className="px-1 py-0.5 rounded bg-muted text-[10px]">
                          {parseSessionType(session.session_id)}
                        </span>
                      )}
                      {session.platform && (
                        <span className="px-1 py-0.5 rounded bg-muted text-[10px]">
                          {session.platform}
                        </span>
                      )}
                      {session.user_id && (
                        <span className="truncate text-[10px]">
                          {abbreviateId(session.user_id)}
                        </span>
                      )}
                      {sessionTakenOver && (
                        <span className="flex items-center gap-0.5 text-orange-600 dark:text-orange-400">
                          <UserCheck className="w-3 h-3" />
                        </span>
                      )}
                      {session.is_active && !sessionTakenOver && (
                        <span className="flex items-center gap-0.5 text-green-600 dark:text-green-400">
                          <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </div>

      {/* Right Panel: Messages */}
      <div className="flex-1 flex flex-col min-h-0 min-w-0">
        {!selectedSessionId ? (
          <div className="text-center text-muted-foreground text-sm flex-1 flex items-center justify-center">
            {t('bots.sessionMonitor.selectSession')}
          </div>
        ) : (
          <>
            {/* Chat Header */}
            <div className="px-4 py-2.5 border-b shrink-0">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">
                    {selectedSession?.user_name ||
                      selectedSession?.user_id ||
                      selectedSessionId.slice(0, 20)}
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-0.5">
                    {parseSessionType(selectedSessionId) && (
                      <span>{parseSessionType(selectedSessionId)}</span>
                    )}
                    {selectedSession?.platform && (
                      <>
                        {parseSessionType(selectedSessionId) && <span>·</span>}
                        <span>{selectedSession.platform}</span>
                      </>
                    )}
                    {selectedSession?.user_id && (
                      <>
                        <span>·</span>
                        <span className="font-mono">
                          {selectedSession.user_id}
                        </span>
                        <button
                          type="button"
                          onClick={() => copyUserId(selectedSession.user_id!)}
                          className="inline-flex items-center text-muted-foreground hover:text-foreground transition-colors"
                          title={t('common.copy')}
                        >
                          {copiedUserId ? (
                            <Check className="w-3 h-3 text-green-600" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </>
                    )}
                    {isTakenOver ? (
                      <>
                        <span>·</span>
                        <span className="flex items-center gap-1 text-orange-600 dark:text-orange-400">
                          <UserCheck className="w-3 h-3" />
                          {t('bots.sessionMonitor.takenOver', {
                            defaultValue: 'Taken Over',
                          })}
                        </span>
                      </>
                    ) : (
                      selectedSession?.is_active && (
                        <>
                          <span>·</span>
                          <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
                            Active
                          </span>
                        </>
                      )
                    )}
                  </div>
                </div>
                {/* Takeover / Release button */}
                <div className="flex-shrink-0">
                  {isTakenOver ? (
                    <button
                      type="button"
                      onClick={handleRelease}
                      disabled={takeoverLoading}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-md bg-orange-100 text-orange-700 hover:bg-orange-200 dark:bg-orange-900/30 dark:text-orange-400 dark:hover:bg-orange-900/50 transition-colors disabled:opacity-50"
                    >
                      <UserCheck className="w-3.5 h-3.5" />
                      {t('bots.sessionMonitor.releaseBtn', {
                        defaultValue: 'Release',
                      })}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={handleTakeover}
                      disabled={takeoverLoading}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-md bg-primary/10 text-primary hover:bg-primary/20 transition-colors disabled:opacity-50"
                    >
                      <UserCheck className="w-3.5 h-3.5" />
                      {t('bots.sessionMonitor.takeoverBtn', {
                        defaultValue: 'Take Over',
                      })}
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Messages Area */}
            <ScrollArea
              ref={messagesContainerRef}
              className="flex-1 px-4 py-4 overflow-y-auto min-h-0"
            >
              <div className="space-y-4">
                {loadingMessages ? (
                  <div className="text-center text-muted-foreground py-12 text-sm">
                    {t('bots.sessionMonitor.loading')}
                  </div>
                ) : messages.length === 0 ? (
                  <div className="text-center text-muted-foreground py-12 text-sm">
                    {t('bots.sessionMonitor.noMessages')}
                  </div>
                ) : (
                  messages.map((msg) => {
                    const isUser = isUserMessage(msg);
                    const isOperator = isOperatorMessage(msg);
                    const isDiscarded =
                      msg.status === 'discarded' ||
                      msg.pipeline_id === PIPELINE_DISCARD;
                    return (
                      <div
                        key={msg.id}
                        className={cn(
                          'flex',
                          isUser ? 'justify-end' : 'justify-start',
                        )}
                      >
                        <div
                          className={cn(
                            'max-w-3xl px-4 py-2.5 rounded-2xl text-sm',
                            isUser
                              ? 'bg-primary/10 rounded-br-sm'
                              : isOperator
                                ? 'bg-orange-100/80 dark:bg-orange-900/30 rounded-bl-sm'
                                : 'bg-muted rounded-bl-sm',
                            msg.status === 'error' && 'ring-1 ring-red-400/50',
                            isDiscarded && 'opacity-60',
                          )}
                        >
                          {renderMessageContent(msg)}
                          {/* Role label + pipeline + timestamp */}
                          <div
                            className={cn(
                              'text-[11px] mt-1.5 flex items-center gap-1.5 text-muted-foreground',
                            )}
                          >
                            <span
                              className={cn(
                                isOperator &&
                                  'text-orange-600 dark:text-orange-400 font-medium',
                              )}
                            >
                              {getMessageRoleLabel(msg)}
                            </span>
                            <span className="tabular-nums">
                              {formatTime(msg.timestamp)}
                            </span>
                            {isDiscarded ? (
                              <span className="inline-flex items-center gap-0.5 text-destructive">
                                <Ban className="w-3 h-3" />
                                {t('bots.sessionMonitor.discarded', {
                                  defaultValue: 'Discarded',
                                })}
                              </span>
                            ) : msg.pipeline_name &&
                              msg.pipeline_name !== 'Human Takeover' ? (
                              <span className="inline-flex items-center gap-0.5 opacity-70">
                                <Workflow className="w-3 h-3" />
                                {msg.pipeline_name}
                              </span>
                            ) : null}
                            {isOperator && (
                              <span className="inline-flex items-center gap-0.5 text-orange-600/70 dark:text-orange-400/70">
                                <UserCheck className="w-3 h-3" />
                                {t('bots.sessionMonitor.humanTakeover', {
                                  defaultValue: 'Human Takeover',
                                })}
                              </span>
                            )}
                            {msg.status === 'error' && (
                              <span className="text-red-500">error</span>
                            )}
                            {msg.runner_name && (
                              <span className="inline-flex items-center gap-0.5 opacity-70">
                                <Bot className="w-3 h-3" />
                                {msg.runner_name}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </ScrollArea>

            {/* Operator Message Input (only shown when session is taken over) */}
            {isTakenOver && (
              <div className="px-4 py-3 border-t shrink-0">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={operatorMessage}
                    onChange={(e) => setOperatorMessage(e.target.value)}
                    onKeyDown={handleMessageKeyDown}
                    placeholder={t('bots.sessionMonitor.sendMessage', {
                      defaultValue: 'Send message as operator...',
                    })}
                    disabled={sendingMessage}
                    className="flex-1 h-9 px-3 rounded-md border bg-background text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
                  />
                  <button
                    type="button"
                    onClick={handleSendMessage}
                    disabled={sendingMessage || !operatorMessage.trim()}
                    className="inline-flex items-center justify-center h-9 px-3 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:pointer-events-none"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
});

export default BotSessionMonitor;
