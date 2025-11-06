'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  DndContext,
  type DragEndEvent,
  type DragOverEvent,
  DragOverlay,
  type DragStartEvent,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
  useDroppable,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { backendClient } from '@/app/infra/http';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { SortablePluginItem } from './SortablePluginItem';

interface Plugin {
  plugin_author: string;
  plugin_name: string;
  version: string;
  description: string;
  enabled: boolean;
}

interface PluginItem {
  id: string;
  plugin: Plugin;
}

function DroppableContainer({
  id,
  children,
  isEmpty,
}: {
  id: string;
  children: React.ReactNode;
  isEmpty: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id });

  return (
    <div
      ref={setNodeRef}
      className={`min-h-[400px] space-y-2 rounded-lg transition-colors ${
        isEmpty ? 'border-2 border-dashed border-border p-4' : ''
      } ${isOver && isEmpty ? 'border-primary bg-primary/5' : ''}`}
    >
      {children}
    </div>
  );
}

export default function PipelineExtension({
  pipelineId,
}: {
  pipelineId: string;
}) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedPlugins, setSelectedPlugins] = useState<PluginItem[]>([]);
  const [availablePlugins, setAvailablePlugins] = useState<PluginItem[]>([]);
  const [initialSelectedIds, setInitialSelectedIds] = useState<string[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
  );

  useEffect(() => {
    loadExtensions();
  }, [pipelineId]);

  const loadExtensions = async () => {
    try {
      setLoading(true);
      const data = await backendClient.getPipelineExtensions(pipelineId);

      // Convert plugins to items with unique ids
      const boundPluginIds = new Set(
        data.bound_plugins.map((p) => `${p.author}/${p.name}`),
      );

      const selected: PluginItem[] = [];
      const available: PluginItem[] = [];

      data.available_plugins.forEach((plugin) => {
        const pluginId = `${plugin.plugin_author}/${plugin.plugin_name}`;
        const item = { id: pluginId, plugin };

        if (boundPluginIds.has(pluginId)) {
          selected.push(item);
        } else {
          available.push(item);
        }
      });

      setSelectedPlugins(selected);
      setAvailablePlugins(available);
      setInitialSelectedIds(selected.map((item) => item.id));
    } catch (error) {
      console.error('Failed to load extensions:', error);
      toast.error(t('pipelines.extensions.loadError'));
    } finally {
      setLoading(false);
    }
  };

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event;

    if (!over) return;

    const activeContainer = findContainer(active.id as string);
    const overContainer =
      over.id === 'selected' || over.id === 'available'
        ? over.id
        : findContainer(over.id as string);

    if (
      !activeContainer ||
      !overContainer ||
      activeContainer === overContainer
    ) {
      return;
    }

    // Moving between containers
    setSelectedPlugins((prev) => {
      const activeItems =
        activeContainer === 'selected' ? prev : availablePlugins;
      const overItems = overContainer === 'selected' ? prev : availablePlugins;

      const activeIndex = activeItems.findIndex((item) => item.id === active.id);
      const overIndex =
        over.id === overContainer
          ? overItems.length
          : overItems.findIndex((item) => item.id === over.id);

      const activeItem = activeItems[activeIndex];

      if (activeContainer === 'selected') {
        // Moving from selected to available
        setAvailablePlugins((items) => {
          const newItems = [...items];
          newItems.splice(overIndex >= 0 ? overIndex : items.length, 0, activeItem);
          return newItems;
        });
        return prev.filter((item) => item.id !== active.id);
      } else {
        // Moving from available to selected
        setAvailablePlugins((items) =>
          items.filter((item) => item.id !== active.id),
        );
        const newItems = [...prev];
        newItems.splice(overIndex >= 0 ? overIndex : prev.length, 0, activeItem);
        return newItems;
      }
    });
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    setActiveId(null);

    if (!over) return;

    const activeContainer = findContainer(active.id as string);
    const overContainer =
      over.id === 'selected' || over.id === 'available'
        ? over.id
        : findContainer(over.id as string);

    if (!activeContainer || !overContainer) return;

    // Sorting within the same container
    if (activeContainer === overContainer) {
      const items =
        activeContainer === 'selected' ? selectedPlugins : availablePlugins;
      const activeIndex = items.findIndex((item) => item.id === active.id);
      const overIndex = items.findIndex((item) => item.id === over.id);

      if (activeIndex !== overIndex && overIndex !== -1) {
        const newItems = arrayMove(items, activeIndex, overIndex);
        if (activeContainer === 'selected') {
          setSelectedPlugins(newItems);
        } else {
          setAvailablePlugins(newItems);
        }
      }
    }
  };

  const findContainer = (id: string): 'selected' | 'available' | null => {
    if (selectedPlugins.find((item) => item.id === id)) {
      return 'selected';
    }
    if (availablePlugins.find((item) => item.id === id)) {
      return 'available';
    }
    return null;
  };

  const handleSave = async () => {
    try {
      setSaving(true);

      // Convert selected plugins to the format expected by the API
      const boundPluginsArray = selectedPlugins.map((item) => {
        const [author, name] = item.id.split('/');
        return { author, name };
      });

      await backendClient.updatePipelineExtensions(
        pipelineId,
        boundPluginsArray,
      );
      setInitialSelectedIds(selectedPlugins.map((item) => item.id));
      toast.success(t('pipelines.extensions.saveSuccess'));
    } catch (error) {
      console.error('Failed to save extensions:', error);
      toast.error(t('pipelines.extensions.saveError'));
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    // Reload extensions to reset to saved state
    loadExtensions();
  };

  const hasChanges =
    JSON.stringify(selectedPlugins.map((item) => item.id).sort()) !==
    JSON.stringify(initialSelectedIds.sort());

  const activeItem =
    selectedPlugins.find((item) => item.id === activeId) ||
    availablePlugins.find((item) => item.id === activeId);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4 h-full flex flex-col">
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div className="grid gap-6 md:grid-cols-2 flex-1 overflow-hidden">
          {/* Selected Plugins (Left) */}
          <Card className="flex flex-col">
            <CardHeader>
              <CardTitle className="text-foreground">
                {t('pipelines.extensions.selectedPlugins')} (
                {selectedPlugins.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto">
              <DroppableContainer
                id="selected"
                isEmpty={selectedPlugins.length === 0}
              >
                <SortableContext
                  items={selectedPlugins.map((item) => item.id)}
                  strategy={verticalListSortingStrategy}
                >
                  {selectedPlugins.length === 0 ? (
                    <div className="flex h-[400px] items-center justify-center">
                      <p className="text-sm text-muted-foreground">
                        {t('pipelines.extensions.dragPluginsHere')}
                      </p>
                    </div>
                  ) : (
                    selectedPlugins.map((item) => (
                      <SortablePluginItem
                        key={item.id}
                        id={item.id}
                        plugin={item.plugin}
                      />
                    ))
                  )}
                </SortableContext>
              </DroppableContainer>
            </CardContent>
          </Card>

          {/* Available Plugins (Right) */}
          <Card className="flex flex-col">
            <CardHeader>
              <CardTitle className="text-foreground">
                {t('pipelines.extensions.availablePlugins')} (
                {availablePlugins.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto">
              <DroppableContainer
                id="available"
                isEmpty={availablePlugins.length === 0}
              >
                <SortableContext
                  items={availablePlugins.map((item) => item.id)}
                  strategy={verticalListSortingStrategy}
                >
                  {availablePlugins.length === 0 ? (
                    <div className="flex h-[400px] items-center justify-center">
                      <p className="text-sm text-muted-foreground">
                        {t('pipelines.extensions.allPluginsSelected')}
                      </p>
                    </div>
                  ) : (
                    availablePlugins.map((item) => (
                      <SortablePluginItem
                        key={item.id}
                        id={item.id}
                        plugin={item.plugin}
                      />
                    ))
                  )}
                </SortableContext>
              </DroppableContainer>
            </CardContent>
          </Card>
        </div>

        <DragOverlay>
          {activeItem ? (
            <div className="cursor-grabbing">
              <Card className="shadow-lg border-primary">
                <CardHeader className="pb-3">
                  <div className="flex items-start gap-3">
                    <div className="flex-1">
                      <CardTitle className="text-base">
                        {activeItem.plugin.plugin_name}
                      </CardTitle>
                      <p className="text-sm text-muted-foreground">
                        {activeItem.plugin.plugin_author} • v
                        {activeItem.plugin.version}
                      </p>
                    </div>
                  </div>
                </CardHeader>
              </Card>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {hasChanges && (
        <div className="flex justify-end gap-2 pt-4 border-t">
          <Button
            type="button"
            variant="outline"
            onClick={handleCancel}
            disabled={saving}
          >
            {t('common.cancel')}
          </Button>
          <Button type="button" onClick={handleSave} disabled={saving}>
            {saving ? t('common.saving') : t('common.save')}
          </Button>
        </div>
      )}
    </div>
  );
}
