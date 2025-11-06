'use client';

import type React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

interface Plugin {
  plugin_author: string;
  plugin_name: string;
  version: string;
  description: string;
  enabled: boolean;
}

interface SortablePluginItemProps {
  id: string;
  plugin: Plugin;
}

export function SortablePluginItem({ id, plugin }: SortablePluginItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'group transition-opacity',
        isDragging && 'opacity-50',
      )}
    >
      <Card className="hover:border-primary/50 transition-colors">
        <CardHeader className="pb-3">
          <div className="flex items-start gap-3">
            <button
              className="cursor-grab touch-none text-muted-foreground transition-colors hover:text-foreground active:cursor-grabbing mt-1"
              {...attributes}
              {...listeners}
            >
              <GripVertical className="h-5 w-5" />
            </button>
            <div className="flex-1">
              <CardTitle className="text-base">
                {plugin.plugin_name}
              </CardTitle>
              <CardDescription className="text-sm">
                {plugin.plugin_author} • v{plugin.version}
              </CardDescription>
            </div>
            {!plugin.enabled && (
              <span className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded">
                Disabled
              </span>
            )}
          </div>
        </CardHeader>
        {plugin.description && (
          <CardContent className="pt-0">
            <p className="text-sm text-muted-foreground">
              {plugin.description}
            </p>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
