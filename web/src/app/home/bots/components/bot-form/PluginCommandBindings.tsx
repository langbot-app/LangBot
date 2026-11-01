import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import {
  GripVertical,
  Plus,
  Settings2,
  Trash2,
  AlertCircle,
  X,
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
import type {
  Agent,
  BotCommandSettings,
  BotCommandProcessorBinding,
  CommandProcessorDescriptor,
  PlatformCommandCapability,
} from '@/app/infra/entities/api';
import PlatformCommandRegistration from './PlatformCommandRegistration';
import { AuthenticatedPluginIcon } from '@/components/AuthenticatedPluginIcon';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Switch } from '@/components/ui/switch';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
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
  agents: Agent[];
  onCreated: (agent: Agent) => void;
  registrationCapability?: PlatformCommandCapability;
  botId?: string;
  dirty?: boolean;
}

const PLUGIN_REF_PREFIX = 'plugin:';

export function commandProcessorPluginId(agent?: Agent): string {
  const ref = agent?.component_ref ?? '';
  return ref.startsWith(PLUGIN_REF_PREFIX)
    ? ref.slice(PLUGIN_REF_PREFIX.length)
    : '';
}

function splitPluginId(pluginId: string): { author: string; name: string } {
  const [author = '', name = ''] = pluginId.split('/');
  return { author, name };
}

interface SortableProcessorItemProps {
  binding: BotCommandProcessorBinding;
  agent?: Agent;
  component?: CommandProcessorDescriptor;
  prefixes: string[];
  overriddenCommands: Map<string, string>;
  onToggleEnabled: (processorUuid: string, enabled: boolean) => void;
  onRemove: (processorUuid: string) => void;
}

function SortableProcessorItem({
  binding,
  agent,
  component,
  prefixes,
  overriddenCommands,
  onToggleEnabled,
  onRemove,
}: SortableProcessorItemProps) {
  const { t } = useTranslation();

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: binding.processor_uuid });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  const pluginId = commandProcessorPluginId(agent);
  const { author, name } = splitPluginId(pluginId);
  const commands = component?.commands ?? [];
  const primaryPrefix = prefixes[0] || '/';

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-start gap-2.5 rounded-lg border p-2.5 ${
        binding.enabled ? 'bg-card' : 'border-dashed bg-muted/30'
      }`}
    >
      <button
        type="button"
        className="mt-1.5 cursor-grab touch-none text-muted-foreground hover:text-foreground active:cursor-grabbing"
        {...attributes}
        {...listeners}
        title={t('bots.pluginCommands.dragHint')}
        aria-label={t('bots.pluginCommands.dragHint')}
      >
        <GripVertical className="size-4" />
      </button>

      {pluginId && (
        <div className="mt-0.5 size-7 shrink-0 overflow-hidden rounded">
          <AuthenticatedPluginIcon
            author={author}
            name={name}
            className="size-7"
          />
        </div>
      )}

      <div className="min-w-0 flex-1 space-y-1.5">
        <Link
          to={`/home/agents?id=${encodeURIComponent(binding.processor_uuid)}`}
          className="block truncate text-sm font-medium hover:underline"
          title={pluginId || undefined}
        >
          {agent
            ? `${agent.emoji || '⌨️'} ${agent.name}`
            : t('bots.pluginCommands.missingProcessor')}
        </Link>
        {commands.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            {t('bots.pluginCommands.noCommands')}
          </p>
        ) : (
          <div className="flex flex-wrap gap-1">
            {commands.map((cmd) => {
              const cmdLabel =
                extractI18nObject({
                  en_US: cmd.name,
                  zh_Hans: cmd.name,
                  ...cmd.label,
                }) || cmd.name;
              const cmdDesc = cmd.description
                ? extractI18nObject({
                    en_US: '',
                    zh_Hans: '',
                    ...cmd.description,
                  })
                : '';
              const conflictWith = overriddenCommands.get(
                `${binding.processor_uuid}:${cmd.name}`,
              );
              const hint = [
                cmdLabel !== cmd.name ? cmdLabel : '',
                cmdDesc,
                conflictWith
                  ? t('bots.pluginCommands.overriddenBy', {
                      plugin: conflictWith,
                    })
                  : '',
              ]
                .filter(Boolean)
                .join(' · ');
              const chip = (
                <span
                  className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-xs ${
                    conflictWith
                      ? 'bg-amber-50 text-amber-700 line-through dark:bg-amber-950/30 dark:text-amber-400'
                      : 'bg-muted text-foreground'
                  }`}
                >
                  {conflictWith && (
                    <AlertCircle className="size-3 no-underline" />
                  )}
                  {primaryPrefix}
                  {cmd.name}
                </span>
              );
              return hint ? (
                <Tooltip key={cmd.name}>
                  <TooltipTrigger asChild>{chip}</TooltipTrigger>
                  <TooltipContent className="max-w-xs">{hint}</TooltipContent>
                </Tooltip>
              ) : (
                <React.Fragment key={cmd.name}>{chip}</React.Fragment>
              );
            })}
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <Switch
          checked={binding.enabled}
          onCheckedChange={(checked) =>
            onToggleEnabled(binding.processor_uuid, checked)
          }
          aria-label={agent?.name ?? binding.processor_uuid}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => onRemove(binding.processor_uuid)}
          className="size-8 text-muted-foreground hover:text-destructive"
          title={t('bots.pluginCommands.remove')}
          aria-label={t('bots.pluginCommands.remove')}
        >
          <Trash2 className="size-4" />
        </Button>
      </div>
    </div>
  );
}

