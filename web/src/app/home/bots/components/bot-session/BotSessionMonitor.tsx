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
import { Copy, Check } from 'lucide-react';
import {
  MessageChainComponent,
  Plain,
  At,
  Image,
  Quote,
  Voice,
} from '@/app/infra/entities/message';

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

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (selectedSessionId) {
      loadMessages(selectedSessionId);
    } else {
      setMessages([]);
    }
  }, [selectedSessionId, loadMessages]);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (container) {
      const viewport = container.querySelector(
        '[data-radix-scroll-area-viewport]',
      );
      const scrollTarget = viewport || container;
      scrollTarget.scrollTop = scrollTarget.scrollHeight;
    }
  }, [messages]);

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
    if (msg.role === 'assistant') return false;
    if (msg.role === 'user') return true;
    return !msg.runner_name;
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
              🎙 [Voice]
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
            📎 {file.name || 'File'}
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
                      {session.is_active && (
                        <span className="flex items-center gap-0.5 text-green-600 dark:text-green-400">
                          <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
                        </span>
                      )}
                      <span className="truncate">{session.pipeline_name}</span>
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
                  {selectedSession?.pipeline_name && (
                    <>
                      <span>·</span>
                      <span>{selectedSession.pipeline_name}</span>
                    </>
                  )}
                  {selectedSession?.is_active && (
                    <>
                      <span>·</span>
                      <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
                        <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
                        Active
                      </span>
                    </>
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
                              : 'bg-muted rounded-bl-sm',
                            msg.status === 'error' && 'ring-1 ring-red-400/50',
                          )}
                        >
                          {renderMessageContent(msg)}
                          {/* Role label + timestamp */}
                          <div
                            className={cn(
                              'text-[11px] mt-1.5 flex items-center gap-1.5 text-muted-foreground',
                            )}
                          >
                            <span>
                              {isUser
                                ? t('bots.sessionMonitor.userMessage', {
                                    defaultValue: 'User',
                                  })
                                : t('bots.sessionMonitor.botMessage', {
                                    defaultValue: 'Assistant',
                                  })}
                            </span>
                            <span className="tabular-nums">
                              {formatTime(msg.timestamp)}
                            </span>
                            {msg.status === 'error' && (
                              <span className="text-red-500">error</span>
                            )}
                            {msg.runner_name && (
                              <span className="opacity-70">
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
          </>
        )}
      </div>
    </div>
  );
});

export default BotSessionMonitor;
