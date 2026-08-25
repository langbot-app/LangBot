import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import { DialogContent } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
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
  File as FileComponent,
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
  Music,
  Code,
  AlignLeft,
  RotateCcw,
} from 'lucide-react';

interface DebugDialogProps {
  open: boolean;
  pipelineId: string;
  isEmbedded?: boolean;
  compact?: boolean;
  onConnectionStatusChange?: (isConnected: boolean) => void;
  beforeSend?: () => Promise<boolean>;
  hasUnsavedChanges?: boolean;
}

function AuthenticatedMessageImage({
  image,
  onOpen,
}: {
  image: Image;
  onOpen: (imageUrl: string) => void;
}) {
  const [downloadedUrl, setDownloadedUrl] = useState('');
  const directUrl =
    image.url ||
    (image.base64
      ? image.base64.startsWith('data:')
        ? image.base64
        : `data:image/jpeg;base64,${image.base64}`
      : '');

  useEffect(() => {
    if (directUrl || !image.path) return;

    let disposed = false;
    let objectUrl = '';
    const encodedPath = image.path
      .split('/')
      .map((segment) => encodeURIComponent(segment))
      .join('/');

    void httpClient
      .downloadFile(`/api/v1/files/image/${encodedPath}`)
      .then((response) => {
        objectUrl = URL.createObjectURL(response.data);
        if (disposed) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        setDownloadedUrl(objectUrl);
      })
      .catch((error) => {
        console.error('Failed to load Debug Chat image:', error);
      });

    return () => {
      disposed = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [directUrl, image.path]);

  const imageUrl = directUrl || downloadedUrl;
  if (!imageUrl) return null;

  return (
    <div className="my-2">
      <img
        src={imageUrl}
        alt="Image"
        data-debug-chat-message-image="true"
        className="max-w-full max-h-96 rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
        onClick={() => onOpen(imageUrl)}
      />
    </div>
  );
}

export default function DebugDialog({
  open,
  pipelineId,
  isEmbedded = false,
  compact = false,
  onConnectionStatusChange,
  beforeSend,
  hasUnsavedChanges = false,
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
    Array<{
      file: File;
      preview: string;
      fileKey?: string;
      kind: 'image' | 'voice' | 'file';
    }>
  >([]);
  const [isUploading, setIsUploading] = useState(false);
  const [previewImageUrl, setPreviewImageUrl] = useState<string>('');
  const [showImagePreview, setShowImagePreview] = useState(false);
  const [quotedMessage, setQuotedMessage] = useState<Message | null>(null);
  const [rawModeMessages, setRawModeMessages] = useState<Set<string>>(
    new Set(),
  );
  const [streamOutput, setStreamOutput] = useState(true);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const wsClientRef = useRef<WebSocketClient | null>(null);
  const isInitializingRef = useRef<boolean>(false);
  const historyRequestGenerationRef = useRef(0);

  const invalidateHistoryRequests = useCallback(() => {
    historyRequestGenerationRef.current++;
  }, []);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      const viewport = scrollAreaRef.current?.querySelector<HTMLElement>(
        '[data-slot="scroll-area-viewport"]',
      );
      viewport?.scrollTo({
        top: viewport.scrollHeight,
        behavior: 'smooth',
      });
    }, 0);
  }, []);

  const loadMessages = useCallback(
    async (pipelineId: string) => {
      const generation = ++historyRequestGenerationRef.current;
      try {
        const response = await httpClient.getWebSocketHistoryMessages(
          pipelineId,
          sessionType,
        );
        if (generation !== historyRequestGenerationRef.current) return;
        setMessages(Array.isArray(response.messages) ? response.messages : []);
      } catch (error) {
        if (generation !== historyRequestGenerationRef.current) return;
        console.error('Failed to load messages:', error);
      }
    },
    [sessionType],
  );

  const resetConversation = useCallback(async () => {
    try {
      await httpClient.resetWebSocketSession(selectedPipelineId, sessionType);
      invalidateHistoryRequests();
      setMessages([]);
      setQuotedMessage(null);
      toast.success(t('pipelines.debugDialog.resetSuccess'));
    } catch (error) {
      console.error('Failed to reset Debug Chat session:', error);
      toast.error(t('pipelines.debugDialog.resetFailed'));
    }
  }, [invalidateHistoryRequests, selectedPipelineId, sessionType, t]);

  // Initialize WebSocket connection
  const initWebSocket = useCallback(
    async (pipelineId: string) => {
      // Prevent duplicate initialization
      if (isInitializingRef.current) {
        return;
      }

      let wsClient: WebSocketClient | null = null;
      let errorReported = false;
      try {
        isInitializingRef.current = true;

        // Disconnect old connection
        const previousClient = wsClientRef.current;
        wsClientRef.current = null;
        previousClient?.disconnect();

        // Create new connection
        wsClient = new WebSocketClient(pipelineId, sessionType);
        // Store the client before awaiting connect so effect cleanup can also
        // cancel sockets that are still authenticating.
        wsClientRef.current = wsClient;

        wsClient
          .onConnected(() => {
            if (wsClientRef.current !== wsClient) return;
            setIsConnected(true);
            isInitializingRef.current = false;
          })
          .onMessage((wsMessage) => {
            if (wsClientRef.current !== wsClient) return;
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
            if (wsClientRef.current !== wsClient) return;
            errorReported = true;
            console.error('WebSocket error:', error);
            setIsConnected(false);
            isInitializingRef.current = false;
            toast.error(t('pipelines.debugDialog.connectionError'));
          })
          .onClose(() => {
            if (wsClientRef.current !== wsClient) return;
            setIsConnected(false);
            isInitializingRef.current = false;
          })
          .onBroadcast((message) => {
            if (wsClientRef.current !== wsClient) return;
            toast.info(message);
          });

        await wsClient.connect();
      } catch (error) {
        if (!wsClient || wsClientRef.current !== wsClient) return;
        console.error('WebSocket connection failed:', error);
        setIsConnected(false);
        isInitializingRef.current = false;
        if (!errorReported) {
          toast.error(t('pipelines.debugDialog.connectionFailed'));
        }
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
      invalidateHistoryRequests();
      // Disconnect WebSocket immediately when dialog closes
      if (wsClientRef.current) {
        const wsClient = wsClientRef.current;
        wsClientRef.current = null;
        wsClient.disconnect();
        setIsConnected(false);
        isInitializingRef.current = false;
      }
    }

    return () => {
      invalidateHistoryRequests();
      // Disconnect WebSocket on component unmount
      if (wsClientRef.current) {
        const wsClient = wsClientRef.current;
        wsClientRef.current = null;
        wsClient.disconnect();
        isInitializingRef.current = false;
      }
    };
  }, [open, pipelineId, invalidateHistoryRequests]);

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

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
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

    const newImages: Array<{
      file: File;
      preview: string;
      kind: 'image' | 'voice' | 'file';
    }> = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (file.type.startsWith('image/')) {
        newImages.push({
          file,
          preview: URL.createObjectURL(file),
          kind: 'image',
        });
      } else if (file.type.startsWith('audio/')) {
        newImages.push({ file, preview: '', kind: 'voice' });
      } else {
        newImages.push({ file, preview: '', kind: 'file' });
      }
    }

    setSelectedImages((prev) => [...prev, ...newImages]);
    // reset the input so selecting the same file again re-triggers onChange
    e.target.value = '';
  };

  const handleRemoveImage = (index: number) => {
    setSelectedImages((prev) => {
      const newImages = [...prev];
      if (newImages[index].preview) {
        URL.revokeObjectURL(newImages[index].preview);
      }
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
      if (hasUnsavedChanges && beforeSend && !(await beforeSend())) {
        return;
      }

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

      // Upload attachments and add to message chain
      for (const attachment of selectedImages) {
        try {
          if (attachment.kind === 'image') {
            const result = await httpClient.uploadWebSocketImage(
              selectedPipelineId,
              attachment.file,
            );
            messageChain.push({
              type: 'Image',
              path: result.file_key,
            });
          } else {
            // Voice / File go through the generic document upload endpoint,
            // which returns a storage key the backend resolves into the
            // sandbox inbox just like images.
            const result = await httpClient.uploadDocumentFile(attachment.file);
            messageChain.push({
              type: attachment.kind === 'voice' ? 'Voice' : 'File',
              path: result.file_id,
              ...(attachment.kind === 'file'
                ? { name: attachment.file.name }
                : {}),
            });
          }
        } catch (error) {
          console.error('Attachment upload failed:', error);
          toast.error(t('pipelines.debugDialog.imageUploadFailed'));
        }
      }

      // Clear input, images, and quoted message
      setInputValue('');
      setHasAt(false);
      setQuotedMessage(null);
      selectedImages.forEach((img) => {
        if (img.preview) URL.revokeObjectURL(img.preview);
      });
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
        return (
          <AuthenticatedMessageImage
            key={`${index}-${img.path || img.url || 'inline'}`}
            image={img}
            onOpen={(imageUrl) => {
              setPreviewImageUrl(imageUrl);
              setShowImagePreview(true);
            }}
          />
        );
      }

      case 'File': {
        const file = component as FileComponent;
        const downloadHref = file.base64
          ? file.base64.startsWith('data:')
            ? file.base64
            : `data:application/octet-stream;base64,${file.base64}`
          : file.url || '';
        const fileName = file.name || 'Unknown';
        return (
          <div key={index} className="my-2 flex items-center gap-2 text-sm">
            <Paperclip className="size-4" />
            {downloadHref ? (
              <a
                href={downloadHref}
                download={fileName}
                className="text-primary underline hover:opacity-80"
              >
                [{t('pipelines.debugDialog.file')}] {fileName}
              </a>
            ) : (
              <span>
                [{t('pipelines.debugDialog.file')}] {fileName}
              </span>
            )}
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
    <div className="flex flex-1 h-full min-h-0 flex-col">
      <div
        className={cn(
          'flex shrink-0 flex-wrap items-center gap-1 border-b px-4 py-2',
          compact && 'px-3',
        )}
        data-debug-session-toolbar="true"
      >
        <span className="mr-1 text-xs text-muted-foreground">
          {t('pipelines.debugDialog.sessionType')}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-pressed={sessionType === 'person'}
          className={cn(
            'shadow-none',
            sessionType === 'person' &&
              'bg-primary/15 text-primary hover:bg-primary/20 hover:text-primary',
          )}
          onClick={() => setSessionType('person')}
        >
          <User className="size-4" />
          {t('pipelines.debugDialog.privateChat')}
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-pressed={sessionType === 'group'}
          className={cn(
            'shadow-none',
            sessionType === 'group' &&
              'bg-primary/15 text-primary hover:bg-primary/20 hover:text-primary',
          )}
          onClick={() => setSessionType('group')}
        >
          <Users className="size-4" />
          {t('pipelines.debugDialog.groupChat')}
        </Button>
      </div>

      <div className="flex-1 flex flex-col w-full h-full min-h-0">
        <ScrollArea
          ref={scrollAreaRef}
          className={cn(
            'flex-1 overflow-y-auto min-h-0 scroll-area',
            compact ? 'p-3' : 'p-6',
          )}
        >
          <div className={compact ? 'space-y-3' : 'space-y-6'}>
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
                      'rounded-2xl',
                      compact
                        ? 'max-w-[92%] px-3 py-2 text-sm'
                        : 'max-w-3xl px-5 py-3',
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

        {/* Attachment preview area */}
        {selectedImages.length > 0 && (
          <div className="px-4 pb-2">
            <div className="flex gap-2 flex-wrap">
              {selectedImages.map((image, index) => (
                <div key={index} className="relative group">
                  {image.kind === 'image' ? (
                    <img
                      src={image.preview}
                      alt={`preview-${index}`}
                      data-debug-chat-attachment-preview="true"
                      className="w-20 h-20 object-cover rounded-lg border"
                    />
                  ) : (
                    <div className="w-36 h-20 px-2 rounded-lg border bg-muted/40 flex items-center gap-2 overflow-hidden">
                      {image.kind === 'voice' ? (
                        <Music className="size-5 shrink-0 text-muted-foreground" />
                      ) : (
                        <Paperclip className="size-5 shrink-0 text-muted-foreground" />
                      )}
                      <span className="text-xs text-muted-foreground truncate">
                        {image.file.name}
                      </span>
                    </div>
                  )}
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

        <div
          className={cn('shrink-0 border-t p-4', compact && 'p-3')}
          data-debug-composer="true"
        >
          <div className="mb-2 flex items-center gap-2">
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
              accept="image/*,audio/*,*/*"
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
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="ml-auto text-muted-foreground"
              onClick={() => void resetConversation()}
            >
              <RotateCcw className="size-4" />
              {t('pipelines.debugDialog.reset')}
            </Button>
          </div>

          <div className="flex min-w-0 items-end gap-2">
            <div className="min-w-0 flex-1">
              {hasAt && (
                <div className="mb-1">
                  <AtBadge
                    targetName="websocketbot"
                    onRemove={handleAtRemove}
                  />
                </div>
              )}
              <div className="relative">
                <Textarea
                  ref={inputRef}
                  value={inputValue}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyPress}
                  placeholder={t('pipelines.debugDialog.inputPlaceholder', {
                    type:
                      sessionType === 'person'
                        ? t('pipelines.debugDialog.privateChat')
                        : t('pipelines.debugDialog.groupChat'),
                  })}
                  disabled={!isConnected || isUploading}
                  rows={1}
                  className="h-11 min-h-11 max-h-32 resize-y rounded-md px-3 py-2 text-sm transition-none disabled:opacity-50"
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
              className={cn(
                'h-11 shrink-0 rounded-md px-4 text-sm font-medium transition-none shadow-none disabled:opacity-50',
                !compact && 'px-6 text-base',
              )}
            >
              {isUploading ? (
                t('pipelines.debugDialog.uploading')
              ) : (
                <>
                  <Send className="size-4" />
                  {hasUnsavedChanges
                    ? t('pipelines.debugDialog.saveAndSend')
                    : t('pipelines.debugDialog.send')}
                </>
              )}
            </Button>
          </div>
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
