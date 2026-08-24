import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  forwardRef,
  useImperativeHandle,
} from 'react';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import {
  Ban,
  Bot,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  Workflow,
  ThumbsUp,
  ThumbsDown,
  ShieldCheck,
  ShieldOff,
  Wrench,
} from 'lucide-react';
import { toast } from 'sonner';
import BotAdminsDialog, {
  useBotAdmins,
} from '@/app/home/bots/components/bot-admins/BotAdminsDialog';
import type { BotAdmin } from '@/app/home/bots/components/bot-admins/BotAdminsDialog';
import { copyToClipboard } from '@/app/utils/clipboard';
import {
  MessageChainComponent,
  Plain,
  At,
  Image,
  Quote,
  Voice,
} from '@/app/infra/entities/message';
import { PIPELINE_DISCARD } from '@/app/home/bots/components/bot-form/EventBindingsEditor';

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

interface SessionFeedback {
  feedback_type: number; // 1=like, 2=dislike
  feedback_content?: string | null;
  stream_id?: string | null;
}

interface SessionToolCall {
  id: string;
  timestamp: string;
  tool_name: string;
  tool_source: string;
  duration: number;
  status: string;
  message_id?: string | null;
  arguments?: string | null;
  result?: string | null;
  error_message?: string | null;
}

