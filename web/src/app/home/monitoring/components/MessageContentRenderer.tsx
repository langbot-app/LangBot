import React, { useState } from 'react';
import { Paperclip, AudioLines } from 'lucide-react';
import {
  MessageChainComponent,
  Image as ImageComponent,
  Plain,
  At,
  Voice,
  Quote,
} from '@/app/infra/entities/message';
import { Badge } from '@/components/ui/badge';
import ImagePreviewDialog from '@/app/home/pipelines/components/debug-dialog/ImagePreviewDialog';

interface MessageContentRendererProps {
  content: string;
  maxLines?: number;
}

export function MessageContentRenderer({
  content,
  maxLines = 3,
}: MessageContentRendererProps) {
  const [previewImageUrl, setPreviewImageUrl] = useState<string>('');
  const [showImagePreview, setShowImagePreview] = useState(false);

  // Try to parse content as message_chain JSON
  const parseContent = (content: string): MessageChainComponent[] | null => {
    try {
      const parsed = JSON.parse(content);
      if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].type) {
        return parsed as MessageChainComponent[];
      }
      return null;
    } catch {
      return null;
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
        const displayName =
          atComponent.display || atComponent.target?.toString() || '';
        return (
          <Badge
            key={index}
            className="mx-0.5 px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-sm"
          >
            @{displayName}
          </Badge>
        );
      }

      case 'AtAll':
        return (
          <Badge
            key={index}
            className="mx-0.5 px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-sm"
          >
            @All
          </Badge>
        );

      case 'Image': {
        const img = component as ImageComponent;
        const imageUrl = img.url || (img.base64 ? img.base64 : '');

        if (!imageUrl) {
          return (
            <Badge
              key={index}
              className="mx-0.5 px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-sm"
            >
              [Image]
            </Badge>
          );
        }

        return (
          <span key={index} className="inline-block align-middle mx-1">
            <img
              src={imageUrl}
              alt="Message attachment"
              className="w-20 h-20 object-cover rounded cursor-pointer hover:opacity-80 transition-opacity border"
              onClick={(e) => {
                e.stopPropagation();
                setPreviewImageUrl(imageUrl);
                setShowImagePreview(true);
              }}
            />
          </span>
        );
      }

      case 'File': {
        const file = component as MessageChainComponent & { name?: string };
        return (
          <Badge
            key={index}
            className="mx-0.5 px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-sm [&>svg]:size-3.5"
          >
            <Paperclip className="mr-1" />
            {file.name || 'File'}
          </Badge>
        );
      }

      case 'Voice': {
        const voice = component as Voice;
        return (
          <Badge
            key={index}
            className="mx-0.5 px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-sm [&>svg]:size-3.5"
          >
            <AudioLines className="mr-1" />
            Voice{voice.length ? ` ${voice.length}s` : ''}
          </Badge>
        );
      }

      case 'Quote': {
        const quote = component as Quote;
        return (
          <Badge
            key={index}
            className="mx-0.5 px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-sm border-l-2 border-l-muted-foreground/50"
          >
            {quote.origin
              ?.filter((c) => (c as MessageChainComponent).type === 'Plain')
              .map((c) => (c as MessageChainComponent as Plain).text)
              .join('') || '[Quote]'}
          </Badge>
        );
      }

      case 'Source':
        return null;

      default:
        return (
          <Badge
            key={index}
            className="mx-0.5 px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-sm"
          >
            [{component.type}]
          </Badge>
        );
    }
  };

  const messageChain = parseContent(content);

  // Determine line clamp class
  const lineClampClass =
    maxLines === 2
      ? 'line-clamp-2'
      : maxLines === 3
        ? 'line-clamp-3'
        : maxLines === 4
          ? 'line-clamp-4'
          : '';

  if (messageChain) {
    // Filter out Source components as they render to null
    const visibleComponents = messageChain.filter(
      (component) => component.type !== 'Source',
    );

    // If no visible components, show placeholder
    if (visibleComponents.length === 0) {
      return (
        <span className="text-muted-foreground italic">[Empty message]</span>
      );
    }

    // Render as message chain
    return (
      <>
        <div className={`${lineClampClass}`}>
          {messageChain.map((component, index) =>
            renderMessageComponent(component, index),
          )}
        </div>
        <ImagePreviewDialog
          open={showImagePreview}
          imageUrl={previewImageUrl}
          onClose={() => setShowImagePreview(false)}
        />
      </>
    );
  }

  // Handle empty plain text
  if (
    !content ||
    content.trim() === '' ||
    content === '[]' ||
    content === '""'
  ) {
    return (
      <span className="text-muted-foreground italic">[Empty message]</span>
    );
  }

  // Render as plain text
  return <span className={lineClampClass}>{content}</span>;
}
