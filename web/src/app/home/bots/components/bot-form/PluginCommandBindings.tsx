import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  GripVertical,
  Plus,
  Trash2,
  Terminal,
  AlertCircle,
  X,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  DndContext,
  closestCenter,
  PointerSensor,
  KeyboardSensor,
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
import { httpClient } from '@/app/infra/http/HttpClient';
import { extractI18nObject } from '@/i18n/I18nProvider';
import type { Plugin, PluginComponent } from '@/app/infra/entities/plugin';
import type {
  BotCommandSettings,
  BotCommandPluginBinding,
} from '@/app/infra/entities/api';
import { AuthenticatedPluginIcon } from '@/components/AuthenticatedPluginIcon';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface PluginCommandBindingsProps {
  value?: BotCommandSettings;
  onChange: (value: BotCommandSettings) => void;
}

function getPluginId(plugin: Plugin): string {
  const meta = plugin.manifest?.manifest?.metadata;
  if (!meta) return '';
  return meta.author ? `${meta.author}/${meta.name}` : meta.name;
}

function getPluginCommands(plugin: Plugin): PluginComponent[] {
  return (
    plugin.components?.filter(
      (comp) => comp.manifest?.manifest?.kind === 'Command',
    ) || []
  );
}

interface SortablePluginItemProps {
  binding: BotCommandPluginBinding;
  plugin?: Plugin;
  prefixes: string[];
  overriddenCommands: Map<string, string>;
  onToggleEnabled: (pluginId: string, enabled: boolean) => void;
  onRemove: (pluginId: string) => void;
}