export default function PluginCommandBindings({
  value = { enabled: true, prefixes: ['/'], processors: [] },
  onChange,
  agents,
  onCreated,
  registrationCapability,
  botId,
  dirty,
}: PluginCommandBindingsProps) {
  const { t } = useTranslation();
  const [components, setComponents] = useState<CommandProcessorDescriptor[]>(
    [],
  );
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [creating, setCreating] = useState<string | null>(null);
  const [newPrefix, setNewPrefix] = useState('');
  const creatingRef = useRef(false);

  const prefixes = useMemo(
    () =>
      value.prefixes && value.prefixes.length > 0 ? value.prefixes : ['/'],
    [value.prefixes],
  );
  const bindings = useMemo(() => value.processors || [], [value.processors]);

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
      .getAgentMetadata()
      .then((metadata) => {
        if (mounted) setComponents(metadata.command_processors ?? []);
      })
      .catch((err) => {
        console.error('Failed to load command processor metadata:', err);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const processors = useMemo(
    () => agents.filter((agent) => agent.kind === 'command_processor'),
    [agents],
  );
  const agentMap = useMemo(
    () => new Map(processors.map((agent) => [agent.uuid ?? '', agent])),
    [processors],
  );
  const componentMap = useMemo(
    () => new Map(components.map((item) => [item.plugin_id, item])),
    [components],
  );

  // One instance per plugin per bot: the backend rejects a second one because it could never match.
  const boundPlugins = useMemo(
    () =>
      new Set(
        bindings.map((binding) =>
          commandProcessorPluginId(agentMap.get(binding.processor_uuid)),
        ),
      ),
    [bindings, agentMap],
  );
  const availableProcessors = useMemo(
    () =>
      processors.filter(
        (agent) =>
          !bindings.some((binding) => binding.processor_uuid === agent.uuid) &&
          !boundPlugins.has(commandProcessorPluginId(agent)),
      ),
    [processors, bindings, boundPlugins],
  );
  const pluginsWithoutInstance = useMemo(
    () =>
      components.filter(
        (component) =>
          !boundPlugins.has(component.plugin_id) &&
          !processors.some(
            (agent) => commandProcessorPluginId(agent) === component.plugin_id,
          ),
      ),
    [components, boundPlugins, processors],
  );

  // Compute command collision/overrides based on priority order
  const overriddenCommands = useMemo(() => {
    const commandOwnerMap = new Map<string, string>();
    const overrides = new Map<string, string>();

    for (const binding of bindings) {
      if (!binding.enabled) continue;
      const agent = agentMap.get(binding.processor_uuid);
      const component = componentMap.get(commandProcessorPluginId(agent));
      if (!agent || !component) continue;
      for (const cmd of component.commands) {
        if (commandOwnerMap.has(cmd.name)) {
          overrides.set(
            `${binding.processor_uuid}:${cmd.name}`,
            commandOwnerMap.get(cmd.name)!,
          );
        } else {
          commandOwnerMap.set(cmd.name, agent.name);
        }
      }
    }
    return overrides;
  }, [bindings, agentMap, componentMap]);

  function update(patch: Partial<BotCommandSettings>) {
    onChange({ ...value, prefixes, processors: bindings, ...patch });
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
    update({ prefixes: [...prefixes, trimmed] });
    setNewPrefix('');
  }

  function handleRemovePrefix(prefixToRemove: string) {
    if (prefixes.length <= 1) {
      toast.error(t('bots.pluginCommands.prefixInvalid'));
      return;
    }
    update({ prefixes: prefixes.filter((p) => p !== prefixToRemove) });
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = bindings.findIndex((p) => p.processor_uuid === active.id);
    const newIndex = bindings.findIndex((p) => p.processor_uuid === over.id);
    if (oldIndex !== -1 && newIndex !== -1) {
      update({ processors: arrayMove(bindings, oldIndex, newIndex) });
    }
  }

  function toggleSelected(agent: Agent, checked: boolean) {
    const pluginId = commandProcessorPluginId(agent);
    setSelected((prev) => {
      // Keep at most one instance per plugin in a single selection.
      const others = prev.filter(
        (uuid) => commandProcessorPluginId(agentMap.get(uuid)) !== pluginId,
      );
      return checked ? [...others, agent.uuid ?? ''] : others;
    });
  }

  function handleConfirmAdd() {
    if (selected.length === 0) return;
    update({
      processors: [
        ...bindings,
        ...selected.map((processor_uuid) => ({
          processor_uuid,
          enabled: true,
        })),
      ],
    });
    setDialogOpen(false);
  }

  async function createDefaultInstance(component: CommandProcessorDescriptor) {
    if (creatingRef.current) return;
    creatingRef.current = true;
    setCreating(component.plugin_id);
    try {
      const agent: Agent = {
        name: component.plugin_id,
        description: '',
        emoji: '⌨️',
        kind: 'command_processor',
        component_ref: component.id,
      };
      const result = await httpClient.createAgent(agent);
      const created = { ...agent, uuid: result.uuid };
      onCreated(created);
      update({
        processors: [
          ...bindings,
          { processor_uuid: result.uuid, enabled: true },
        ],
      });
      setDialogOpen(false);
    } catch {
      toast.error(t('agents.createError'));
    } finally {
      creatingRef.current = false;
      setCreating(null);
    }
  }

  const nothingToAdd =
    availableProcessors.length === 0 && pluginsWithoutInstance.length === 0;

  return (
    <div className="space-y-4">
      {!value.enabled && (
        <p className="text-center text-xs text-muted-foreground">
          {t('bots.routingLayers.commandsDisabled')}
        </p>
      )}
      {value.enabled && (
        <>
          {/* Command processor list and drag reordering */}
          <div className="space-y-2">
            {bindings.length === 0 ? (
              <div className="rounded-lg border border-dashed p-5 text-center text-xs text-muted-foreground">
                {t('bots.pluginCommands.empty')}
              </div>
            ) : (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
              >
                <SortableContext
                  items={bindings.map((p) => p.processor_uuid)}
                  strategy={verticalListSortingStrategy}
                >
                  <div className="space-y-2">
                    {bindings.map((binding) => {
                      const agent = agentMap.get(binding.processor_uuid);
                      return (
                        <SortableProcessorItem
                          key={binding.processor_uuid}
                          binding={binding}
                          agent={agent}
                          component={componentMap.get(
                            commandProcessorPluginId(agent),
                          )}
                          prefixes={prefixes}
                          overriddenCommands={overriddenCommands}
                          onToggleEnabled={(uuid, enabled) =>
                            update({
                              processors: bindings.map((p) =>
                                p.processor_uuid === uuid
                                  ? { ...p, enabled }
                                  : p,
                              ),
                            })
                          }
                          onRemove={(uuid) =>
                            update({
                              processors: bindings.filter(
                                (p) => p.processor_uuid !== uuid,
                              ),
                            })
                          }
                        />
                      );
                    })}
                  </div>
                </SortableContext>
              </DndContext>
            )}
            {bindings.length > 1 && (
              <p className="text-[11px] text-muted-foreground">
                {t('bots.pluginCommands.dragHint')}
              </p>
            )}
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setSelected([]);
                  setDialogOpen(true);
                }}
                disabled={loading || nothingToAdd}
                className="flex-1"
              >
                <Plus className="mr-1 size-3.5" />
                {t('bots.pluginCommands.addPlugin')}
              </Button>
              {/* Prefixes change rarely, so they live behind a small popover. */}
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-8 shrink-0 px-2 text-xs text-muted-foreground"
                    title={t('bots.pluginCommands.prefixes')}
                    aria-label={t('bots.pluginCommands.prefixes')}
                  >
                    <Settings2 className="mr-1 size-3.5" />
                    <span className="font-mono">{prefixes.join(' ')}</span>
                  </Button>
                </PopoverTrigger>
                <PopoverContent align="end" className="w-72 space-y-2 p-3">
                  <Label className="text-xs font-medium">
                    {t('bots.pluginCommands.prefixes')}
                  </Label>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {prefixes.map((p) => (
                      <Badge
                        key={p}
                        variant="secondary"
                        className="flex h-7 items-center gap-1 px-2 font-mono text-sm"
                      >
                        {p}
                        {prefixes.length > 1 && (
                          <button
                            type="button"
                            onClick={() => handleRemovePrefix(p)}
                            className="rounded-full p-0.5 text-muted-foreground hover:text-foreground"
                            title={t('common.remove')}
                            aria-label={`${t('common.remove')} ${p}`}
                          >
                            <X className="size-3" />
                          </button>
                        )}
                      </Badge>
                    ))}
                  </div>
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
                    aria-label={t('bots.pluginCommands.addPrefix')}
                    className="h-8 font-mono text-xs"
                  />
                </PopoverContent>
              </Popover>
            </div>
          </div>
          {registrationCapability && (
            <PlatformCommandRegistration
              value={value}
              onChange={onChange}
              capability={registrationCapability}
              botId={botId}
              dirty={dirty}
              names={[
                ...new Set(
                  bindings
                    .filter((binding) => binding.enabled)
                    .flatMap(
                      (binding) =>
                        componentMap
                          .get(
                            commandProcessorPluginId(
                              agentMap.get(binding.processor_uuid),
                            ),
                          )
                          ?.commands.map((command) => command.name) ?? [],
                    ),
                ),
              ]}
            />
          )}
        </>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base">
              {t('bots.pluginCommands.selectPlugins')}
            </DialogTitle>
            <DialogDescription className="text-xs">
              {t('bots.pluginCommands.instanceHint')}
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-72 overflow-y-auto space-y-2 py-2">
            {nothingToAdd && (
              <p className="text-xs text-muted-foreground py-4 text-center">
                {t('bots.pluginCommands.noAvailablePlugins')}
              </p>
            )}
            {availableProcessors.map((agent) => {
              const pluginId = commandProcessorPluginId(agent);
              const { author, name } = splitPluginId(pluginId);
              const commands = componentMap.get(pluginId)?.commands ?? [];
              return (
                <label
                  key={agent.uuid}
                  className="flex items-center justify-between p-2.5 rounded-lg border hover:bg-muted/50 cursor-pointer transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Checkbox
                      checked={selected.includes(agent.uuid ?? '')}
                      onCheckedChange={(checked) =>
                        toggleSelected(agent, Boolean(checked))
                      }
                    />
                    <div className="size-7 shrink-0 overflow-hidden rounded">
                      <AuthenticatedPluginIcon
                        author={author}
                        name={name}
                        className="size-7"
                      />
                    </div>
                    <div className="min-w-0">
                      <div className="font-medium text-xs truncate">
                        {agent.emoji || '⌨️'} {agent.name}
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
            })}
            {pluginsWithoutInstance.length > 0 && (
              <div className="space-y-2 pt-2">
                <p className="text-[11px] text-muted-foreground">
                  {t('bots.pluginCommands.createDefaultHint')}
                </p>
                {pluginsWithoutInstance.map((component) => {
                  const { author, name } = splitPluginId(component.plugin_id);
                  return (
                    <div
                      key={component.plugin_id}
                      className="flex items-center justify-between gap-3 p-2.5 rounded-lg border border-dashed"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="size-7 shrink-0 overflow-hidden rounded">
                          <AuthenticatedPluginIcon
                            author={author}
                            name={name}
                            className="size-7"
                          />
                        </div>
                        <div className="min-w-0">
                          <div className="font-mono text-xs truncate">
                            {component.plugin_id}
                          </div>
                          <div className="text-[11px] text-muted-foreground">
                            {t('bots.pluginCommands.commandsCount', {
                              count: component.commands.length,
                            })}
                          </div>
                        </div>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="h-7 text-xs shrink-0"
                        disabled={creating !== null}
                        onClick={() => void createDefaultInstance(component)}
                      >
                        <Plus className="size-3.5 mr-1" />
                        {t('bots.pluginCommands.createDefault')}
                      </Button>
                    </div>
                  );
                })}
              </div>
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
              disabled={selected.length === 0}
              onClick={handleConfirmAdd}
            >
              {t('common.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
