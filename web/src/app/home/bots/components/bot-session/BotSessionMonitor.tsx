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
  const messagesEndRef = useRef<HTMLDivElement>(null);

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
      // Sort messages chronologically (ascending) for chat view
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
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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
    // Fallback for old messages without role field
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
            className="inline-flex align-middle mx-1 px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded text-xs"
          >
            @{displayName}
          </span>
        );
      }

      case 'AtAll':
        return (
          <span
            key={index}
            className="inline-flex align-middle mx-1 px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded text-xs"
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
              className="text-gray-500 dark:text-gray-400 text-xs"
            >
              [Image]
            </span>
          );
        }
        return (
          <div key={index} className="my-1">
            <img
              src={imageUrl}
              alt="Image"
              className="max-w-full max-h-48 rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
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
              className="text-gray-500 dark:text-gray-400 text-xs"
            >
              [Voice]
            </span>
          );
        }
        return (
          <div key={index} className="my-1 flex items-center gap-2">
            <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 dark:bg-gray-800 rounded-lg">
              <audio
                controls
                src={voiceUrl}
                className="h-8"
                style={{ maxWidth: '200px' }}
              />
              {voice.length && voice.length > 0 && (
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {voice.length}s
                </span>
              )}
            </div>
          </div>
        );
      }

      case 'Quote': {
        const quote = component as Quote;
        return (
          <div
            key={index}
            className="mb-1 pl-2 border-l-2 border-gray-400 dark:border-gray-500"
          >
            <div className="text-sm opacity-75">
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
          <div key={index} className="my-1 flex items-center gap-2 text-sm">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M8 4a3 3 0 00-3 3v4a5 5 0 0010 0V7a1 1 0 112 0v4a7 7 0 11-14 0V7a5 5 0 0110 0v4a3 3 0 11-6 0V7a1 1 0 012 0v4a1 1 0 102 0V7a3 3 0 00-3-3z" />
            </svg>
            <span>[File] {file.name || 'Unknown'}</span>
          </div>
        );
      }

      default:
        return (
          <span
            key={index}
            className="text-gray-500 dark:text-gray-400 text-xs"
          >
            [{component.type}]
          </span>
        );
    }
  };

  const renderMessageContent = (msg: SessionMessage) => {
    const chain = parseMessageChain(msg.message_content);
    return (
      <div className="text-sm leading-relaxed whitespace-pre-wrap">
        {chain.map((component, index) =>
          renderMessageComponent(component, index),
        )}
      </div>
    );
  };

  const formatTime = (timestamp: string): string => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const now = new Date();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');

    if (now.toDateString() === date.toDateString()) {
      return `${hours}:${minutes}`;
    }

    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (yesterday.toDateString() === date.toDateString()) {
      return `${t('bots.yesterday')} ${hours}:${minutes}`;
    }

    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${month}/${day} ${hours}:${minutes}`;
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

  return (
    <div className="flex h-full min-h-0 gap-0">
      {/* Left Panel: Session List */}
      <div className="w-56 flex-shrink-0 border-r border-gray-200 dark:border-gray-700 flex flex-col min-h-0">
        <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 shrink-0 flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {t('bots.sessionMonitor.sessions')}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="w-6 h-6"
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
              className={cn('w-3.5 h-3.5', loadingSessions && 'animate-spin')}
            >
              <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
            </svg>
          </Button>
        </div>
        <ScrollArea className="flex-1 min-h-0">
          {loadingSessions && sessions.length === 0 ? (
            <div className="text-center text-muted-foreground py-8 text-sm">
              {t('bots.sessionMonitor.loading')}
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center text-muted-foreground py-8 text-sm">
              {t('bots.sessionMonitor.noSessions')}
            </div>
          ) : (
            <div className="p-1">
              {sessions.map((session) => (
                <button
                  key={session.session_id}
                  className={cn(
                    'w-full text-left px-3 py-2.5 rounded-md mb-0.5 transition-colors',
                    selectedSessionId === session.session_id
                      ? 'bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800'
                      : 'hover:bg-gray-50 dark:hover:bg-gray-800 border border-transparent',
                  )}
                  onClick={() => setSelectedSessionId(session.session_id)}
                >
                  <div className="flex items-center gap-1.5 mb-1">
                    {session.is_active && (
                      <div className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0" />
                    )}
                    <span className="text-xs font-medium text-gray-900 dark:text-gray-100 truncate">
                      {session.user_id || session.session_id}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 mb-1">
                    {session.platform && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                        {session.platform}
                      </span>
                    )}
                    <span className="text-[10px] text-gray-500 dark:text-gray-400">
                      {session.message_count}{' '}
                      {t('bots.sessionMonitor.messages')}
                    </span>
                  </div>
                  <div className="text-[10px] text-gray-400 dark:text-gray-500">
                    {formatRelativeTime(session.last_activity)}
                  </div>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>

      {/* Right Panel: Messages */}
      <div className="flex-1 flex flex-col min-h-0 min-w-0">
        {!selectedSessionId ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
            {t('bots.sessionMonitor.selectSession')}
          </div>
        ) : (
          <>
            {/* Session Info Header */}
            <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 shrink-0 flex items-center gap-2">
              <span className="text-xs font-mono text-gray-600 dark:text-gray-400 truncate">
                {selectedSessionId}
              </span>
              {(() => {
                const session = sessions.find(
                  (s) => s.session_id === selectedSessionId,
                );
                return session ? (
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {session.platform && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                        {session.platform}
                      </span>
                    )}
                    <span className="text-[10px] text-gray-500 dark:text-gray-400">
                      {session.pipeline_name}
                    </span>
                  </div>
                ) : null;
              })()}
            </div>

            {/* Messages - Chat Bubble Style (like DebugDialog) */}
            <ScrollArea className="flex-1 min-h-0 p-4 bg-white dark:bg-black">
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
                            'max-w-[75%] px-4 py-2.5 rounded-2xl',
                            isUser
                              ? 'bg-blue-100 dark:bg-blue-900 text-gray-900 dark:text-gray-100 rounded-br-none'
                              : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-none',
                            msg.status === 'error' &&
                              'border border-red-300 dark:border-red-700',
                          )}
                        >
                          {renderMessageContent(msg)}
                          <div
                            className={cn(
                              'text-[10px] mt-1.5 flex items-center gap-2',
                              isUser
                                ? 'text-gray-500 dark:text-gray-400 justify-end'
                                : 'text-gray-400 dark:text-gray-500',
                            )}
                          >
                            <span>{formatTime(msg.timestamp)}</span>
                            {msg.status === 'error' && (
                              <span className="text-red-500 dark:text-red-400">
                                error
                              </span>
                            )}
                            {msg.runner_name && (
                              <span className="px-1 py-0.5 rounded bg-purple-100 text-purple-600 dark:bg-purple-900 dark:text-purple-300">
                                {msg.runner_name}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>
          </>
        )}
      </div>
    </div>
  );
}
