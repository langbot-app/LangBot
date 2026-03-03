'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
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

interface BotSessionMonitorProps {
  botId: string;
}

export default function BotSessionMonitor({ botId }: BotSessionMonitorProps) {
  const { t } = useTranslation();
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    null,
  );
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

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
            className="mb-2 pl-2.5 border-l-2 border-gray-300 dark:border-gray-600 opacity-80"
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

  const formatTime = (timestamp: string): string => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
  };

  const formatRelativeTime = (timestamp: string): string => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
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
    <div className="flex h-full min-h-0">
      {/* Left Panel: Session List */}
      <div className="w-64 flex-shrink-0 border-r flex flex-col min-h-0">
        {/* Refresh Button */}
        <div className="px-2 py-2 border-b shrink-0">
          <Button
            variant="ghost"
            className="w-full h-9 text-sm text-muted-foreground"
            onClick={loadSessions}
            disabled={loadingSessions}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              className={cn(
                'w-3.5 h-3.5 mr-1.5',
                loadingSessions && 'animate-spin',
              )}
            >
              <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
            </svg>
            {t('bots.sessionMonitor.refresh')}
          </Button>
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
            <div className="p-1">
              {sessions.map((session) => {
                const isSelected = selectedSessionId === session.session_id;
                return (
                  <button
                    key={session.session_id}
                    className={cn(
                      'w-full text-left px-3 py-2.5 rounded-md transition-colors',
                      isSelected ? 'bg-accent' : 'hover:bg-accent/50',
                    )}
                    onClick={() => setSelectedSessionId(session.session_id)}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-sm font-medium truncate mr-2">
                        {session.user_id || session.session_id.slice(0, 12)}
                      </span>
                      <span className="text-[11px] text-muted-foreground tabular-nums flex-shrink-0">
                        {formatRelativeTime(session.last_activity)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      {session.platform && (
                        <span className="px-1 py-0.5 rounded bg-muted text-[10px]">
                          {session.platform}
                        </span>
                      )}
                      {session.is_active && (
                        <span className="flex items-center gap-0.5 text-green-600 dark:text-green-400">
                          <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
                        </span>
                      )}
                      <span>{session.pipeline_name}</span>
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
          <div className="text-center text-muted-foreground py-12 text-lg flex-1 flex items-center justify-center">
            {t('bots.sessionMonitor.selectSession')}
          </div>
        ) : (
          <>
            {/* Chat Header */}
            <div className="px-6 py-3 border-b shrink-0 flex items-center justify-between">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">
                  {selectedSession?.user_id || selectedSessionId.slice(0, 20)}
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  {selectedSession?.platform && (
                    <span>{selectedSession.platform}</span>
                  )}
                  {selectedSession?.pipeline_name && (
                    <>
                      {selectedSession?.platform && <span>·</span>}
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
              <Button
                variant="ghost"
                size="icon"
                className="w-8 h-8"
                onClick={() => loadMessages(selectedSessionId)}
                disabled={loadingMessages}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className={cn('w-4 h-4', loadingMessages && 'animate-spin')}
                >
                  <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
                </svg>
              </Button>
            </div>

            {/* Messages Area — matches DebugDialog style */}
            <ScrollArea
              ref={messagesContainerRef}
              className="flex-1 p-6 overflow-y-auto min-h-0 bg-white dark:bg-black"
            >
              <div className="space-y-6">
                {loadingMessages ? (
                  <div className="text-center text-muted-foreground py-12 text-lg">
                    {t('bots.sessionMonitor.loading')}
                  </div>
                ) : messages.length === 0 ? (
                  <div className="text-center text-muted-foreground py-12 text-lg">
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
                            'max-w-3xl px-5 py-3 rounded-2xl',
                            isUser
                              ? 'bg-blue-100 dark:bg-blue-900 text-gray-900 dark:text-gray-100 rounded-br-none'
                              : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-none',
                            msg.status === 'error' && 'ring-1 ring-red-400/50',
                          )}
                        >
                          {renderMessageContent(msg)}
                          {/* Role label + timestamp inside bubble, matching DebugDialog */}
                          <div
                            className={cn(
                              'text-xs mt-2 flex items-center gap-2',
                              isUser
                                ? 'text-gray-600 dark:text-gray-300'
                                : 'text-gray-500 dark:text-gray-400',
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
}
