import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import { DialogContent } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import {
  Message,
  MessageChainComponent,
  Image,
  Plain,
  At,
  Quote,
  Voice,
  Source,
} from '@/app/infra/entities/message';
import { toast } from 'sonner';
import AtBadge from './AtBadge';
import { WebSocketClient } from '@/app/infra/websocket/WebSocketClient';
import ImagePreviewDialog from './ImagePreviewDialog';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import rehypeRaw from 'rehype-raw';
import rehypeSlug from 'rehype-slug';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';
import '@/styles/github-markdown.css';

interface DebugDialogProps {
  open: boolean;
  pipelineId: string;
  isEmbedded?: boolean;
  onConnectionStatusChange?: (isConnected: boolean) => void;
}

export default function DebugDialog({
  open,
  pipelineId,
  isEmbedded = false,
  onConnectionStatusChange,
}: DebugDialogProps) {
  const { t } = useTranslation();
  const [selectedPipelineId, setSelectedPipelineId] = useState(pipelineId);
  const [sessionType, setSessionType] = useState<'person' | 'group'>('person');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [showAtPopover, setShowAtPopover] = useState(false);
  const [hasAt, setHasAt] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [selectedImages, setSelectedImages] = useState<
    Array<{ file: File; preview: string; fileKey?: string }>
  >([]);
  const [isUploading, setIsUploading] = useState(false);
  const [previewImageUrl, setPreviewImageUrl] = useState<string>('');
  const [showImagePreview, setShowImagePreview] = useState(false);
  const [quotedMessage, setQuotedMessage] = useState<Message | null>(null);
  const [rawModeMessages, setRawModeMessages] = useState<Set<string>>(
    new Set(),
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const wsClientRef = useRef<WebSocketClient | null>(null);
  const isInitializingRef = useRef<boolean>(false);

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

  const loadMessages = useCallback(
    async (pipelineId: string) => {
      try {
        const response = await httpClient.getWebSocketHistoryMessages(
          pipelineId,
          sessionType,
        );
        setMessages(response.messages);
      } catch (error) {
        console.error('Failed to load messages:', error);
      }
    },
    [sessionType],
  );

  // 初始化WebSocket连接
  const initWebSocket = useCallback(
    async (pipelineId: string) => {
      // 防止重复初始化
      if (isInitializingRef.current) {
        return;
      }

      try {
        isInitializingRef.current = true;

        // 断开旧连接
        if (wsClientRef.current) {
          wsClientRef.current.disconnect();
          wsClientRef.current = null;
        }

        // 创建新连接
        const wsClient = new WebSocketClient(pipelineId, sessionType);

        wsClient
          .onConnected(() => {
            setIsConnected(true);
            isInitializingRef.current = false;
          })
          .onMessage((wsMessage) => {
            // 将 WebSocketMessage 转换为 Message 类型
            const message: Message = {
              ...wsMessage,
              message_chain: wsMessage.message_chain as MessageChainComponent[],
            };

            setMessages((prevMessages) => {
              // 查找是否已存在相同ID的消息
              const existingIndex = prevMessages.findIndex(
                (m) => m.id === message.id,
              );

              if (existingIndex >= 0) {
                // 更新已存在的消息（流式输出）
                const newMessages = [...prevMessages];
                newMessages[existingIndex] = message;
                return newMessages;
              } else {
                // 添加新消息
                return [...prevMessages, message];
              }
            });
          })
          .onError((error) => {
            console.error('WebSocket错误:', error);
            setIsConnected(false);
            isInitializingRef.current = false;
            toast.error(t('pipelines.debugDialog.connectionError'));
          })
          .onClose(() => {
            setIsConnected(false);
            isInitializingRef.current = false;
          })
          .onBroadcast((message) => {
            toast.info(message);
          });

        await wsClient.connect();
        wsClientRef.current = wsClient;
      } catch (error) {
        console.error('WebSocket连接失败:', error);
        setIsConnected(false);
        isInitializingRef.current = false;
        toast.error(t('pipelines.debugDialog.connectionFailed'));
      }
    },
    [sessionType, t],
  );

  // 在useEffect中监听messages变化时滚动
  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // 监听 open 和 pipelineId 变化，进入时连接，离开时断开
  useEffect(() => {
    if (open) {
      setSelectedPipelineId(pipelineId);
    } else {
      // 关闭对话框时立即断开WebSocket
      if (wsClientRef.current) {
        wsClientRef.current.disconnect();
        wsClientRef.current = null;
        setIsConnected(false);
        isInitializingRef.current = false;
      }
    }

    return () => {
      // 组件卸载时断开WebSocket
      if (wsClientRef.current) {
        wsClientRef.current.disconnect();
        wsClientRef.current = null;
        isInitializingRef.current = false;
      }
    };
  }, [open, pipelineId]);

  // 监听 sessionType 和 selectedPipelineId 变化，重新加载消息和连接
  useEffect(() => {
    if (open) {
      loadMessages(selectedPipelineId);
      initWebSocket(selectedPipelineId);
    }
  }, [sessionType, selectedPipelineId, open, loadMessages, initWebSocket]);

  // 通知父组件连接状态变化
  useEffect(() => {
    onConnectionStatusChange?.(isConnected);
  }, [isConnected, onConnectionStatusChange]);

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

  const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const newImages: Array<{ file: File; preview: string }> = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (file.type.startsWith('image/')) {
        const preview = URL.createObjectURL(file);
        newImages.push({ file, preview });
      }
    }

    setSelectedImages((prev) => [...prev, ...newImages]);
  };

  const handleRemoveImage = (index: number) => {
    setSelectedImages((prev) => {
      const newImages = [...prev];
      URL.revokeObjectURL(newImages[index].preview);
      newImages.splice(index, 1);
      return newImages;
    });
  };

  const sendMessage = async () => {
    if (
      !inputValue.trim() &&
      !hasAt &&
      selectedImages.length === 0 &&
      !quotedMessage
    )
      return;
    if (!isConnected || !wsClientRef.current) {
      toast.error(t('pipelines.debugDialog.notConnected'));
      return;
    }

    try {
      setIsUploading(true);

      const messageChain = [];

      // 添加引用消息(如果有)
      if (quotedMessage) {
        // 获取被引用消息的Source组件以获取message_id
        const sourceComponent = quotedMessage.message_chain.find(
          (c) => c.type === 'Source',
        ) as Source | undefined;
        const messageId = sourceComponent
          ? sourceComponent.id
          : quotedMessage.id;

        messageChain.push({
          type: 'Quote',
          id: messageId,
          origin: quotedMessage.message_chain.filter(
            (c) => c.type !== 'Source',
          ),
        });
      }

      let text_content = inputValue.trim();
      if (hasAt) {
        text_content = ' ' + text_content;
      }

      if (hasAt) {
        messageChain.push({
          type: 'At',
          target: 'websocketbot',
          display: 'websocketbot',
        });
      }

      // 添加文本
      if (text_content) {
        messageChain.push({
          type: 'Plain',
          text: text_content,
        });
      }

      // 上传图片并添加到消息链
      for (const image of selectedImages) {
        try {
          const result = await httpClient.uploadWebSocketImage(
            selectedPipelineId,
            image.file,
          );
          messageChain.push({
            type: 'Image',
            path: result.file_key,
          });
        } catch (error) {
          console.error('图片上传失败:', error);
          toast.error(t('pipelines.debugDialog.imageUploadFailed'));
        }
      }

      // 清空输入框、图片和引用消息
      setInputValue('');
      setHasAt(false);
      setQuotedMessage(null);
      selectedImages.forEach((img) => URL.revokeObjectURL(img.preview));
      setSelectedImages([]);

      // 通过WebSocket发送消息
      // 不在本地添加消息，等待后端广播回来（带有正确的ID）
      wsClientRef.current.sendMessage(messageChain);
    } catch (error) {
      console.error('Failed to send message:', error);
      toast.error(t('pipelines.debugDialog.sendFailed'));
    } finally {
      setIsUploading(false);
      inputRef.current?.focus();
    }
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
        // 优先使用 display，如果没有则使用 target
        const displayName =
          atComponent.display || atComponent.target?.toString() || '';
        return (
          <span key={index} className="inline-flex align-middle mx-1">
            <AtBadge targetName={displayName} readonly={true} />
          </span>
        );
      }

      case 'AtAll':
        return (
          <span key={index} className="inline-flex align-middle mx-1">
            <AtBadge targetName="全体成员" readonly={true} />
          </span>
        );

      case 'Image': {
        const img = component as Image;
        const imageUrl = img.url || (img.base64 ? img.base64 : '');

        if (!imageUrl) return null;

        return (
          <div key={index} className="my-2">
            <img
              src={imageUrl}
              alt="Image"
              className="max-w-full max-h-96 rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
              onClick={() => {
                setPreviewImageUrl(imageUrl);
                setShowImagePreview(true);
              }}
            />
          </div>
        );
      }

      case 'File': {
        const file = component as MessageChainComponent & { name?: string };
        return (
          <div key={index} className="my-2 flex items-center gap-2 text-sm">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M8 4a3 3 0 00-3 3v4a5 5 0 0010 0V7a1 1 0 112 0v4a7 7 0 11-14 0V7a5 5 0 0110 0v4a3 3 0 11-6 0V7a1 1 0 012 0v4a1 1 0 102 0V7a3 3 0 00-3-3z" />
            </svg>
            <span>[文件] {file.name || 'Unknown'}</span>
          </div>
        );
      }

      case 'Voice': {
        const voice = component as Voice;
        const voiceUrl = voice.url || (voice.base64 ? voice.base64 : '');

        if (!voiceUrl) {
          return <span key={index}>[语音]</span>;
        }

        return (
          <div key={index} className="my-2 flex items-center gap-2">
            <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 dark:bg-gray-800 rounded-lg">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z" />
              </svg>
              <audio
                controls
                src={voiceUrl}
                className="h-8"
                style={{ maxWidth: '200px' }}
              >
                Your browser does not support the audio element.
              </audio>
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
            className="mb-2 pl-3 border-l-2 border-gray-400 dark:border-gray-500"
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
        // Source 不显示
        return null;

      default:
        return <span key={index}>[{component.type}]</span>;
    }
  };

  const getMessageTimestamp = (message: Message): number => {
    // 首先尝试从message_chain中的Source组件获取时间戳
    const sourceComponent = message.message_chain.find(
      (c) => c.type === 'Source',
    ) as Source | undefined;

    if (sourceComponent && sourceComponent.timestamp) {
      return sourceComponent.timestamp;
    }

    // 如果没有Source组件，使用message.timestamp
    // 假设timestamp是ISO字符串，转换为Unix时间戳（秒）
    if (message.timestamp) {
      return Math.floor(new Date(message.timestamp).getTime() / 1000);
    }

    return 0;
  };

  const formatTimestamp = (timestamp: number): string => {
    if (!timestamp) return '';

    const date = new Date(timestamp * 1000);
    const now = new Date();

    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');

    // 判断是否是今天
    const isToday = now.toDateString() === date.toDateString();
    if (isToday) {
      return `${hours}:${minutes}`;
    }

    // 判断是否是昨天
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const isYesterday = yesterday.toDateString() === date.toDateString();
    if (isYesterday) {
      return `${t('bots.yesterday')} ${hours}:${minutes}`;
    }

    // 判断是否是今年
    const isThisYear = now.getFullYear() === date.getFullYear();
    if (isThisYear) {
      const month = date.getMonth() + 1;
      const day = date.getDate();
      return t('bots.dateFormat', { month, day });
    }

    // 更早的日期
    return t('bots.earlier');
  };

  // Generate a unique key for a message
  const getMessageKey = (message: Message): string => {
    return `${message.id}-${message.timestamp}`;
  };

  // Toggle raw mode for a message (by default, messages are in markdown mode)
  const toggleRawMode = (message: Message) => {
    const key = getMessageKey(message);
    setRawModeMessages((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(key)) {
        newSet.delete(key);
      } else {
        newSet.add(key);
      }
      return newSet;
    });
  };

  // Check if message has any Plain text content
  const hasPlainText = (message: Message): boolean => {
    return message.message_chain.some((c) => c.type === 'Plain');
  };

  // Extract plain text from message chain
  const getPlainText = (message: Message): string => {
    return message.message_chain
      .filter((c) => c.type === 'Plain')
      .map((c) => (c as Plain).text)
      .join('');
  };

  const renderMessageContent = (message: Message) => {
    const key = getMessageKey(message);
    const isRawMode = rawModeMessages.has(key);

    // By default, render with markdown if there's plain text (unless raw mode is enabled)
    if (!isRawMode && hasPlainText(message)) {
      const plainText = getPlainText(message);
      const nonPlainComponents = message.message_chain.filter(
        (c) => c.type !== 'Plain' && c.type !== 'Source',
      );

      return (
        <div className="text-base leading-relaxed align-middle">
          {/* Render non-Plain components first */}
          {nonPlainComponents.map((component, index) =>
            renderMessageComponent(component, index),
          )}
          {/* Render Plain text as markdown */}
          <div className="markdown-body">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[
                rehypeRaw,
                rehypeHighlight,
                rehypeSlug,
                [
                  rehypeAutolinkHeadings,
                  {
                    behavior: 'wrap',
                    properties: {
                      className: ['anchor'],
                    },
                  },
                ],
              ]}
              components={{
                ul: ({ children }) => <ul className="list-disc">{children}</ul>,
                ol: ({ children }) => (
                  <ol className="list-decimal">{children}</ol>
                ),
                li: ({ children }) => <li className="ml-4">{children}</li>,
                img: ({ src, alt, ...props }) => {
                  const imageSrc = src || '';

                  if (typeof imageSrc !== 'string') {
                    return (
                      <img
                        src={src}
                        alt={alt || ''}
                        className="max-w-full h-auto rounded-lg my-4"
                        {...props}
                      />
                    );
                  }

                  return (
                    <img
                      src={imageSrc}
                      alt={alt || ''}
                      className="max-w-lg h-auto my-4"
                      {...props}
                    />
                  );
                },
              }}
            >
              {plainText}
            </ReactMarkdown>
          </div>
        </div>
      );
    }

    return (
      <div className="text-base leading-relaxed align-middle whitespace-pre-wrap">
        {message.message_chain.map((component, index) =>
          renderMessageComponent(component, index),
        )}
      </div>
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
      </div>

      <div className="flex-1 flex flex-col w-[10rem] h-full min-h-0">
        <ScrollArea className="flex-1 p-6 overflow-y-auto min-h-0 bg-white dark:bg-black scroll-area">
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
                      'max-w-3xl px-5 py-3 rounded-2xl',
                      message.role === 'user'
                        ? 'user-message-bubble bg-blue-100 dark:bg-blue-900 text-gray-900 dark:text-gray-100 rounded-br-none'
                        : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-none',
                    )}
                  >
                    {renderMessageContent(message)}
                    <div
                      className={cn(
                        'text-xs mt-2 flex items-center justify-between gap-2',
                        message.role === 'user'
                          ? 'text-gray-600 dark:text-gray-300'
                          : 'text-gray-500 dark:text-gray-400',
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <span>
                          {message.role === 'user'
                            ? t('pipelines.debugDialog.userMessage')
                            : t('pipelines.debugDialog.botMessage')}
                        </span>
                        {hasPlainText(message) && (
                          <button
                            onClick={() => toggleRawMode(message)}
                            className={cn(
                              'px-1.5 py-0.5 rounded text-[10px] transition-colors',
                              message.role === 'user'
                                ? 'hover:bg-blue-200 dark:hover:bg-blue-800'
                                : 'hover:bg-gray-200 dark:hover:bg-gray-700',
                            )}
                            title={
                              rawModeMessages.has(getMessageKey(message))
                                ? t('pipelines.debugDialog.showMarkdown')
                                : t('pipelines.debugDialog.showRaw')
                            }
                          >
                            {rawModeMessages.has(getMessageKey(message)) ? (
                              <span className="flex items-center gap-0.5">
                                <svg
                                  className="w-3 h-3"
                                  viewBox="0 0 16 16"
                                  fill="currentColor"
                                >
                                  <path d="M14.85 3H1.15C.52 3 0 3.52 0 4.15v7.69C0 12.48.52 13 1.15 13h13.69c.64 0 1.15-.52 1.15-1.15v-7.7C16 3.52 15.48 3 14.85 3zM9 11H7V8L5.5 9.92 4 8v3H2V5h2l1.5 2L7 5h2v6zm2.99.5L9.5 8H11V5h2v3h1.5l-2.51 3.5z" />
                                </svg>
                                MD
                              </span>
                            ) : (
                              <span className="flex items-center gap-0.5">
                                <svg
                                  className="w-3 h-3"
                                  fill="none"
                                  viewBox="0 0 24 24"
                                  stroke="currentColor"
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M4 6h16M4 12h16M4 18h7"
                                  />
                                </svg>
                                {t('pipelines.debugDialog.showRaw')}
                              </span>
                            )}
                          </button>
                        )}
                        <button
                          onClick={() => setQuotedMessage(message)}
                          className={cn(
                            'px-1.5 py-0.5 rounded text-[10px] transition-colors flex items-center gap-0.5',
                            message.role === 'user'
                              ? 'hover:bg-blue-200 dark:hover:bg-blue-800'
                              : 'hover:bg-gray-200 dark:hover:bg-gray-700',
                          )}
                          title={t('pipelines.debugDialog.reply')}
                        >
                          <svg
                            className="w-3 h-3"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"
                            />
                          </svg>
                          {t('pipelines.debugDialog.reply')}
                        </button>
                      </div>
                      <span className="text-[10px]">
                        {formatTimestamp(getMessageTimestamp(message))}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* 引用消息预览区域 */}
        {quotedMessage && (
          <div className="px-4 py-2 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700">
            <div className="flex items-start gap-2">
              <div className="flex-1 pl-3 border-l-2 border-[#2288ee]">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                  {t('pipelines.debugDialog.replyTo')}{' '}
                  {quotedMessage.role === 'user'
                    ? t('pipelines.debugDialog.userMessage')
                    : t('pipelines.debugDialog.botMessage')}
                </div>
                <div className="text-sm text-gray-700 dark:text-gray-300 line-clamp-2">
                  {quotedMessage.message_chain
                    .filter((c) => c.type === 'Plain')
                    .map((c) => (c as Plain).text)
                    .join('')}
                </div>
              </div>
              <button
                onClick={() => setQuotedMessage(null)}
                className="w-5 h-5 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              >
                ×
              </button>
            </div>
          </div>
        )}

        {/* 图片预览区域 */}
        {selectedImages.length > 0 && (
          <div className="px-4 pb-2 bg-white dark:bg-black">
            <div className="flex gap-2 flex-wrap">
              {selectedImages.map((image, index) => (
                <div key={index} className="relative group">
                  <img
                    src={image.preview}
                    alt={`preview-${index}`}
                    className="w-20 h-20 object-cover rounded-lg border border-gray-300 dark:border-gray-600"
                  />
                  <button
                    onClick={() => handleRemoveImage(index)}
                    className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="p-4 pb-0 bg-white dark:bg-black flex gap-2">
          <div className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              onChange={handleImageSelect}
              className="hidden"
            />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => fileInputRef.current?.click()}
              disabled={!isConnected || isUploading}
              className="w-10 h-10 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
              title="上传图片"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
            </Button>
          </div>
          <div className="flex-1 flex items-center gap-2">
            {hasAt && (
              <AtBadge targetName="websocketbot" onRemove={handleAtRemove} />
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
                disabled={!isConnected || isUploading}
                className="flex-1 rounded-md px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 focus:border-[#2288ee] transition-none text-base disabled:opacity-50"
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
                      @websocketbot - {t('pipelines.debugDialog.atTips')}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
          <Button
            onClick={sendMessage}
            disabled={
              (!inputValue.trim() &&
                !hasAt &&
                selectedImages.length === 0 &&
                !quotedMessage) ||
              !isConnected ||
              isUploading
            }
            className="rounded-md bg-[#2288ee] hover:bg-[#2288ee] w-20 text-white px-6 py-2 text-base font-medium transition-none flex items-center gap-2 shadow-none disabled:opacity-50"
          >
            {isUploading ? '上传中...' : t('pipelines.debugDialog.send')}
          </Button>
        </div>
      </div>
    </div>
  );

  // 如果是嵌入模式，直接返回内容
  if (isEmbedded) {
    return (
      <>
        <div className="flex flex-col h-full min-h-0">
          <div className="flex-1 min-h-0 flex flex-col">{renderContent()}</div>
        </div>
        <ImagePreviewDialog
          open={showImagePreview}
          imageUrl={previewImageUrl}
          onClose={() => setShowImagePreview(false)}
        />
      </>
    );
  }

  // 原有的Dialog包装
  return (
    <>
      <DialogContent className="!max-w-[70vw] max-w-6xl h-[70vh] p-6 flex flex-col rounded-2xl shadow-2xl bg-white dark:bg-black">
        {renderContent()}
      </DialogContent>
      <ImagePreviewDialog
        open={showImagePreview}
        imageUrl={previewImageUrl}
        onClose={() => setShowImagePreview(false)}
      />
    </>
  );
}