type SessionTimelineItem =
  | {
      id: string;
      type: 'message';
      timestamp: number;
      order: number;
      message: SessionMessage;
    }
  | {
      id: string;
      type: 'tool';
      timestamp: number;
      order: number;
      toolCall: SessionToolCall;
    };

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
  const [feedbackMap, setFeedbackMap] = useState<
    Record<string, SessionFeedback>
  >({});
  const [toolCalls, setToolCalls] = useState<SessionToolCall[]>([]);
  const [expandedToolCallIds, setExpandedToolCallIds] = useState<
    Record<string, boolean>
  >({});
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const { admins, reload: reloadAdmins } = useBotAdmins(botId);
  const [adminsDialogOpen, setAdminsDialogOpen] = useState(false);
  const [togglingAdmin, setTogglingAdmin] = useState<string | null>(null);

  const parseSessionType = (sessionId: string): string | null => {
    const lower = sessionId.toLowerCase();
    if (lower.includes('person')) return 'person';
    if (lower.includes('group')) return 'group';
    return null;
  };

  const isSessionAdmin = (session: SessionInfo): boolean => {
    const type = parseSessionType(session.session_id);
    const lid =
      session.user_id ??
      session.session_id.replace(
        /^.*?[._](?:PERSON|GROUP|person|group)[._]/i,
        '',
      );
    return admins.some(
      (a: BotAdmin) => a.launcher_type === type && a.launcher_id === lid,
    );
  };

  const toggleAdmin = async (session: SessionInfo) => {
    const type = parseSessionType(session.session_id);
    if (!type) return;
    const lid =
      session.user_id ??
      session.session_id.replace(
        /^.*?[._](?:PERSON|GROUP|person|group)[._]/i,
        '',
      );
    const key = session.session_id;
    setTogglingAdmin(key);
    try {
      const existing = admins.find(
        (a: BotAdmin) => a.launcher_type === type && a.launcher_id === lid,
      );
      if (existing) {
        await httpClient.deleteBotAdmin(botId, existing.id);
        toast.success(t('bots.admins.deleteSuccess'));
      } else {
        await httpClient.addBotAdmin(botId, type, lid);
        toast.success(t('bots.admins.addSuccess'));
      }
      await reloadAdmins();
    } catch {
      toast.error(t('bots.admins.addError'));
    } finally {
      setTogglingAdmin(null);
    }
  };

  const abbreviateId = (id: string): string => {
    if (id.length <= 10) return id;
    return `${id.slice(0, 4)}..${id.slice(-4)}`;
  };

  const copyUserId = (userId: string) => {
    copyToClipboard(userId).catch(() => {});
    setCopiedUserId(true);
    setTimeout(() => setCopiedUserId(false), 2000);
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

  const loadMessages = useCallback(
    async (sessionId: string) => {
      setLoadingMessages(true);
      setExpandedToolCallIds({});
      try {
        const messagesRes = await httpClient.getSessionMessages(sessionId);
        const sorted = (messagesRes.messages ?? []).sort(
          (a, b) =>
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
        );
        setMessages(sorted);

        try {
          const analysisRes = await httpClient.get<{
            tool_calls?: SessionToolCall[];
          }>(
            `/api/v1/monitoring/sessions/${encodeURIComponent(sessionId)}/analysis`,
          );
          setToolCalls(analysisRes?.tool_calls ?? []);
        } catch (analysisError) {
          console.error('Failed to load session tool calls:', analysisError);
          setToolCalls([]);
        }

        // Collect user message IDs for feedback matching
        const userMsgIds = new Set(
          sorted.filter((m) => !m.role || m.role === 'user').map((m) => m.id),
        );

        if (userMsgIds.size > 0) {
          // Fetch feedback for this bot, then match by stream_id locally
          const feedbackRes = await httpClient.get<{
            feedback: SessionFeedback[];
          }>(
            `/api/v1/monitoring/feedback?botId=${encodeURIComponent(botId)}&limit=200`,
          );

          const map: Record<string, SessionFeedback> = {};
          if (feedbackRes?.feedback) {
            for (const fb of feedbackRes.feedback) {
              if (fb.stream_id && userMsgIds.has(fb.stream_id)) {
                map[fb.stream_id] = fb;
              }
            }
          }
          setFeedbackMap(map);
        } else {
          setFeedbackMap({});
        }
      } catch (error) {
        console.error('Failed to load session messages:', error);
      } finally {
        setLoadingMessages(false);
      }
    },
    [botId],
  );

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (selectedSessionId) {
      loadMessages(selectedSessionId);
    } else {
      setMessages([]);
      setToolCalls([]);
      setExpandedToolCallIds({});
      setFeedbackMap({});
    }
  }, [selectedSessionId, loadMessages]);

  useEffect(() => {
    if (messages.length === 0 && toolCalls.length === 0) return;
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
  }, [messages, toolCalls]);

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

  const formatDuration = (durationMs: number): string => {
    if (!durationMs) return '0ms';
    if (durationMs < 1000) return `${durationMs}ms`;
    return `${(durationMs / 1000).toFixed(2)}s`;
  };

  const truncateToolDetail = (value?: string | null): string => {
    if (!value) return '';
    return value.length > 600 ? `${value.slice(0, 600)}...` : value;
  };

  const toggleToolCallDetails = (toolCallId: string) => {
    setExpandedToolCallIds((previous) => ({
      ...previous,
      [toolCallId]: !previous[toolCallId],
    }));
  };

  const feedbackByMessageId = useMemo(() => {
    const map: Record<string, SessionFeedback> = {};

    for (let index = 0; index < messages.length; index++) {
      const msg = messages[index];
      if (isUserMessage(msg)) continue;

      for (let previousIndex = index - 1; previousIndex >= 0; previousIndex--) {
        const previousMessage = messages[previousIndex];
        if (isUserMessage(previousMessage)) {
          const feedback = feedbackMap[previousMessage.id];
          if (feedback) {
            map[msg.id] = feedback;
          }
          break;
        }
      }
    }

    return map;
  }, [feedbackMap, messages]);

  const timelineItems = useMemo<SessionTimelineItem[]>(() => {
    const messageItems: SessionTimelineItem[] = messages.map(
      (message, index) => ({
        id: `message-${message.id}`,
        type: 'message',
        timestamp: parseTimestamp(message.timestamp).getTime(),
        order: index * 2,
        message,
      }),
    );
    const toolItems: SessionTimelineItem[] = toolCalls.map(
      (toolCall, index) => ({
        id: `tool-${toolCall.id}`,
        type: 'tool',
        timestamp: parseTimestamp(toolCall.timestamp).getTime(),
        order: index * 2 + 1,
        toolCall,
      }),
    );

    return [...messageItems, ...toolItems].sort(
      (a, b) => a.timestamp - b.timestamp || a.order - b.order,
    );
  }, [messages, toolCalls]);

  const selectedSession = sessions.find(
    (s) => s.session_id === selectedSessionId,
  );

  return (
    <>
      <div className="flex flex-col md:flex-row h-full min-h-0 rounded-lg border overflow-hidden">
        {/* Left Panel: Session List */}
        <div className="max-h-48 md:max-h-none md:w-60 flex-shrink-0 border-b md:border-b-0 md:border-r flex flex-col min-h-0">
          {/* Admin header */}
          <div className="px-2 py-1.5 border-b shrink-0 flex items-center justify-between">
            <button
              type="button"
              className="inline-flex items-center gap-1.5 text-sm font-medium hover:text-foreground transition-colors"
              onClick={() => setAdminsDialogOpen(true)}
            >
              <ShieldCheck className="size-4" />
              <span>
                {t('bots.admins.configureAdmins')}
                {admins.length > 0 && (
                  <span className="ml-1 tabular-nums text-xs text-muted-foreground">
                    ({admins.length})
                  </span>
                )}
              </span>
            </button>
          </div>
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
                  const sessionType = parseSessionType(session.session_id);
                  const sessionIsAdmin = isSessionAdmin(session);
                  return (
                    <div
                      key={session.session_id}
                      role="button"
                      tabIndex={0}
                      className={cn(
                        'w-full text-left px-2.5 py-2 rounded-md transition-colors cursor-pointer',
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
                        {sessionType && (
                          <span className="px-1 py-0.5 rounded bg-muted text-[10px]">
                            {sessionType}
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
                      </div>
                    </div>
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
              <div className="px-4 py-2.5 border-b shrink-0 flex items-center justify-between">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate">
                    {selectedSession?.user_name ||
                      selectedSession?.user_id ||
                      selectedSessionId.slice(0, 20)}
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-0.5">
                    {parseSessionType(selectedSessionId) && (
                      <span>{parseSessionType(selectedSessionId)}</span>
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
                    {selectedSession?.is_active && (
                      <>
                        <span>·</span>
                        <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
                          <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
                          Active
                        </span>
                      </>
                    )}
                    {selectedSession && parseSessionType(selectedSessionId) && (
                      <>
                        <span>·</span>
                        <button
                          type="button"
                          className={cn(
                            'inline-flex items-center gap-1 transition-colors',
                            isSessionAdmin(selectedSession)
                              ? 'text-blue-500'
                              : 'text-muted-foreground hover:text-blue-500',
                          )}
                          disabled={togglingAdmin === selectedSessionId}
                          title={
                            isSessionAdmin(selectedSession)
                              ? t('bots.admins.removeAdminTitle')
                              : t('bots.admins.setAdminTitle')
                          }
                          onClick={() => toggleAdmin(selectedSession)}
                        >
                          {isSessionAdmin(selectedSession) ? (
                            <ShieldCheck className="size-3.5" />
                          ) : (
                            <ShieldOff className="size-3.5" />
                          )}
                          <span>{t('bots.admins.adminBadge')}</span>
                        </button>
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
                  ) : timelineItems.length === 0 ? (
                    <div className="text-center text-muted-foreground py-12 text-sm">
                      {t('bots.sessionMonitor.noMessages')}
                    </div>
                  ) : (
                    timelineItems.map((item) => {
                      if (item.type === 'tool') {
                        const call = item.toolCall;
                        const hasToolDetails = Boolean(
                          call.arguments || call.result || call.error_message,
                        );
                        const expandedToolCall = Boolean(
                          expandedToolCallIds[call.id],
                        );
                        const detailsId = `tool-call-details-${call.id}`;
                        return (
                          <div key={item.id} className="flex justify-start">
                            <div className="max-w-2xl rounded-xl rounded-bl-sm border border-border/60 bg-muted/25 px-2.5 py-1.5 text-xs text-muted-foreground">
                              <button
                                type="button"
                                className={cn(
                                  'flex w-full items-center justify-between gap-3 rounded-md text-left outline-none transition-colors',
                                  hasToolDetails &&
                                    'cursor-pointer hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring',
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
                                  toggleToolCallDetails(call.id)
                                }
                              >
                                <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                                  {hasToolDetails &&
                                    (expandedToolCall ? (
                                      <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground/70" />
                                    ) : (
                                      <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/70" />
                                    ))}
                                  <Wrench className="h-3.5 w-3.5 shrink-0 text-muted-foreground/70" />
                                  <span className="min-w-0 max-w-[18rem] truncate text-[13px] font-medium text-foreground/75">
                                    {call.tool_name}
                                  </span>
                                  <span className="rounded border border-border/50 bg-background/60 px-1.5 py-0.5 text-[10px] leading-none text-muted-foreground">
                                    {call.tool_source}
                                  </span>
                                  <span
                                    className={cn(
                                      'rounded px-1.5 py-0.5 text-[10px] font-medium leading-none',
                                      call.status === 'success'
                                        ? 'bg-green-100/70 text-green-700 dark:bg-green-950/60 dark:text-green-300'
                                        : 'bg-red-100/70 text-red-700 dark:bg-red-950/60 dark:text-red-300',
                                    )}
                                  >
                                    {call.status}
                                  </span>
                                </div>
                                <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground/80">
                                  {formatDuration(call.duration)}
                                </span>
                              </button>

                              {hasToolDetails && expandedToolCall && (
                                <div
                                  id={detailsId}
                                  className="mt-2 space-y-1.5"
                                >
                                  {(call.arguments || call.result) && (
                                    <div className="space-y-1.5">
                                      {call.arguments && (
                                        <div>
                                          <div className="mb-1 text-[11px] font-medium text-muted-foreground">
                                            {t(
                                              'monitoring.toolCalls.arguments',
                                              {
                                                defaultValue: '参数',
                                              },
                                            )}
                                          </div>
                                          <pre className="whitespace-pre-wrap break-words rounded bg-background/80 p-2 font-mono text-[11px] leading-4 text-muted-foreground">
                                            {truncateToolDetail(call.arguments)}
                                          </pre>
                                        </div>
                                      )}
                                      {call.result && (
                                        <div>
                                          <div className="mb-1 text-[11px] font-medium text-muted-foreground">
                                            {t('monitoring.toolCalls.result', {
                                              defaultValue: '结果',
                                            })}
                                          </div>
                                          <pre className="whitespace-pre-wrap break-words rounded bg-background/80 p-2 font-mono text-[11px] leading-4 text-muted-foreground">
                                            {truncateToolDetail(call.result)}
                                          </pre>
                                        </div>
                                      )}
                                    </div>
                                  )}

                                  {call.error_message && (
                                    <div className="whitespace-pre-wrap break-words rounded bg-red-50 p-2 text-[11px] text-red-600 dark:bg-red-950/40 dark:text-red-400">
                                      {call.error_message}
                                    </div>
                                  )}
                                </div>
                              )}

                              <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                                <span>
                                  {t('monitoring.toolCalls.title', {
                                    defaultValue: '工具调用',
                                  })}
                                </span>
                                <span className="tabular-nums">
                                  {formatTime(call.timestamp)}
                                </span>
                                {hasToolDetails && (
                                  <>
                                    <span>·</span>
                                    <span>
                                      {expandedToolCall
                                        ? t(
                                            'monitoring.toolCalls.hideDetails',
                                            {
                                              defaultValue: '隐藏详情',
                                            },
                                          )
                                        : t(
                                            'monitoring.toolCalls.showDetails',
                                            {
                                              defaultValue: '查看详情',
                                            },
                                          )}
                                    </span>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      }

                      const msg = item.message;
                      const isUser = isUserMessage(msg);
                      const isDiscarded =
                        msg.status === 'discarded' ||
                        msg.pipeline_id === PIPELINE_DISCARD;
                      const msgFeedback = feedbackByMessageId[msg.id];
                      return (
                        <div
                          key={item.id}
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
                              msg.status === 'error' &&
                                'ring-1 ring-red-400/50',
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
                              {isDiscarded ? (
                                <span className="inline-flex items-center gap-0.5 text-destructive">
                                  <Ban className="w-3 h-3" />
                                  {t('bots.sessionMonitor.discarded', {
                                    defaultValue: 'Discarded',
                                  })}
                                </span>
                              ) : msg.pipeline_name ? (
                                <span className="inline-flex items-center gap-0.5 opacity-70">
                                  <Workflow className="w-3 h-3" />
                                  {msg.pipeline_name}
                                </span>
                              ) : null}
                              {msg.status === 'error' && (
                                <span className="text-red-500">error</span>
                              )}
                              {msg.runner_name && (
                                <span className="inline-flex items-center gap-0.5 opacity-70">
                                  <Bot className="w-3 h-3" />
                                  {msg.runner_name}
                                </span>
                              )}
                              {/* Feedback indicator — same line, pushed right */}
                              {!isUser &&
                                msgFeedback &&
                                (msgFeedback.feedback_type === 1 ? (
                                  <span className="inline-flex items-center gap-1 ml-auto text-green-600 dark:text-green-400 cursor-default relative group">
                                    <ThumbsUp className="w-3 h-3 flex-shrink-0" />
                                    {t('monitoring.feedback.like')}
                                    {msgFeedback.feedback_content && (
                                      <span className="hidden group-hover:block absolute bottom-full right-0 mb-1 px-3 py-1.5 rounded-lg bg-popover border text-popover-foreground text-xs whitespace-nowrap shadow-md z-10">
                                        {msgFeedback.feedback_content}
                                      </span>
                                    )}
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1 ml-auto text-red-500 dark:text-red-400 cursor-default relative group">
                                    <ThumbsDown className="w-3 h-3 flex-shrink-0" />
                                    {t('monitoring.feedback.dislike')}
                                    {msgFeedback.feedback_content && (
                                      <span className="hidden group-hover:block absolute bottom-full right-0 mb-1 px-3 py-1.5 rounded-lg bg-popover border text-popover-foreground text-xs whitespace-nowrap shadow-md z-10">
                                        {msgFeedback.feedback_content}
                                      </span>
                                    )}
                                  </span>
                                ))}
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

      <BotAdminsDialog
        botId={botId}
        open={adminsDialogOpen}
        onOpenChange={setAdminsDialogOpen}
        admins={admins}
        onAdminsChange={reloadAdmins}
      />
    </>
  );
});

export default BotSessionMonitor;