function SortablePluginItem({
  binding,
  plugin,
  prefixes,
  overriddenCommands,
  onToggleEnabled,
  onRemove,
}: SortablePluginItemProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(true);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: binding.plugin_id });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  const meta = plugin?.manifest?.manifest?.metadata;
  const label = meta
    ? extractI18nObject(meta.label) || meta.name
    : binding.plugin_id;
  const description = meta?.description
    ? extractI18nObject(meta.description)
    : '';
  const commands = plugin ? getPluginCommands(plugin) : [];
  const primaryPrefix = prefixes[0] || '/';

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="rounded-lg border bg-card text-card-foreground shadow-sm transition-all"
    >
      <div className="flex items-center justify-between p-3.5">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            className="cursor-grab touch-none p-1 text-muted-foreground hover:text-foreground active:cursor-grabbing"
            {...attributes}
            {...listeners}
            title={t('bots.pluginCommands.dragHint')}
            aria-label={t('bots.pluginCommands.dragHint')}
          >
            <GripVertical className="size-4" />
          </button>

          {plugin && meta && (
            <div className="size-8 shrink-0 overflow-hidden rounded">
              <AuthenticatedPluginIcon
                author={meta.author || ''}
                name={meta.name || ''}
                className="size-8"
              />
            </div>
          )}

          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm truncate">{label}</span>
              <span className="text-xs text-muted-foreground font-mono">
                {binding.plugin_id}
              </span>
              <Badge variant="secondary" className="text-xs font-normal">
                {t('bots.pluginCommands.commandsCount', {
                  count: commands.length,
                })}
              </Badge>
            </div>
            {description && (
              <p className="text-xs text-muted-foreground truncate max-w-md">
                {description}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setExpanded((prev) => !prev)}
            className="h-8 px-2 text-xs text-muted-foreground"
          >
            {expanded ? (
              <ChevronDown className="size-4" />
            ) : (
              <ChevronRight className="size-4" />
            )}
          </Button>

          <Switch
            checked={binding.enabled}
            onCheckedChange={(checked) =>
              onToggleEnabled(binding.plugin_id, checked)
            }
          />

          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => onRemove(binding.plugin_id)}
            className="size-8 text-muted-foreground hover:text-destructive"
            title={t('bots.pluginCommands.remove')}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      </div>

      {expanded && (
        <div className="border-t bg-muted/30 p-3 rounded-b-lg">
          {commands.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              {t('bots.pluginCommands.noCommands')}
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {commands.map((cmd) => {
                const cmdMeta = cmd.manifest?.manifest?.metadata;
                const cmdName = cmdMeta?.name || '';
                const cmdLabel = cmdMeta
                  ? extractI18nObject(cmdMeta.label) || cmdName
                  : cmdName;
                const cmdDesc = cmdMeta?.description
                  ? extractI18nObject(cmdMeta.description)
                  : '';
                const conflictWith = overriddenCommands.get(
                  `${binding.plugin_id}:${cmdName}`,
                );

                return (
                  <div
                    key={cmdName}
                    className="flex items-center justify-between gap-3 text-xs py-1 px-2 rounded bg-background/60"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <Terminal className="size-3.5 text-muted-foreground shrink-0" />
                      <span className="font-mono font-medium text-foreground">
                        {primaryPrefix}
                        {cmdName}
                      </span>
                      {cmdLabel !== cmdName && (
                        <span className="text-muted-foreground">
                          ({cmdLabel})
                        </span>
                      )}
                      {cmdDesc && (
                        <span className="text-muted-foreground truncate max-w-sm">
                          - {cmdDesc}
                        </span>
                      )}
                    </div>

                    {conflictWith && (
                      <Badge
                        variant="outline"
                        className="border-amber-400 text-amber-700 dark:text-amber-400 text-xs gap-1 shrink-0 bg-amber-50 dark:bg-amber-950/30"
                      >
                        <AlertCircle className="size-3" />
                        {t('bots.pluginCommands.overriddenBy', {
                          plugin: conflictWith,
                        })}
                      </Badge>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function PluginCommandBindings({
  value = { enabled: true, prefixes: ['/'], plugins: [] },
  onChange,
}: PluginCommandBindingsProps) {
  const { t } = useTranslation();
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedPlugins, setSelectedPlugins] = useState<string[]>([]);
  const [newPrefix, setNewPrefix] = useState('');

  const prefixes = useMemo(
    () =>
      value.prefixes && value.prefixes.length > 0 ? value.prefixes : ['/'],
    [value.prefixes],
  );
  const pluginBindings = useMemo(() => value.plugins || [], [value.plugins]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    httpClient
      .getPlugins()
      .then((res) => {
        if (mounted) {
          setPlugins(res.plugins || []);
        }
      })
      .catch((err) => {
        console.error('Failed to load plugins:', err);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const installedPluginsWithCommands = useMemo(() => {
    return plugins.filter((p) => getPluginCommands(p).length > 0);
  }, [plugins]);

  const pluginMap = useMemo(() => {
    const map = new Map<string, Plugin>();
    for (const p of plugins) {
      map.set(getPluginId(p), p);
    }
    return map;
  }, [plugins]);

  const availablePlugins = useMemo(() => {
    const boundIds = new Set(pluginBindings.map((b) => b.plugin_id));
    return installedPluginsWithCommands.filter(
      (p) => !boundIds.has(getPluginId(p)),
    );
  }, [installedPluginsWithCommands, pluginBindings]);

  // Compute command collision/overrides based on priority order
  const overriddenCommands = useMemo(() => {
    const commandOwnerMap = new Map<string, string>();
    const overrides = new Map<string, string>();

    for (const binding of pluginBindings) {
      if (!binding.enabled) continue;
      const plugin = pluginMap.get(binding.plugin_id);
      if (!plugin) continue;
      const meta = plugin.manifest?.manifest?.metadata;
      const label = meta
        ? extractI18nObject(meta.label) || meta.name
        : binding.plugin_id;
      const cmds = getPluginCommands(plugin);
      for (const cmd of cmds) {
        const cmdName = cmd.manifest?.manifest?.metadata?.name;
        if (!cmdName) continue;
        if (commandOwnerMap.has(cmdName)) {
          overrides.set(
            `${binding.plugin_id}:${cmdName}`,
            commandOwnerMap.get(cmdName)!,
          );
        } else {
          commandOwnerMap.set(cmdName, label);
        }
      }
    }
    return overrides;
  }, [pluginBindings, pluginMap]);

  function handleToggleMainEnabled(enabled: boolean) {
    onChange({
      ...value,
      enabled,
      prefixes,
      plugins: pluginBindings,
    });
  }

  function handleAddPrefix() {
    const trimmed = newPrefix.trim();
    if (!trimmed || /\s/.test(trimmed)) {
      toast.error(t('bots.pluginCommands.prefixInvalid'));
      return;
    }
    if (prefixes.includes(trimmed)) {
      toast.error(t('bots.pluginCommands.prefixDuplicate'));
      return;
    }
    onChange({
      ...value,
      prefixes: [...prefixes, trimmed],
    });
    setNewPrefix('');
  }

  function handleRemovePrefix(prefixToRemove: string) {
    if (prefixes.length <= 1) {
      toast.error(t('bots.pluginCommands.prefixInvalid'));
      return;
    }
    onChange({
      ...value,
      prefixes: prefixes.filter((p) => p !== prefixToRemove),
    });
  }

  function handleTogglePluginEnabled(pluginId: string, enabled: boolean) {
    onChange({
      ...value,
      plugins: pluginBindings.map((p) =>
        p.plugin_id === pluginId ? { ...p, enabled } : p,
      ),
    });
  }

  function handleRemovePlugin(pluginId: string) {
    onChange({
      ...value,
      plugins: pluginBindings.filter((p) => p.plugin_id !== pluginId),
    });
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = pluginBindings.findIndex(
        (p) => p.plugin_id === active.id,
      );
      const newIndex = pluginBindings.findIndex((p) => p.plugin_id === over.id);
      if (oldIndex !== -1 && newIndex !== -1) {
        onChange({
          ...value,
          plugins: arrayMove(pluginBindings, oldIndex, newIndex),
        });
      }
    }
  }

  function openAddDialog() {
    setSelectedPlugins([]);
    setDialogOpen(true);
  }

  function handleConfirmAddPlugins() {
    if (selectedPlugins.length === 0) return;
    const newBindings: BotCommandPluginBinding[] = [
      ...pluginBindings,
      ...selectedPlugins.map((plugin_id) => ({
        plugin_id,
        enabled: true,
      })),
    ];
    onChange({
      ...value,
      plugins: newBindings,
    });
    setDialogOpen(false);
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-4">
        <div className="space-y-1 pr-4">
          <CardTitle className="text-base font-semibold">
            {t('bots.pluginCommands.title')}
          </CardTitle>
          <CardDescription className="text-xs">
            {t('bots.pluginCommands.description')}
          </CardDescription>
        </div>
        <Switch
          checked={value.enabled}
          onCheckedChange={handleToggleMainEnabled}
        />
      </CardHeader>

      {value.enabled && (
        <CardContent className="space-y-5">
          {/* Prefix configuration */}
          <div className="space-y-2">
            <Label className="text-xs font-medium">
              {t('bots.pluginCommands.prefixes')}
            </Label>
            <div className="flex flex-wrap items-center gap-2">
              {prefixes.map((p) => (
                <Badge
                  key={p}
                  variant="secondary"
                  className="font-mono text-sm py-1 px-2.5 flex items-center gap-1.5"
                >
                  {p}
                  {prefixes.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemovePrefix(p)}
                      className="text-muted-foreground hover:text-foreground rounded-full p-0.5"
                      title={t('common.remove')}
                    >
                      <X className="size-3" />
                    </button>
                  )}
                </Badge>
              ))}

              <div className="flex items-center gap-1.5">
                <Input
                  value={newPrefix}
                  onChange={(e) => setNewPrefix(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddPrefix();
                    }
                  }}
                  placeholder={t('bots.pluginCommands.prefixPlaceholder')}
                  className="h-8 w-60 text-xs font-mono"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAddPrefix}
                  className="h-8 px-2.5 text-xs"
                >
                  <Plus className="size-3.5 mr-1" />
                  {t('bots.pluginCommands.addPrefix')}
                </Button>
              </div>
            </div>
          </div>

          {/* Plugin list and drag reordering */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-xs font-medium">
                  {t('bots.pluginCommands.plugins')}
                </Label>
                {pluginBindings.length > 1 && (
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {t('bots.pluginCommands.dragHint')}
                  </p>
                )}
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={openAddDialog}
                disabled={loading || availablePlugins.length === 0}
                className="h-8 text-xs"
              >
                <Plus className="size-3.5 mr-1" />
                {t('bots.pluginCommands.addPlugin')}
              </Button>
            </div>

            {pluginBindings.length === 0 ? (
              <div className="rounded-lg border border-dashed p-6 text-center text-xs text-muted-foreground">
                {t('bots.pluginCommands.empty')}
              </div>
            ) : (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
              >
                <SortableContext
                  items={pluginBindings.map((p) => p.plugin_id)}
                  strategy={verticalListSortingStrategy}
                >
                  <div className="space-y-2">
                    {pluginBindings.map((binding) => (
                      <SortablePluginItem
                        key={binding.plugin_id}
                        binding={binding}
                        plugin={pluginMap.get(binding.plugin_id)}
                        prefixes={prefixes}
                        overriddenCommands={overriddenCommands}
                        onToggleEnabled={handleTogglePluginEnabled}
                        onRemove={handleRemovePlugin}
                      />
                    ))}
                  </div>
                </SortableContext>
              </DndContext>
            )}
          </div>
        </CardContent>
      )}

      {/* Dialog for adding plugin commands */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base">
              {t('bots.pluginCommands.selectPlugins')}
            </DialogTitle>
            <DialogDescription className="text-xs">
              {t('bots.pluginCommands.description')}
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-72 overflow-y-auto space-y-2 py-2">
            {availablePlugins.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">
                {t('bots.pluginCommands.noAvailablePlugins')}
              </p>
            ) : (
              availablePlugins.map((plugin) => {
                const pluginId = getPluginId(plugin);
                const meta = plugin.manifest?.manifest?.metadata;
                const label = meta
                  ? extractI18nObject(meta.label) || meta.name
                  : pluginId;
                const commands = getPluginCommands(plugin);
                const isChecked = selectedPlugins.includes(pluginId);

                return (
                  <label
                    key={pluginId}
                    className="flex items-center justify-between p-2.5 rounded-lg border hover:bg-muted/50 cursor-pointer transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <Checkbox
                        checked={isChecked}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            setSelectedPlugins((prev) => [...prev, pluginId]);
                          } else {
                            setSelectedPlugins((prev) =>
                              prev.filter((id) => id !== pluginId),
                            );
                          }
                        }}
                      />
                      <div className="size-7 shrink-0 overflow-hidden rounded">
                        <AuthenticatedPluginIcon
                          author={meta?.author || ''}
                          name={meta?.name || ''}
                          className="size-7"
                        />
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium text-xs truncate">
                          {label}
                        </div>
                        <div className="text-[11px] text-muted-foreground font-mono truncate">
                          {pluginId}
                        </div>
                      </div>
                    </div>

                    <Badge
                      variant="secondary"
                      className="text-xs shrink-0 font-normal"
                    >
                      {t('bots.pluginCommands.commandsCount', {
                        count: commands.length,
                      })}
                    </Badge>
                  </label>
                );
              })
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setDialogOpen(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={selectedPlugins.length === 0}
              onClick={handleConfirmAddPlugins}
            >
              {t('common.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
