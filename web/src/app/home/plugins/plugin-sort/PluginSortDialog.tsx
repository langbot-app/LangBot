'use client';

import * as React from 'react';
import { useState, useEffect } from 'react';
import { PluginCardVO } from '@/app/home/plugins/plugin-installed/PluginCardVO';
import { httpClient } from '@/app/infra/http/HttpClient';
import { PluginReorderElement } from '@/app/infra/entities/api';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useTranslation } from 'react-i18next';
import { i18nObj } from '@/i18n/I18nProvider';

interface PluginSortDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSortComplete: () => void;
}

function SortablePluginItem({ plugin }: { plugin: PluginCardVO }) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({
      id: `${plugin.author}-${plugin.name}`,
    });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="bg-white dark:bg-gray-800 p-4 rounded-md shadow-sm border mb-2 cursor-move"
    >
      <div className="flex flex-col">
        <div className="text-sm text-gray-600 dark:text-gray-400">
          {plugin.author}
        </div>
        <div className="text-lg font-medium">{plugin.name}</div>
        <div className="text-sm line-clamp-2 text-gray-500 dark:text-gray-400 mt-1">
          {plugin.description}
        </div>
      </div>
    </div>
  );
}

export default function PluginSortDialog({
  open,
  onOpenChange,
  onSortComplete,
}: PluginSortDialogProps) {
  const { t } = useTranslation();
  const [sortedPlugins, setSortedPlugins] = useState<PluginCardVO[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  function getPluginList() {
    httpClient.getPlugins().then((value) => {
      setSortedPlugins(
        value.plugins.map((plugin) => {
          return new PluginCardVO({
            author: plugin.author,
            description: i18nObj(plugin.description),
            enabled: plugin.enabled,
            name: plugin.name,
            version: plugin.version,
            status: plugin.status,
            tools: plugin.tools,
            event_handlers: plugin.event_handlers,
            repository: plugin.repository,
            priority: plugin.priority,
          });
        }),
      );
    });
  }

  useEffect(() => {
    if (open) {
      getPluginList();
    }
  }, [open]);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    console.log('Drag end event:', { active, over });

    if (over && active.id !== over.id) {
      setSortedPlugins((items) => {
        const oldIndex = items.findIndex(
          (item) => `${item.author}-${item.name}` === active.id,
        );
        const newIndex = items.findIndex(
          (item) => `${item.author}-${item.name}` === over.id,
        );

        const newItems = arrayMove(items, oldIndex, newIndex);

        return newItems;
      });
    }
  }

  function handleSave() {
    setIsLoading(true);

    const reorderElements: PluginReorderElement[] = sortedPlugins.map(
      (plugin, index) => ({
        author: plugin.author,
        name: plugin.name,
        priority: index,
      }),
    );

    httpClient
      .reorderPlugins(reorderElements)
      .then(() => {
        toast.success(t('plugins.pluginSortSuccess'));
        onSortComplete();
        onOpenChange(false);
      })
      .catch((err) => {
        toast.error(t('plugins.pluginSortError') + err.message);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[700px] max-h-[80vh] p-0 flex flex-col">
        <DialogHeader className="px-6 pt-6 pb-0">
          <DialogTitle>{t('plugins.pluginSort')}</DialogTitle>
        </DialogHeader>
        <div className="flex-1 overflow-y-auto px-6 py-0">
          <p className="text-sm text-gray-500 mb-4">
            {t('plugins.pluginSortDescription')}
          </p>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={sortedPlugins.map(
                (plugin) => `${plugin.author}-${plugin.name}`,
              )}
              strategy={verticalListSortingStrategy}
            >
              {sortedPlugins.map((plugin) => (
                <SortablePluginItem
                  key={`${plugin.author}-${plugin.name}`}
                  plugin={plugin}
                />
              ))}
            </SortableContext>
          </DndContext>
        </div>
        <DialogFooter className="px-6 py-4">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isLoading}
          >
            {t('common.cancel')}
          </Button>
          <Button onClick={handleSave} disabled={isLoading}>
            {isLoading ? t('common.saving') : t('common.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
