import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import { DialogContent } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Switch } from '@/components/ui/switch';
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
import rehypeSanitize from 'rehype-sanitize';
import rehypeSlug from 'rehype-slug';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';
import '@/styles/github-markdown.css';
import {
  User,
  Users,
  ImageIcon,
  Paperclip,
  Send,
  Reply,
  FileText,
  Music,
  Code,
  AlignLeft,
} from 'lucide-react';

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
  const [streamOutput, setStreamOutput] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const wsClientRef = useRef<WebSocketClient | null>(null);
  const isInitializingRef = useRef<boolean>(false);

  const scrollToBottom = useCallback(() => {
    // Use setTimeout to ensure scroll happens after DOM update
    setTimeout(() => {
      const scrollArea = document.querySelector('.scroll-area') as HTMLElement;
      if (scrollArea) {
        scrollArea.scrollTo({
          top: scrollArea.scrollHeight,
          behavior: 'smooth',
        });
      }
      // Also ensure messagesEndRef scrolls into view
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

  // Initialize WebSocket connection
  const initWebSocket = useCallback(
    async (pipelineId: string) => {
      // Prevent duplicate initialization
      if (isInitializingRef.current) {
        return;
      }

      try {
        isInitializingRef.current = true;

        // Disconnect old connection
        if (wsClientRef.current) {
          wsClientRef.current.disconnect();
          wsClientRef.current = null;
        }

        // Create new connection
        const wsClient = new WebSocketClient(pipelineId, sessionType);

        wsClient
          .onConnected(() => {
            setIsConnected(true);
            isInitializingRef.current = false;
          })
          .onMessage((wsMessage) => {
            // Convert WebSocketMessage to Message type
            const message: Message = {
              ...wsMessage,
              message_chain: wsMessage.message_chain as MessageChainComponent[],
            };

            setMessages((prevMessages) => {
              // Check if message with same ID already exists
              const existingIndex = prevMessages.findIndex(
                (m) => m.id === message.id,
              );

              if (existingIndex >= 0) {
                // Update existing message (streaming output)
                const newMessages = [...prevMessages];
                newMessages[existingIndex] = message;
                return newMessages;
              } else {
                // Add new message
                return [...prevMessages, message];
              }
            });
          })
          .onError((error) => {
            console.error('WebSocket error:', error);
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
        console.error('WebSocket connection failed:', error);
        setIsConnected(false);
        isInitializingRef.current = false;
        toast.error(t('pipelines.debugDialog.connectionFailed'));
      }
    },
    [sessionType, t],
  );

  // Scroll when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Watch open and pipelineId changes: connect on open, disconnect on close
  useEffect(() => {
    if (open) {
      setSelectedPipelineId(pipelineId);
    } else {
      // Disconnect WebSocket immediately when dialog closes
      if (wsClientRef.current) {
        wsClientRef.current.disconnect();
        wsClientRef.current = null;
        setIsConnected(false);
        isInitializingRef.current = false;
      }
    }

    return () => {
      // Disconnect WebSocket on component unmount
      if (wsClientRef.current) {
        wsClientRef.current.disconnect();
        wsClientRef.current = null;
        isInitializingRef.current = false;
      }
    };
  }, [open, pipelineId]);

  // Reload messages and reconnect when sessionType or selectedPipelineId changes
  useEffect(() => {
    if (open) {
      // Clear current messages to avoid showing stale messages
      setMessages([]);
      loadMessages(selectedPipelineId);
      initWebSocket(selectedPipelineId);
    }
  }, [sessionType, selectedPipelineId, open, loadMessages, initWebSocket]);

  // Notify parent of connection status changes
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

      // Add quoted message if present
      if (quotedMessage) {
        // Get message_id from the quoted message Source component
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

      // Add text content
      if (text_content) {
        messageChain.push({
          type: 'Plain',
          text: text_content,
        });
      }

      // Upload images and add to message chain
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
          console.error('Image upload failed:', error);
          toast.error(t('pipelines.debugDialog.imageUploadFailed'));
        }
      }

      // Clear input, images, and quoted message
      setInputValue('');
      setHasAt(false);
      setQuotedMessage(null);
      selectedImages.forEach((img) => URL.revokeObjectURL(img.preview));
      setSelectedImages([]);

      // Send message via WebSocket
      // Do not add locally; wait for backend broadcast with correct ID
      wsClientRef.current.sendMessage(messageChain, streamOutput);
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
        // Prefer display name, fall back to target
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
            <AtBadge
              targetName={t('pipelines.debugDialog.allMembers')}
              readonly={true}
            />
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
            <Paperclip className="size-4" />
            <span>
              [{t('pipelines.debugDialog.file')}] {file.name || 'Unknown'}
            </span>
          </div>
        );
      }

      case 'Voice': {
        const voice = component as Voice;
        const voiceUrl = voice.url || (voice.base64 ? voice.base64 : '');

        if (!voiceUrl) {
          return <span key={index}>[{t('pipelines.debugDialog.voice')}]</span>;
        }

        return (
          <div key={index} className="my-2 flex items-center gap-2">
            <div className="flex items-center gap-2 px-3 py-2 bg-muted rounded-lg">
              <Music className="size-5" />
              <audio
                controls
                src={voiceUrl}
                className="h-8"
                style={{ maxWidth: '200px' }}
              >
                Your browser does not support the audio element.
              </audio>
              {voice.length && voice.length > 0 && (
                <span className="text-xs text-muted-foreground">
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
            className="mb-2 pl-3 border-l-2 border-muted-foreground/50"
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
        // Source is not rendered
        return null;

      default:
        return <span key={index}>[{component.type}]</span>;
    }
  };

  const getMessageTimestamp = (message: Message): number => {
    // Try to get timestamp from Source component in message_chain
    const sourceComponent = message.message_chain.find(
      (c) => c.type === 'Source',
    ) as Source | undefined;

    if (sourceComponent && sourceComponent.timestamp) {
      return sourceComponent.timestamp;
    }

    // Fall back to message.timestamp if no Source component
    // Assume ISO string, convert to Unix timestamp (seconds)
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

    // Check if today
    const isToday = now.toDateString() === date.toDateString();
    if (isToday) {
      return `${hours}:${minutes}`;
    }

    // Check if yesterday
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const isYesterday = yesterday.toDateString() === date.toDateString();
    if (isYesterday) {
      return `${t('bots.yesterday')} ${hours}:${minutes}`;
    }

    // Check if this year
    const isThisYear = now.getFullYear() === date.getFullYear();
    if (isThisYear) {
      const month = date.getMonth() + 1;
      const day = date.getDate();
      return t('bots.dateFormat', { month, day });
    }

    // Earlier dates
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
                rehypeSanitize,
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
      <div className="w-14 p-2 pl-0 shrink-0 flex flex-col justify-start gap-2">
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            'w-10 h-10 justify-center rounded-md transition-none border-0 shadow-none',
            sessionType === 'person'
              ? 'bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground'
              : 'bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground',
          )}
          onClick={() => setSessionType('person')}
        >
          <User className="size-5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            'w-10 h-10 justify-center rounded-md transition-none border-0 shadow-none',
            sessionType === 'group'
              ? 'bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground'
              : 'bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground',
          )}
          onClick={() => setSessionType('group')}
        >
          <Users className="size-5" />
        </Button>
      </div>

      <div className="flex-1 flex flex-col w-[10rem] h-full min-h-0">
        <ScrollArea className="flex-1 p-6 overflow-y-auto min-h-0 scroll-area">
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
                        ? 'user-message-bubble bg-primary/10 text-foreground rounded-br-none'
                        : 'bg-muted text-foreground rounded-bl-none',
                    )}
                  >
                    {renderMessageContent(message)}
                    <div
                      className={cn(
                        'text-xs mt-2 flex items-center justify-between gap-2',
                        'text-muted-foreground',
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
                            type="button"
                            onClick={() => toggleRawMode(message)}
                            className={cn(
                              'px-1.5 py-0.5 rounded text-[10px] transition-colors',
                              'hover:bg-accent',
                            )}
                            title={
                              rawModeMessages.has(getMessageKey(message))
                                ? t('pipelines.debugDialog.showMarkdown')
                                : t('pipelines.debugDialog.showRaw')
                            }
                          >
                            {rawModeMessages.has(getMessageKey(message)) ? (
                              <span className="flex items-center gap-0.5">
                                <Code className="size-3" />
                                MD
                              </span>
                            ) : (
                              <span className="flex items-center gap-0.5">
                                <AlignLeft className="size-3" />
                                {t('pipelines.debugDialog.showRaw')}
                              </span>
                            )}
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => setQuotedMessage(message)}
                          className={cn(
                            'px-1.5 py-0.5 rounded text-[10px] transition-colors flex items-center gap-0.5',
                            'hover:bg-accent',
                          )}
                          title={t('pipelines.debugDialog.reply')}
                        >
                          <Reply className="size-3" />
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

        {/* Quoted message preview */}
        {quotedMessage && (
          <div className="px-4 py-2 bg-muted/50 border-t">
            <div className="flex items-start gap-2">
              <div className="flex-1 pl-3 border-l-2 border-primary">
                <div className="text-xs text-muted-foreground mb-1">
                  {t('pipelines.debugDialog.replyTo')}{' '}
                  {quotedMessage.role === 'user'
                    ? t('pipelines.debugDialog.userMessage')
                    : t('pipelines.debugDialog.botMessage')}
                </div>
                <div className="text-sm text-foreground/70 line-clamp-2">
                  {quotedMessage.message_chain
                    .filter((c) => c.type === 'Plain')
                    .map((c) => (c as Plain).text)
                    .join('')}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setQuotedMessage(null)}
                className="w-5 h-5 text-muted-foreground hover:text-foreground"
              >
                ×
              </button>
            </div>
          </div>
        )}

        {/* Image preview area */}
        {selectedImages.length > 0 && (
          <div className="px-4 pb-2">
            <div className="flex gap-2 flex-wrap">
              {selectedImages.map((image, index) => (
                <div key={index} className="relative group">
                  <img
                    src={image.preview}
                    alt={`preview-${index}`}
                    className="w-20 h-20 object-cover rounded-lg border"
                  />
                  <button
                    type="button"
                    onClick={() => handleRemoveImage(index)}
                    className="absolute -top-2 -right-2 w-5 h-5 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="p-4 pb-0 flex gap-2">
          <div className="flex gap-2 items-center">
            <div className="flex items-center gap-1">
              <span className="text-xs text-muted-foreground">
                {t('pipelines.debugDialog.streamOutput')}
              </span>
              <Switch
                checked={streamOutput}
                onCheckedChange={setStreamOutput}
                disabled={!isConnected}
              />
            </div>
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
              className="w-10 h-10 rounded-md hover:bg-accent"
              title={t('pipelines.debugDialog.uploadImage')}
            >
              <ImageIcon className="size-5" />
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
                className="flex-1 rounded-md px-3 py-2 transition-none text-base disabled:opacity-50"
              />
              {showAtPopover && (
                <div
                  ref={popoverRef}
                  className="absolute bottom-full left-0 mb-2 w-auto rounded-md border bg-popover text-popover-foreground shadow-lg"
                >
                  <div
                    className={cn(
                      'flex items-center gap-2 px-4 py-1.5 rounded cursor-pointer',
                      isHovering ? 'bg-accent' : '',
                    )}
                    onClick={handleAtSelect}
                    onMouseEnter={() => setIsHovering(true)}
                    onMouseLeave={() => setIsHovering(false)}
                  >
                    <span>
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
            className="rounded-md w-20 px-6 py-2 text-base font-medium transition-none flex items-center gap-2 shadow-none disabled:opacity-50"
          >
            {isUploading ? (
              t('pipelines.debugDialog.uploading')
            ) : (
              <>
                <Send className="size-4" />
                {t('pipelines.debugDialog.send')}
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );

  // Embedded mode: return content directly
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

  // Dialog wrapper mode
  return (
    <>
      <DialogContent className="!max-w-[70vw] max-w-6xl h-[70vh] p-6 flex flex-col rounded-2xl shadow-2xl">
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
