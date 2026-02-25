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
              className="inline-flex items-center gap-1 text-gray-400 dark:text-gray-500 text-xs"
            >
              <svg
                className="w-3.5 h-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21Z"
                />
              </svg>
              [Image]
            </span>
          );
        }
        return (
          <div key={index} className="my-1.5">
            <img
              src={imageUrl}
              alt="Image"
              className="max-w-full max-h-52 rounded-xl cursor-pointer hover:opacity-90 transition-opacity shadow-sm"
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
              className="inline-flex items-center gap-1 text-gray-400 dark:text-gray-500 text-xs"
            >
              🎙 [Voice]
            </span>
          );
        }
        return (
          <div key={index} className="my-1.5">
            <div className="inline-flex items-center gap-2 px-3 py-2 bg-white/50 dark:bg-gray-900/50 rounded-xl">
              <audio
                controls
                src={voiceUrl}
                className="h-8"
                style={{ maxWidth: '220px' }}
              />
              {voice.length && voice.length > 0 && (
                <span className="text-[11px] text-gray-500 dark:text-gray-400 tabular-nums">
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
            className="mb-2 pl-2.5 border-l-2 border-gray-300 dark:border-gray-600 opacity-80"
          >
            <div className="text-[13px]">
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
          <div
            key={index}
            className="my-1.5 inline-flex items-center gap-2 px-3 py-2 bg-white/50 dark:bg-gray-900/50 rounded-xl text-sm"
          >
            <svg
              className="w-4 h-4 text-gray-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m18.375 12.739-7.693 7.693a4.5 4.5 0 0 1-6.364-6.364l10.94-10.94A3 3 0 1 1 19.5 7.372L8.552 18.32m.009-.01-.01.01m5.699-9.941-7.81 7.81a1.5 1.5 0 0 0 2.112 2.13"
              />
            </svg>
            <span className="text-gray-700 dark:text-gray-300">
              {file.name || 'File'}
            </span>
          </div>
        );
      }

      default:
        return (
          <span
            key={index}
            className="text-gray-400 dark:text-gray-500 text-xs"
          >
            [{component.type}]
          </span>
        );
    }
  };

  const renderMessageContent = (msg: SessionMessage) => {
    const chain = parseMessageChain(msg.message_content);
    return (
      <div className="text-[14px] leading-relaxed whitespace-pre-wrap break-words">
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

  /** Get a preview of the last message for session list */
  const getSessionPreview = (session: SessionInfo): string => {
    // We don't have last message content in session info,
    // so show message count and relative time
    return `${session.message_count} ${t('bots.sessionMonitor.messages')}`;
  };

  const selectedSession = sessions.find(
    (s) => s.session_id === selectedSessionId,
  );

  return (
    <div className="flex h-full min-h-0 rounded-xl overflow-hidden border border-gray-200 dark:border-gray-800 bg-white dark:bg-[#0a0a0a]">
      {/* Left Panel: Session List */}
      <div className="w-72 flex-shrink-0 border-r border-gray-200 dark:border-gray-800 flex flex-col min-h-0 bg-gray-50/50 dark:bg-[#111]">
        {/* Session List Header */}
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 shrink-0 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            {t('bots.sessionMonitor.sessions')}
          </h3>
          <Button
            variant="ghost"
            size="icon"
            className="w-7 h-7 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-800"
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

        {/* Session List */}
        <ScrollArea className="flex-1 min-h-0">
          {loadingSessions && sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-sm text-gray-400">
              <svg
                className="w-5 h-5 mb-2 animate-spin"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              {t('bots.sessionMonitor.loading')}
            </div>
          ) : sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
              <div className="w-12 h-12 mb-3 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                <svg
                  className="w-6 h-6 text-gray-400 dark:text-gray-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 0 1-.825-.242m9.345-8.334a2.126 2.126 0 0 0-.476-.095 48.64 48.64 0 0 0-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0 0 11.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155"
                  />
                </svg>
              </div>
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                {t('bots.sessionMonitor.noSessions')}
              </p>
            </div>
          ) : (
            <div className="p-2 space-y-0.5">
              {sessions.map((session) => {
                const isSelected = selectedSessionId === session.session_id;
                return (
                  <button
                    key={session.session_id}
                    className={cn(
                      'w-full text-left px-3 py-3 rounded-lg transition-all duration-150',
                      isSelected
                        ? 'bg-blue-50 dark:bg-blue-950/50 shadow-sm'
                        : 'hover:bg-gray-100 dark:hover:bg-gray-800/60',
                    )}
                    onClick={() =>
                      setSelectedSessionId(session.session_id)
                    }
                  >
                    {/* Top row: user + time */}
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        {/* Avatar circle */}
                        <div
                          className={cn(
                            'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-semibold',
                            isSelected
                              ? 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300'
                              : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300',
                          )}
                        >
                          {session.is_active && (
                            <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-green-500 border-2 border-white dark:border-gray-900" />
                          )}
                          {(session.user_id || session.session_id)
                            .slice(0, 2)
                            .toUpperCase()}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                            {session.user_id || session.session_id.slice(0, 12)}
                          </div>
                        </div>
                      </div>
                      <span className="text-[11px] text-gray-400 dark:text-gray-500 tabular-nums flex-shrink-0 ml-2">
                        {formatRelativeTime(session.last_activity)}
                      </span>
                    </div>
                    {/* Bottom row: preview + badges */}
                    <div className="flex items-center gap-1.5 pl-10">
                      {session.platform && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-gray-200/80 dark:bg-gray-700/80 text-gray-500 dark:text-gray-400 flex-shrink-0">
                          {session.platform}
                        </span>
                      )}
                      <span className="text-xs text-gray-400 dark:text-gray-500 truncate">
                        {getSessionPreview(session)}
                      </span>
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
          /* Empty state */
          <div className="flex-1 flex flex-col items-center justify-center text-center px-8">
            <div className="w-16 h-16 mb-4 rounded-2xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
              <svg
                className="w-8 h-8 text-gray-300 dark:text-gray-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z"
                />
              </svg>
            </div>
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
              {t('bots.sessionMonitor.selectSession')}
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              {t('bots.sessionMonitor.selectSessionHint', {
                defaultValue: 'Choose a session from the left to view messages',
              })}
            </p>
          </div>
        ) : (
          <>
            {/* Chat Header */}
            <div className="px-5 py-3 border-b border-gray-200 dark:border-gray-800 shrink-0 flex items-center justify-between bg-white dark:bg-[#0a0a0a]">
              <div className="flex items-center gap-3 min-w-0">
                {/* Avatar */}
                <div className="w-9 h-9 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center flex-shrink-0">
                  <span className="text-xs font-semibold text-blue-600 dark:text-blue-300">
                    {(selectedSession?.user_id || selectedSessionId)
                      .slice(0, 2)
                      .toUpperCase()}
                  </span>
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
                    {selectedSession?.user_id ||
                      selectedSessionId.slice(0, 16)}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                    {selectedSession?.platform && (
                      <span>{selectedSession.platform}</span>
                    )}
                    {selectedSession?.pipeline_name && (
                      <>
                        <span className="text-gray-300 dark:text-gray-600">
                          ·
                        </span>
                        <span>{selectedSession.pipeline_name}</span>
                      </>
                    )}
                    {selectedSession?.is_active && (
                      <>
                        <span className="text-gray-300 dark:text-gray-600">
                          ·
                        </span>
                        <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
                          <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
                          Active
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="w-8 h-8 rounded-lg"
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
                  className={cn(
                    'w-4 h-4',
                    loadingMessages && 'animate-spin',
                  )}
                >
                  <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
                </svg>
              </Button>
            </div>

            {/* Messages Area */}
            <ScrollArea
              ref={messagesContainerRef}
              className="flex-1 min-h-0"
            >
              <div className="px-5 py-4 space-y-3">
                {loadingMessages ? (
                  <div className="flex flex-col items-center justify-center py-16 text-sm text-gray-400">
                    <svg
                      className="w-5 h-5 mb-2 animate-spin"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                      />
                    </svg>
                    {t('bots.sessionMonitor.loading')}
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="w-12 h-12 mb-3 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                      <svg
                        className="w-6 h-6 text-gray-300 dark:text-gray-600"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={1.5}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M2.25 12.76c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 0 1 1.037-.443 48.282 48.282 0 0 0 5.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z"
                        />
                      </svg>
                    </div>
                    <p className="text-sm text-gray-400 dark:text-gray-500">
                      {t('bots.sessionMonitor.noMessages')}
                    </p>
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
                        <div className={cn('max-w-[75%] group')}>
                          <div
                            className={cn(
                              'px-4 py-2.5 rounded-2xl shadow-sm',
                              isUser
                                ? 'bg-blue-500 text-white rounded-br-md'
                                : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-md',
                              msg.status === 'error' &&
                                'ring-1 ring-red-400/50',
                            )}
                          >
                            {renderMessageContent(msg)}
                          </div>
                          {/* Metadata line below bubble */}
                          <div
                            className={cn(
                              'flex items-center gap-1.5 mt-1 px-1 text-[11px]',
                              isUser ? 'justify-end' : 'justify-start',
                              'text-gray-400 dark:text-gray-500',
                              'opacity-0 group-hover:opacity-100 transition-opacity duration-150',
                            )}
                          >
                            <span className="tabular-nums">
                              {formatTime(msg.timestamp)}
                            </span>
                            {msg.status === 'error' && (
                              <span className="text-red-400">
                                · error
                              </span>
                            )}
                            {msg.runner_name && (
                              <>
                                <span>·</span>
                                <span>{msg.runner_name}</span>
                              </>
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
