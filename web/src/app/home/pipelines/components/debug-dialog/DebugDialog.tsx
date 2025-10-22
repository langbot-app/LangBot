import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import { DialogContent } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { Message } from '@/app/infra/entities/message';
import { toast } from 'sonner';
import AtBadge from './AtBadge';
import { Switch } from '@/components/ui/switch';
import {
  PipelineWebSocketClient,
  SessionType,
} from '@/app/infra/websocket/PipelineWebSocketClient';

interface MessageComponent {
  type: 'At' | 'Plain';
  target?: string;
  text?: string;
}

interface DebugDialogProps {
  open: boolean;
  pipelineId: string;
  isEmbedded?: boolean;
}

export default function DebugDialog({
  open,
  pipelineId,
  isEmbedded = false,
}: DebugDialogProps) {
  const { t } = useTranslation();
  const [selectedPipelineId, setSelectedPipelineId] = useState(pipelineId);
  const [sessionType, setSessionType] = useState<SessionType>('person');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [showAtPopover, setShowAtPopover] = useState(false);
  const [hasAt, setHasAt] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  // WebSocket states
  const [wsClient, setWsClient] = useState<PipelineWebSocketClient | null>(
    null,
  );
  const [connectionStatus, setConnectionStatus] = useState<
    'disconnected' | 'connecting' | 'connected'
  >('disconnected');
  const [pendingMessages, setPendingMessages] = useState<
    Map<string, Message>
  >(new Map());

  const scrollToBottom = useCallback(() => {
    // 使用setTimeout确保在DOM更新后执行滚动
    setTimeout(() => {
      const scrollArea = document.querySelector('.scroll-area') as HTMLElement;
      if (scrollArea) {
        scrollArea.scrollTo({
          top: scrollArea.scrollHeight,
          behavior: 'smooth',
        });
      }
      // 同时确保messagesEndRef也滚动到视图
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 0);
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // WebSocket connection setup
  useEffect(() => {
    if (!open) return;

    const client = new PipelineWebSocketClient(
      selectedPipelineId,
      sessionType,
    );

    // Setup event handlers
    client.onConnected = (data) => {
      console.log('[DebugDialog] WebSocket connected:', data);
      setConnectionStatus('connected');
      // Load history messages after connection
      client.loadHistory();
    };

    client.onHistory = (data) => {
      console.log('[DebugDialog] History loaded:', data?.messages.length);
      if (data) {
        setMessages(data.messages);
      }
    };

    client.onMessageSent = (data) => {
      console.log('[DebugDialog] Message sent confirmed:', data);
      if (data) {
        // Update client message ID to server message ID
        const clientMsgId = data.client_message_id;
        const serverMsgId = data.server_message_id;

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === -1 && pendingMessages.has(clientMsgId)
              ? { ...msg, id: serverMsgId }
              : msg,
          ),
        );

        setPendingMessages((prev) => {
          const newMap = new Map(prev);
          newMap.delete(clientMsgId);
          return newMap;
        });
      }
    };

    client.onMessageStart = (data) => {
      console.log('[DebugDialog] Message start:', data);
      if (data) {
        const placeholderMessage: Message = {
          id: data.message_id,
          role: 'assistant',
          content: '',
          message_chain: [],
          timestamp: data.timestamp,
        };
        setMessages((prev) => [...prev, placeholderMessage]);
      }
    };

    client.onMessageChunk = (data) => {
      if (data) {
        // Update streaming message (content is cumulative)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === data.message_id
              ? {
                  ...msg,
                  content: data.content,
                  message_chain: data.message_chain,
                }
              : msg,
          ),
        );
      }
    };

    client.onMessageComplete = (data) => {
      console.log('[DebugDialog] Message complete:', data);
      if (data) {
        // Mark message as complete
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === data.message_id
              ? {
                  ...msg,
                  content: data.final_content,
                  message_chain: data.message_chain,
                }
              : msg,
          ),
        );
      }
    };

    client.onMessageError = (data) => {
      console.error('[DebugDialog] Message error:', data);
      if (data) {
        toast.error(`Message error: ${data.error}`);
      }
    };

    client.onPluginMessage = (data) => {
      console.log('[DebugDialog] Plugin message:', data);
      if (data) {
        const pluginMessage: Message = {
          id: data.message_id,
          role: 'assistant',
          content: data.content,
          message_chain: data.message_chain,
          timestamp: data.timestamp,
        };
        setMessages((prev) => [...prev, pluginMessage]);
      }
    };

    client.onError = (data) => {
      console.error('[DebugDialog] WebSocket error:', data);
      if (data) {
        toast.error(`WebSocket error: ${data.error}`);
      }
    };

    client.onDisconnected = () => {
      console.log('[DebugDialog] WebSocket disconnected');
      setConnectionStatus('disconnected');
    };

    // Connect to WebSocket
    setConnectionStatus('connecting');
    client
      .connect(httpClient.getSessionSync())
      .then(() => {
        console.log('[DebugDialog] WebSocket connection established');
      })
      .catch((err) => {
        console.error('[DebugDialog] Failed to connect WebSocket:', err);
        toast.error('Failed to connect to server');
        setConnectionStatus('disconnected');
      });

    setWsClient(client);

    // Cleanup on unmount or session type change
    return () => {
      console.log('[DebugDialog] Cleaning up WebSocket connection');
      client.disconnect();
    };
  }, [open, selectedPipelineId, sessionType]); // Reconnect when session type changes

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(event.target as Node) &&
        !inputRef.current?.contains(event.target as Node)
      ) {
        setShowAtPopover(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  useEffect(() => {
    if (showAtPopover) {
      setIsHovering(true);
    }
  }, [showAtPopover]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    if (sessionType === 'group') {
      if (value.endsWith('@')) {
        setShowAtPopover(true);
      } else if (showAtPopover && (!value.includes('@') || value.length > 1)) {
        setShowAtPopover(false);
      }
    }
    setInputValue(value);
  };

  const handleAtSelect = () => {
    setHasAt(true);
    setShowAtPopover(false);
    setInputValue(inputValue.slice(0, -1));
  };

  const handleAtRemove = () => {
    setHasAt(false);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (showAtPopover) {
        handleAtSelect();
      } else {
        sendMessage();
      }
    } else if (e.key === 'Backspace' && hasAt && inputValue === '') {
      handleAtRemove();
    }
  };

  const sendMessage = async () => {
    if (!inputValue.trim() && !hasAt) return;

    // Check WebSocket connection
    if (!wsClient || connectionStatus !== 'connected') {
      toast.error('Not connected to server');
      return;
    }

    try {
      const messageChain = [];

      let text_content = inputValue.trim();
      if (hasAt) {
        text_content = ' ' + text_content;
      }

      if (hasAt) {
        messageChain.push({
          type: 'At',
          target: 'webchatbot',
        });
      }
      messageChain.push({
        type: 'Plain',
        text: text_content,
      });

      if (hasAt) {
        // For display
        text_content = '@webchatbot' + text_content;
      }

      const userMessage: Message = {
        id: -1,
        role: 'user',
        content: text_content,
        timestamp: new Date().toISOString(),
        message_chain: messageChain,
      };

      // Add user message to UI immediately
      setMessages((prevMessages) => [...prevMessages, userMessage]);
      setInputValue('');
      setHasAt(false);

      // Send via WebSocket
      const clientMessageId = wsClient.sendMessage(messageChain);

      // Track pending message for ID mapping
      setPendingMessages((prev) => {
        const newMap = new Map(prev);
        newMap.set(clientMessageId, userMessage);
        return newMap;
      });

      console.log('[DebugDialog] Message sent:', clientMessageId);
    } catch (error) {
      console.error('[DebugDialog] Failed to send message:', error);
      toast.error(t('pipelines.debugDialog.sendFailed'));
    } finally {
      inputRef.current?.focus();
    }
  };

  const renderMessageContent = (message: Message) => {
    return (
      <span className="text-base leading-relaxed align-middle whitespace-pre-wrap">
        {(message.message_chain as MessageComponent[]).map(
          (component, index) => {
            if (component.type === 'At') {
              return (
                <AtBadge
                  key={index}
                  targetName={component.target || ''}
                  readonly={true}
                />
              );
            } else if (component.type === 'Plain') {
              return <span key={index}>{component.text}</span>;
            }
            return null;
          },
        )}
      </span>
    );
  };

  const renderContent = () => (
    <div className="flex flex-1 h-full min-h-0">
      <div className="w-14 bg-white dark:bg-black p-2 pl-0  flex-shrink-0 flex flex-col justify-start gap-2">
        <Button
          variant="ghost"
          size="icon"
          className={`w-10 h-10 justify-center rounded-md transition-none ${
            sessionType === 'person'
              ? 'bg-[#2288ee] text-white hover:bg-[#2288ee] hover:text-white'
              : 'bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'
          } border-0 shadow-none`}
          onClick={() => setSessionType('person')}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            className="w-6 h-6"
          >
            <path d="M4 22C4 17.5817 7.58172 14 12 14C16.4183 14 20 17.5817 20 22H18C18 18.6863 15.3137 16 12 16C8.68629 16 6 18.6863 6 22H4ZM12 13C8.685 13 6 10.315 6 7C6 3.685 8.685 1 12 1C15.315 1 18 3.685 18 7C18 10.315 15.315 13 12 13ZM12 11C14.21 11 16 9.21 16 7C16 4.79 14.21 3 12 3C9.79 3 8 4.79 8 7C8 9.21 9.79 11 12 11Z"></path>
          </svg>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className={`w-10 h-10 justify-center rounded-md transition-none ${
            sessionType === 'group'
              ? 'bg-[#2288ee] text-white hover:bg-[#2288ee] hover:text-white'
              : 'bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'
          } border-0 shadow-none`}
          onClick={() => setSessionType('group')}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            className="w-6 h-6"
          >
            <path d="M2 22C2 17.5817 5.58172 14 10 14C14.4183 14 18 17.5817 18 22H16C16 18.6863 13.3137 16 10 16C6.68629 16 4 18.6863 4 22H2ZM10 13C6.685 13 4 10.315 4 7C4 3.685 6.685 1 10 1C13.315 1 16 3.685 16 7C16 10.315 13.315 13 10 13ZM10 11C12.21 11 14 9.21 14 7C14 4.79 12.21 3 10 3C7.79 3 6 4.79 6 7C6 9.21 7.79 11 10 11ZM18.2837 14.7028C21.0644 15.9561 23 18.752 23 22H21C21 19.564 19.5483 17.4671 17.4628 16.5271L18.2837 14.7028ZM17.5962 3.41321C19.5944 4.23703 21 6.20361 21 8.5C21 11.3702 18.8042 13.7252 16 13.9776V11.9646C17.6967 11.7222 19 10.264 19 8.5C19 7.11935 18.2016 5.92603 17.041 5.35635L17.5962 3.41321Z"></path>
          </svg>
        </Button>
        <div className="flex-1" />
      </div>

      <div className="flex-1 flex flex-col w-[10rem] h-full min-h-0">
        <ScrollArea className="flex-1 p-6 overflow-y-auto min-h-0 bg-white dark:bg-black">
          <div className="space-y-6">
            {messages.length === 0 ? (
              <div className="text-center text-muted-foreground py-12 text-lg">
                {t('pipelines.debugDialog.noMessages')}
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id + message.timestamp}
                  className={cn(
                    'flex',
                    message.role === 'user' ? 'justify-end' : 'justify-start',
                  )}
                >
                  <div
                    className={cn(
                      'max-w-md px-5 py-3 rounded-2xl',
                      message.role === 'user'
                        ? 'bg-[#2288ee] text-white rounded-br-none'
                        : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-none',
                    )}
                  >
                    {renderMessageContent(message)}
                    <div
                      className={cn(
                        'text-xs mt-2',
                        message.role === 'user'
                          ? 'text-white/70'
                          : 'text-gray-500 dark:text-gray-400',
                      )}
                    >
                      {message.role === 'user'
                        ? t('pipelines.debugDialog.userMessage')
                        : t('pipelines.debugDialog.botMessage')}
                    </div>
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        <div className="p-4 pb-0 bg-white dark:bg-black flex gap-2">
          <div className="flex-1 flex items-center gap-2">
            {hasAt && (
              <AtBadge targetName="webchatbot" onRemove={handleAtRemove} />
            )}
            <div className="relative flex-1">
              <Input
                ref={inputRef}
                value={inputValue}
                onChange={handleInputChange}
                onKeyPress={handleKeyPress}
                placeholder={t('pipelines.debugDialog.inputPlaceholder', {
                  type:
                    sessionType === 'person'
                      ? t('pipelines.debugDialog.privateChat')
                      : t('pipelines.debugDialog.groupChat'),
                })}
                className="flex-1 rounded-md px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 focus:border-[#2288ee] transition-none text-base"
              />
              {showAtPopover && (
                <div
                  ref={popoverRef}
                  className="absolute bottom-full left-0 mb-2 w-auto rounded-md border bg-white dark:bg-gray-800 dark:border-gray-600 shadow-lg"
                >
                  <div
                    className={cn(
                      'flex items-center gap-2 px-4 py-1.5 rounded cursor-pointer',
                      isHovering
                        ? 'bg-gray-100 dark:bg-gray-700'
                        : 'bg-white dark:bg-gray-800',
                    )}
                    onClick={handleAtSelect}
                    onMouseEnter={() => setIsHovering(true)}
                    onMouseLeave={() => setIsHovering(false)}
                  >
                    <span className="text-gray-800 dark:text-gray-200">
                      @webchatbot - {t('pipelines.debugDialog.atTips')}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
          <Button
            onClick={sendMessage}
            disabled={!inputValue.trim() && !hasAt}
            className="rounded-md bg-[#2288ee] hover:bg-[#2288ee] w-20 text-white px-6 py-2 text-base font-medium transition-none flex items-center gap-2 shadow-none"
          >
            <>{t('pipelines.debugDialog.send')}</>
          </Button>
        </div>
      </div>
    </div>
  );

  // 如果是嵌入模式，直接返回内容
  if (isEmbedded) {
    return (
      <div className="flex flex-col h-full min-h-0">
        <div className="flex-1 min-h-0 flex flex-col">{renderContent()}</div>
      </div>
    );
  }

  // 原有的Dialog包装
  return (
    <DialogContent className="!max-w-[70vw] max-w-6xl h-[70vh] p-6 flex flex-col rounded-2xl shadow-2xl bg-white dark:bg-black">
      {renderContent()}
    </DialogContent>
  );
}
