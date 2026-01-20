'use client';

import React, { useState } from 'react';
import {
  MessageChainComponent,
  Image as ImageComponent,
  Plain,
  At,
  Voice,
  Quote,
} from '@/app/infra/entities/message';
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
          <span
            key={index}
            className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-sm"
          >
            @{displayName}
          </span>
        );
      }

      case 'AtAll':
        return (
          <span
            key={index}
            className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-sm"
          >
            @All
          </span>
        );

      case 'Image': {
        const img = component as ImageComponent;
        const imageUrl = img.url || (img.base64 ? img.base64 : '');

        if (!imageUrl) {
          return (
            <span
              key={index}
              className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-sm"
            >
              [Image]
            </span>
          );
        }

        return (
          <span key={index} className="inline-block align-middle mx-1">
            <img
              src={imageUrl}
              alt="Image"
              className="w-20 h-20 object-cover rounded cursor-pointer hover:opacity-80 transition-opacity border border-gray-200 dark:border-gray-700"
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
          <span
            key={index}
            className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-sm"
          >
            <svg
              className="w-3.5 h-3.5 mr-1"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path d="M8 4a3 3 0 00-3 3v4a5 5 0 0010 0V7a1 1 0 112 0v4a7 7 0 11-14 0V7a5 5 0 0110 0v4a3 3 0 11-6 0V7a1 1 0 012 0v4a1 1 0 102 0V7a3 3 0 00-3-3z" />
            </svg>
            {file.name || 'File'}
          </span>
        );
      }

      case 'Voice': {
        const voice = component as Voice;
        return (
          <span
            key={index}
            className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-sm"
          >
            <svg
              className="w-3.5 h-3.5 mr-1"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z" />
            </svg>
            Voice{voice.length ? ` ${voice.length}s` : ''}
          </span>
        );
      }

      case 'Quote': {
        const quote = component as Quote;
        return (
          <span
            key={index}
            className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-sm border-l-2 border-gray-400"
          >
            {quote.origin
              ?.filter((c) => (c as MessageChainComponent).type === 'Plain')
              .map((c) => (c as MessageChainComponent as Plain).text)
              .join('') || '[Quote]'}
          </span>
        );
      }

      case 'Source':
        return null;

      default:
        return (
          <span
            key={index}
            className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-sm"
          >
            [{component.type}]
          </span>
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
        <span className="text-gray-400 dark:text-gray-500 italic">
          [Empty message]
        </span>
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
  if (!content || content.trim() === '' || content === '[]' || content === '""') {
    return (
      <span className="text-gray-400 dark:text-gray-500 italic">
        [Empty message]
      </span>
    );
  }

  // Render as plain text
  return <span className={lineClampClass}>{content}</span>;
}
