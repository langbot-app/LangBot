'use client';

import { useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { UseFormReturn } from 'react-hook-form';
import {
  ArrowRight,
  Ban,
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  GripVertical,
  Plus,
  Trash2,
  Workflow,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DndContext,
  DragOverlay,
  closestCenter,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragStartEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Input } from '@/components/ui/input';
import { EventBinding, Agent } from '@/app/infra/entities/api';

export const PIPELINE_DISCARD = '__discard__';

// ── types ─────────────────────────────────────────────────────────────────────

interface EventBindingsEditorProps {
  form: UseFormReturn<any>;
  supportedEvents: string[];
  agentOptions: Agent[];
}

type FilterField =
  | 'chat_type'
  | 'chat_id'
  | 'message_text'
  | 'message_element_types';
type FilterOperator =
  | 'eq'
  | 'neq'
  | 'contains'
  | 'not_contains'
  | 'starts_with'
  | 'regex';

interface FilterRow {
  field: FilterField;
  operator: FilterOperator;
  value: string;
}

const OPERATORS_BY_FIELD: Record<FilterField, FilterOperator[]> = {
  chat_type: ['eq', 'neq'],
  chat_id: ['eq', 'neq', 'contains', 'not_contains', 'regex'],
  message_text: [
    'contains',
    'not_contains',
    'eq',
    'neq',
    'starts_with',
    'regex',
  ],
  message_element_types: ['contains', 'not_contains'],
};

const ELEMENTS = [
  'Image',
  'Voice',
  'File',
  'Forward',
  'Face',
  'At',
  'AtAll',
  'Quote',
];

// Adapters that don't declare `supported_events` (e.g. legacy adapters)
// only emit message.received, so that's the sole fallback option.
const DEFAULT_EVENTS = ['message.received'];

// ── helpers ───────────────────────────────────────────────────────────────────

function isMessageEventPattern(p: string) {
  return p === 'message.*' || p.startsWith('message.');
}

function eventPatternCovers(sup: string, bind: string) {
  if (sup === '*') return true;
  if (sup === bind) return true;
  if (bind === '*') return false;
  if (sup.endsWith('.*')) {
    const ns = sup.replace('.*', '');
    return bind === `${ns}.*` || bind.startsWith(`${ns}.`);
  }
  return false;
}

function agentSupportsEventPattern(agent: Agent, pattern: string) {
  const patterns = agent.supported_event_patterns ??
    agent.capability?.supported_event_patterns ?? ['*'];
  return patterns.some((p) => eventPatternCovers(p, pattern));
}

function eventNamespaces(events: string[]) {
  // Only surface a `ns.*` wildcard when the namespace actually has 2+
  // concrete events — otherwise the wildcard is redundant with the single event.
  const counts = new Map<string, number>();
  events.forEach((e) => {
    const n = e.split('.')[0];
    if (n) counts.set(n, (counts.get(n) ?? 0) + 1);
  });
  return Array.from(counts.entries())
    .filter(([, c]) => c >= 2)
    .map(([n]) => `${n}.*`)
    .sort();
}

// Localized label for an event pattern. Concrete events look up
// `bots.eventNames.<event_with_underscores>`, falling back to the raw
// string when no translation exists (e.g. custom/unknown events).
function eventLabel(event: string, t: TFunction) {
  if (event === '*') return t('bots.eventWildcard');
  if (event.endsWith('.*'))
    return t('bots.eventNamespaceWildcard', {
      namespace: event.replace('.*', ''),
    });
  const key = `bots.eventNames.${event.replace(/\./g, '_')}`;
  const label = t(key);
  return label === key ? event : label;
}

function targetLabel(agent: Agent) {
  return `${agent.emoji ? `${agent.emoji} ` : ''}${agent.name}`;
}

// ── target combobox (type + target merged, with search + groups) ───────────────

// Encoded value: "discard", "agent:<uuid>", "pipeline:<uuid>"
function encodeTarget(type: EventBinding['target_type'], uuid: string): string {
  return type === 'discard' ? 'discard' : `${type}:${uuid}`;
}
function decodeTarget(val: string): {
  type: EventBinding['target_type'];
  uuid: string;
} {
  if (val === 'discard') return { type: 'discard', uuid: '' };
  const sep = val.indexOf(':');
  return {
    type: val.slice(0, sep) as EventBinding['target_type'],
    uuid: val.slice(sep + 1),
  };
}

function TargetCombobox({
  binding,
  agentOptions,
  onUpdate,
}: {
  binding: EventBinding;
  agentOptions: Agent[];
  onUpdate: (patch: Partial<EventBinding>) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const pipelineAllowed = isMessageEventPattern(binding.event_pattern);
  const targetType = binding.target_type || 'agent';

  const current =
    targetType === 'discard'
      ? encodeTarget('discard', '')
      : binding.target_uuid
        ? encodeTarget(targetType, binding.target_uuid)
        : '';

  const agents = agentOptions.filter(
    (a) =>
      a.kind === 'agent' && agentSupportsEventPattern(a, binding.event_pattern),
  );
  const pipelines = pipelineAllowed
    ? agentOptions.filter((a) => a.kind === 'pipeline')
    : [];

  function currentLabel() {
    if (targetType === 'discard')
      return (
        <span className="flex items-center gap-1.5 text-destructive">
          <Ban className="size-3.5" />
          {t('bots.targetDiscard')}
        </span>
      );
    const agent = agentOptions.find((a) => a.uuid === binding.target_uuid);
    if (agent)
      return (
        <span className="flex items-center gap-1.5">
          {agent.kind === 'pipeline' ? (
            <Workflow className="size-3.5" />
          ) : (
            <Bot className="size-3.5" />
          )}
          {targetLabel(agent)}
        </span>
      );
    return (
      <span className="text-muted-foreground">{t('bots.selectTarget')}</span>
    );
  }

  function select(val: string) {
    const { type, uuid } = decodeTarget(val);
    onUpdate({ target_type: type, target_uuid: uuid });
    setOpen(false);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="h-8 w-[200px] justify-between text-sm font-normal px-3"
        >
          <span className="truncate">{currentLabel()}</span>
          <ChevronsUpDown className="ml-1 h-3.5 w-3.5 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[240px] p-0" align="start">
        <Command>
          <CommandInput placeholder={t('bots.searchTarget')} className="h-8" />
          <CommandList>
            <CommandEmpty>{t('bots.noTargetFound')}</CommandEmpty>
            {agents.length > 0 && (
              <CommandGroup heading={t('bots.targetAgent')}>
                {agents.map((a) => (
                  <CommandItem
                    key={a.uuid}
                    value={`agent:${a.uuid}:${a.name}`}
                    onSelect={() => select(encodeTarget('agent', a.uuid || ''))}
                  >
                    <Bot className="mr-2 size-3.5 shrink-0" />
                    <span className="truncate">{targetLabel(a)}</span>
                    {current === encodeTarget('agent', a.uuid || '') && (
                      <Check className="ml-auto size-3.5 shrink-0" />
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {pipelines.length > 0 && (
              <CommandGroup heading={t('bots.targetPipeline')}>
                {pipelines.map((a) => (
                  <CommandItem
                    key={a.uuid}
                    value={`pipeline:${a.uuid}:${a.name}`}
                    onSelect={() =>
                      select(encodeTarget('pipeline', a.uuid || ''))
                    }
                  >
                    <Workflow className="mr-2 size-3.5 shrink-0" />
                    <span className="truncate">{targetLabel(a)}</span>
                    {current === encodeTarget('pipeline', a.uuid || '') && (
                      <Check className="ml-auto size-3.5 shrink-0" />
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

// ── filter conditions panel ───────────────────────────────────────────────────

function FilterConditionsPanel({
  filters,
  onChange,
}: {
  filters: FilterRow[];
  onChange: (f: FilterRow[]) => void;
}) {
  const { t } = useTranslation();

  function add() {
    onChange([
      ...filters,
      { field: 'chat_type', operator: 'eq', value: 'person' },
    ]);
  }

  function update(i: number, patch: Partial<FilterRow>) {
    const next = [...filters];
    next[i] = { ...next[i], ...patch };
    if ('field' in patch) {
      next[i].operator = OPERATORS_BY_FIELD[patch.field as FilterField][0];
      next[i].value = '';
    }
    onChange(next);
  }

  function remove(i: number) {
    const next = [...filters];
    next.splice(i, 1);
    onChange(next);
  }

  return (
    <div className="space-y-1.5">
      {filters.length === 0 && (
        <p className="text-xs text-muted-foreground">
          {t('bots.conditionsEmpty')}
        </p>
      )}
      {filters.map((f, i) => (
        <div key={i} className="flex items-center gap-2">
          <Select
            value={f.field}
            onValueChange={(v) => update(i, { field: v as FilterField })}
          >
            <SelectTrigger className="h-8 w-[130px] text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="chat_type">
                {t('bots.filterChatType')}
              </SelectItem>
              <SelectItem value="chat_id">{t('bots.filterChatId')}</SelectItem>
              <SelectItem value="message_text">
                {t('bots.filterMessageText')}
              </SelectItem>
              <SelectItem value="message_element_types">
                {t('bots.filterMessageElement')}
              </SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={f.operator}
            onValueChange={(v) => update(i, { operator: v as FilterOperator })}
          >
            <SelectTrigger className="h-8 w-[110px] text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(OPERATORS_BY_FIELD[f.field] ?? ['eq']).map((op) => (
                <SelectItem key={op} value={op}>
                  {t(`bots.operator_${op}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {f.field === 'chat_type' ? (
            <Select
              value={f.value}
              onValueChange={(v) => update(i, { value: v })}
            >
              <SelectTrigger className="h-8 w-[90px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="person">
                  {t('bots.sessionTypePerson')}
                </SelectItem>
                <SelectItem value="group">
                  {t('bots.sessionTypeGroup')}
                </SelectItem>
              </SelectContent>
            </Select>
          ) : f.field === 'message_element_types' ? (
            <Select
              value={f.value}
              onValueChange={(v) => update(i, { value: v })}
            >
              <SelectTrigger className="h-8 w-[100px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ELEMENTS.map((el) => (
                  <SelectItem key={el} value={el}>
                    {t(`bots.element${el}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Input
              className="h-8 w-[160px] text-xs"
              placeholder={
                f.field === 'chat_id'
                  ? t('bots.ruleValueLauncherIdPlaceholder')
                  : t('bots.ruleValueMessagePlaceholder')
              }
              value={f.value}
              onChange={(e) => update(i, { value: e.target.value })}
            />
          )}

          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0"
            onClick={() => remove(i)}
          >
            <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-7 px-1 text-xs text-muted-foreground"
        onClick={add}
      >
        <Plus className="h-3 w-3 mr-1" />
        {t('bots.addFilter')}
      </Button>
    </div>
  );
}

// ── single binding card ───────────────────────────────────────────────────────

interface BindingCardProps {
  binding: EventBinding;
  globalIndex: number;
  eventOptions: string[];
  agentOptions: Agent[];
  expandedIds: Set<string>;
  onToggleExpand: (id: string) => void;
  onUpdate: (globalIndex: number, patch: Partial<EventBinding>) => void;
  onRemove: (globalIndex: number) => void;
  dragHandleProps?: Record<string, unknown>;
  isOverlay?: boolean;
}

function BindingCardContent({
  binding,
  globalIndex,
  eventOptions,
  agentOptions,
  expandedIds,
  onToggleExpand,
  onUpdate,
  onRemove,
  dragHandleProps,
}: BindingCardProps) {
  const { t } = useTranslation();
  const isEnabled = binding.enabled ?? true;
  const id = String(binding.id ?? globalIndex);
  const isExpanded = expandedIds.has(id);
  const filterCount = (binding.filters as FilterRow[] | undefined)?.length ?? 0;
  const pipelineAllowed = isMessageEventPattern(binding.event_pattern);

  return (
    <div className="rounded-lg border bg-card">
      {/* main row */}
      <div className="flex items-center gap-2 p-2.5">
        {isEnabled && (
          <button
            type="button"
            className="cursor-grab active:cursor-grabbing shrink-0 text-muted-foreground hover:text-foreground touch-none"
            {...dragHandleProps}
          >
            <GripVertical className="h-4 w-4" />
          </button>
        )}

        <Select
          value={binding.event_pattern}
          onValueChange={(eventPattern) => {
            const patch: Partial<EventBinding> = {
              event_pattern: eventPattern,
            };
            if (
              binding.target_type === 'pipeline' &&
              !isMessageEventPattern(eventPattern)
            ) {
              patch.target_type = 'agent';
              patch.target_uuid = '';
            }
            onUpdate(globalIndex, patch);
          }}
        >
          <SelectTrigger className="h-8 flex-1 min-w-0 text-sm">
            {binding.event_pattern ? (
              <span className="truncate">
                {eventLabel(binding.event_pattern, t)}
              </span>
            ) : (
              <SelectValue placeholder={t('bots.eventPatternPlaceholder')} />
            )}
          </SelectTrigger>
          <SelectContent>
            {eventOptions.map((event) => {
              const label = eventLabel(event, t);
              return (
                <SelectItem key={event} value={event}>
                  <span className="flex flex-col">
                    <span>{label}</span>
                    {label !== event && (
                      <span className="text-[11px] text-muted-foreground font-mono">
                        {event}
                      </span>
                    )}
                  </span>
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>

        {/* conditions toggle */}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 px-2 text-xs text-muted-foreground shrink-0"
          onClick={() => onToggleExpand(id)}
        >
          {isExpanded ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          {t('bots.conditions')}
          {filterCount > 0 && (
            <Badge variant="secondary" className="h-4 px-1 text-[10px] ml-0.5">
              {filterCount}
            </Badge>
          )}
        </Button>

        <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />

        <TargetCombobox
          binding={binding}
          agentOptions={agentOptions}
          onUpdate={(patch) => onUpdate(globalIndex, patch)}
        />

        {!pipelineAllowed && binding.target_type === 'pipeline' && (
          <span className="text-xs text-destructive shrink-0">
            {t('bots.unsupportedPipelineEvent')}
          </span>
        )}

        {/* disable/enable toggle */}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 px-2 text-xs text-muted-foreground shrink-0"
          onClick={() => onUpdate(globalIndex, { enabled: !isEnabled })}
        >
          {isEnabled ? t('bots.disable') : t('bots.enable')}
        </Button>

        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0"
          onClick={() => onRemove(globalIndex)}
        >
          <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
        </Button>
      </div>

      {/* conditions panel */}
      {isExpanded && (
        <div className="border-t px-3 py-2.5">
          <FilterConditionsPanel
            filters={(binding.filters as unknown as FilterRow[]) || []}
            onChange={(filters) =>
              onUpdate(globalIndex, {
                filters: filters as unknown as Record<string, unknown>[],
              })
            }
          />
        </div>
      )}
    </div>
  );
}

// ── sortable wrapper ──────────────────────────────────────────────────────────

function SortableBindingCard(props: BindingCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useSortable({ id: props.binding.id ?? props.globalIndex });
  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        opacity: isDragging ? 0.3 : undefined,
      }}
    >
      <BindingCardContent
        {...props}
        dragHandleProps={{ ...attributes, ...listeners }}
      />
    </div>
  );
}

// ── main editor ───────────────────────────────────────────────────────────────

export default function EventBindingsEditor({
  form,
  supportedEvents,
  agentOptions,
}: EventBindingsEditorProps) {
  const { t } = useTranslation();
  const bindings: EventBinding[] = form.watch('event_bindings') || [];
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [disabledSectionOpen, setDisabledSectionOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);

  // stable ids for dnd
  const nextId = useRef(0);
  const idsRef = useRef<string[]>([]);
  const enabledBindings = bindings.filter((b) => b.enabled ?? true);
  useMemo(() => {
    while (idsRef.current.length < enabledBindings.length)
      idsRef.current.push(`b-${nextId.current++}`);
    if (idsRef.current.length > enabledBindings.length)
      idsRef.current = idsRef.current.slice(0, enabledBindings.length);
  }, [enabledBindings.length]);

  const eventOptions = useMemo(() => {
    const concrete =
      supportedEvents.length > 0 ? supportedEvents : DEFAULT_EVENTS;
    return [...eventNamespaces(concrete), ...concrete].filter(
      (e, i, a) => a.indexOf(e) === i,
    );
  }, [supportedEvents]);

  function updateBindings(next: EventBinding[]) {
    form.setValue('event_bindings', next, { shouldDirty: true });
  }

  function addBinding() {
    updateBindings([
      ...bindings,
      {
        event_pattern: 'message.received',
        target_type: 'agent',
        target_uuid: '',
        priority: bindings.length,
        enabled: true,
        description: '',
        filters: [],
      },
    ]);
  }

  function updateBinding(index: number, patch: Partial<EventBinding>) {
    const next = [...bindings];
    next[index] = { ...next[index], ...patch };
    updateBindings(next);
  }

  function removeBinding(index: number) {
    const next = [...bindings];
    next.splice(index, 1);
    updateBindings(next);
  }

  function toggleExpand(id: string) {
    setExpandedIds((prev) => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });
  }

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  function handleDragStart(e: DragStartEvent) {
    setActiveId(String(e.active.id));
  }

  function handleDragEnd(e: DragEndEvent) {
    setActiveId(null);
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    // reorder only within enabled bindings; disabled ones stay at end
    const enabledIdxs = bindings.reduce<number[]>((acc, b, i) => {
      if (b.enabled ?? true) acc.push(i);
      return acc;
    }, []);
    const activeEnabledIdx = idsRef.current.indexOf(String(active.id));
    const overEnabledIdx = idsRef.current.indexOf(String(over.id));
    if (activeEnabledIdx === -1 || overEnabledIdx === -1) return;
    const newOrder = arrayMove(enabledIdxs, activeEnabledIdx, overEnabledIdx);
    idsRef.current = arrayMove(
      idsRef.current,
      activeEnabledIdx,
      overEnabledIdx,
    );
    const disabledBindings = bindings.filter((b) => !(b.enabled ?? true));
    updateBindings([...newOrder.map((i) => bindings[i]), ...disabledBindings]);
  }

  const disabledBindings = bindings.reduce<{ b: EventBinding; i: number }[]>(
    (acc, b, i) => {
      if (!(b.enabled ?? true)) acc.push({ b, i });
      return acc;
    },
    [],
  );

  const activeEnabledIdx = activeId ? idsRef.current.indexOf(activeId) : -1;
  const activeBinding =
    activeEnabledIdx >= 0 ? enabledBindings[activeEnabledIdx] : null;
  const activeGlobalIdx = activeBinding ? bindings.indexOf(activeBinding) : -1;

  return (
    <div className="space-y-3">
      {/* enabled section */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={idsRef.current}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-2">
            {enabledBindings.length === 0 && (
              <div className="rounded-lg border border-dashed p-5 text-center text-sm text-muted-foreground">
                {t('bots.noEventBindings')}
              </div>
            )}
            {enabledBindings.map((binding, sortIdx) => {
              const globalIdx = bindings.indexOf(binding);
              return (
                <SortableBindingCard
                  key={idsRef.current[sortIdx]}
                  binding={binding}
                  globalIndex={globalIdx}
                  eventOptions={eventOptions}
                  agentOptions={agentOptions}
                  expandedIds={expandedIds}
                  onToggleExpand={toggleExpand}
                  onUpdate={updateBinding}
                  onRemove={removeBinding}
                />
              );
            })}
          </div>
        </SortableContext>
        <DragOverlay dropAnimation={null}>
          {activeBinding && activeGlobalIdx >= 0 ? (
            <BindingCardContent
              binding={activeBinding}
              globalIndex={activeGlobalIdx}
              eventOptions={eventOptions}
              agentOptions={agentOptions}
              expandedIds={expandedIds}
              onToggleExpand={toggleExpand}
              onUpdate={updateBinding}
              onRemove={removeBinding}
              isOverlay
            />
          ) : null}
        </DragOverlay>
      </DndContext>

      <Button type="button" variant="outline" size="sm" onClick={addBinding}>
        <Plus className="h-4 w-4 mr-1" />
        {t('bots.addEventBinding')}
      </Button>

      {/* disabled section */}
      {disabledBindings.length > 0 && (
        <div className="rounded-lg border border-dashed">
          <button
            type="button"
            className="flex w-full items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
            onClick={() => setDisabledSectionOpen((v) => !v)}
          >
            {disabledSectionOpen ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            {t('bots.disabledBindings')}
            <Badge variant="outline" className="ml-1 text-xs">
              {disabledBindings.length}
            </Badge>
          </button>
          {disabledSectionOpen && (
            <div className="border-t p-2 space-y-2">
              {disabledBindings.map(({ b, i }) => (
                <BindingCardContent
                  key={b.id ?? i}
                  binding={b}
                  globalIndex={i}
                  eventOptions={eventOptions}
                  agentOptions={agentOptions}
                  expandedIds={expandedIds}
                  onToggleExpand={toggleExpand}
                  onUpdate={updateBinding}
                  onRemove={removeBinding}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
