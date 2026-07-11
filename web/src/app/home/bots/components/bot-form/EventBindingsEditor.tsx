'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { UseFormReturn } from 'react-hook-form';
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Ban,
  Bot,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  GripVertical,
  ListChecks,
  Plus,
  Play,
  RefreshCw,
  Trash2,
  Workflow,
  XCircle,
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
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
import { Textarea } from '@/components/ui/textarea';
import {
  EventBinding,
  Agent,
  BotRouteDryRunResult,
  BotEventRouteStatus,
  BotRouteTestResult,
} from '@/app/infra/entities/api';
import { backendClient } from '@/app/infra/http';

export const PIPELINE_DISCARD = '__discard__';

// ── types ─────────────────────────────────────────────────────────────────────

interface EventBindingsEditorProps {
  form: UseFormReturn<any>;
  botId?: string;
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

function eventDescription(event: string, t: TFunction) {
  if (event === '*') return t('bots.eventDescriptions.all');
  if (event.endsWith('.*')) return t('bots.eventDescriptions.namespace');
  const key = `bots.eventDescriptions.${event.replace(/\./g, '_')}`;
  const description = t(key);
  return description === key ? t('bots.eventDescriptions.custom') : description;
}

function targetLabel(agent: Agent) {
  return `${agent.emoji ? `${agent.emoji} ` : ''}${agent.name}`;
}

function targetTypeLabel(
  type: EventBinding['target_type'] | undefined,
  t: TFunction,
) {
  if (type === 'pipeline') return t('bots.targetPipeline');
  if (type === 'discard') return t('bots.targetDiscard');
  return t('bots.targetAgent');
}

function routeStatusLabel(
  status: BotEventRouteStatus['last_status'] | undefined,
  t: TFunction,
) {
  if (!status) return t('bots.routeStatusIdle');
  const key = `bots.routeStatus.${status}`;
  const label = t(key);
  return label === key ? String(status) : label;
}

function routeStatusBadgeClass(
  status: BotEventRouteStatus['last_status'] | undefined,
) {
  if (status === 'delivered') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/30 dark:text-emerald-300';
  }
  if (status === 'matched' || status === 'discarded') {
    return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/40 dark:bg-sky-950/30 dark:text-sky-300';
  }
  if (status === 'failed' || status === 'not_matched') {
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-300';
  }
  return 'border-border bg-muted/40 text-muted-foreground';
}

function localizedFailureReason(
  failureCode: string | null | undefined,
  fallback: string | null | undefined,
  t: TFunction,
) {
  if (!failureCode) return fallback || '';
  const key = `bots.routeFailure.${failureCode}`;
  const label = t(key);
  return label === key ? fallback || failureCode : label;
}

function routeStatusDetail(
  status: BotEventRouteStatus | undefined,
  t: TFunction,
) {
  if (!status) return '';
  if (status.failure_code) {
    return localizedFailureReason(status.failure_code, status.reason, t);
  }
  if (status.last_status) {
    const key = `bots.routeStatusDetail.${status.last_status}`;
    const label = t(key);
    if (label !== key) return label;
  }
  return status.reason || formatRouteStatusTime(status.timestamp);
}

function diagnosticDetailLabel(
  detail: Record<string, unknown>,
  fallbackIndex: number,
  t: TFunction,
) {
  const order =
    typeof detail.binding_index === 'number'
      ? detail.binding_index
      : typeof detail.order === 'number'
        ? detail.order
        : fallbackIndex;
  const route = t('bots.dryRunRuleIndex', { index: order + 1 });
  if (detail.selected) {
    return t('bots.dryRunDiagnosticSelected', { route });
  }
  const failureCode =
    typeof detail.failure_code === 'string' ? detail.failure_code : null;
  const reason = localizedFailureReason(
    failureCode,
    typeof detail.reason === 'string' ? detail.reason : null,
    t,
  );
  if (detail.matched) {
    return t('bots.dryRunDiagnosticMatched', { route, reason });
  }
  return t('bots.dryRunDiagnosticSkipped', { route, reason });
}

function formatRouteStatusTime(timestamp: number | null | undefined) {
  if (!timestamp) return '';
  return new Date(timestamp * 1000).toLocaleString();
}

function samplePayloadForEvent(eventType: string): Record<string, unknown> {
  if (eventType === 'message.received') {
    return {
      message_text: 'Hello',
      chat_type: 'private',
      chat_id: 'test-user',
      user_id: 'test-user',
    };
  }
  if (eventType === 'group.member_joined') {
    return {
      group_id: 'test-group',
      group_name: 'Test Group',
      user_id: 'test-user',
      user_name: 'Test User',
    };
  }
  if (eventType === 'group.member_left') {
    return {
      group_id: 'test-group',
      group_name: 'Test Group',
      user_id: 'test-user',
      user_name: 'Test User',
      is_kicked: false,
    };
  }
  if (eventType === 'platform.specific') {
    return { action: 'test', data: {} };
  }
  return {};
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

// ── adapter capability summary ────────────────────────────────────────────────

function AdapterCapabilitySummary({
  supportedEvents,
  eventOptions,
}: {
  supportedEvents: string[];
  eventOptions: string[];
}) {
  const { t } = useTranslation();
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const concreteEvents =
    supportedEvents.length > 0 ? supportedEvents : DEFAULT_EVENTS;
  const previewEvents = concreteEvents.slice(0, 4);

  return (
    <div className="rounded-lg border bg-muted/20 p-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-background text-primary shadow-xs">
              <Activity className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium">
                {t('bots.adapterEventsTitle')}
              </p>
              <p className="text-xs text-muted-foreground">
                {t('bots.adapterEventsDescription', {
                  count: concreteEvents.length,
                })}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {previewEvents.map((event) => (
              <Badge
                key={event}
                variant="secondary"
                className="max-w-full rounded-md px-2 py-0.5 font-normal"
                title={event}
              >
                <span className="truncate">{eventLabel(event, t)}</span>
              </Badge>
            ))}
            {concreteEvents.length > previewEvents.length && (
              <Badge variant="outline" className="rounded-md px-2 py-0.5">
                {t('bots.adapterEventsMore', {
                  count: concreteEvents.length - previewEvents.length,
                })}
              </Badge>
            )}
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 shrink-0 px-2 text-xs"
          onClick={() => setAdvancedOpen((v) => !v)}
        >
          {advancedOpen ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          {t('bots.advancedEventValues')}
        </Button>
      </div>
      {advancedOpen && (
        <div className="mt-3 grid gap-2 border-t pt-3 sm:grid-cols-2">
          {eventOptions.map((event) => (
            <div key={event} className="min-w-0 rounded-md bg-background p-2">
              <div className="flex min-w-0 items-center justify-between gap-2">
                <span className="truncate text-xs font-medium">
                  {eventLabel(event, t)}
                </span>
                {event.endsWith('.*') && (
                  <Badge variant="outline" className="shrink-0 text-[10px]">
                    {t('bots.eventGroup')}
                  </Badge>
                )}
              </div>
              <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-muted-foreground">
                {eventDescription(event, t)}
              </p>
              <code className="mt-1 block truncate text-[11px] text-muted-foreground">
                {event}
              </code>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── route dry-run dialog ─────────────────────────────────────────────────────

function RouteDryRunDialog({
  botId,
  bindings,
  eventOptions,
  agentOptions,
  onRouteStatusUpdate,
}: {
  botId?: string;
  bindings: EventBinding[];
  eventOptions: string[];
  agentOptions: Agent[];
  onRouteStatusUpdate?: (statuses: BotEventRouteStatus[]) => void;
}) {
  const { t } = useTranslation();
  const firstEvent = eventOptions[0] ?? DEFAULT_EVENTS[0];
  const [open, setOpen] = useState(false);
  const [eventType, setEventType] = useState(firstEvent);
  const [payloadText, setPayloadText] = useState(() =>
    JSON.stringify(samplePayloadForEvent(firstEvent), null, 2),
  );
  const [advancedPayloadOpen, setAdvancedPayloadOpen] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isDispatching, setIsDispatching] = useState(false);
  const [payloadError, setPayloadError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<BotRouteDryRunResult | null>(null);
  const [dispatchResult, setDispatchResult] =
    useState<BotRouteTestResult | null>(null);

  useEffect(() => {
    if (!eventOptions.includes(eventType)) {
      setEventType(firstEvent);
    }
  }, [eventOptions, eventType, firstEvent]);

  useEffect(() => {
    setPayloadText(JSON.stringify(samplePayloadForEvent(eventType), null, 2));
    setPayloadError(null);
    setResult(null);
    setDispatchResult(null);
  }, [eventType]);

  function resolveTargetName(resultTarget?: BotRouteDryRunResult['target']) {
    if (!resultTarget) return '';
    if (resultTarget.target_name) return resultTarget.target_name;
    if (resultTarget.target_type === 'discard') return t('bots.targetDiscard');
    const agent = agentOptions.find((a) => a.uuid === resultTarget.target_uuid);
    return agent ? targetLabel(agent) : (resultTarget.target_uuid ?? '');
  }

  function parsePayload(): Record<string, unknown> | null {
    setPayloadError(null);
    let payload: Record<string, unknown> = {};
    if (payloadText.trim()) {
      try {
        const parsed = JSON.parse(payloadText);
        if (
          parsed === null ||
          typeof parsed !== 'object' ||
          Array.isArray(parsed)
        ) {
          setPayloadError(t('bots.dryRunPayloadObjectError'));
          return null;
        }
        payload = parsed as Record<string, unknown>;
      } catch {
        setPayloadError(t('bots.dryRunPayloadJsonError'));
        return null;
      }
    }
    return payload;
  }

  async function runDryRun() {
    setRunError(null);
    setResult(null);
    setDispatchResult(null);

    const payload = parsePayload();
    if (payload === null) return;

    if (!botId) {
      setRunError(t('bots.dryRunNeedsSavedBot'));
      return;
    }

    setIsRunning(true);
    try {
      const dryRunResult = await backendClient.dryRunBotEventRoute(botId, {
        event_type: eventType,
        payload,
        event_bindings: bindings,
      });
      setResult({
        ...dryRunResult,
        diagnostic_steps: dryRunResult.diagnostic_steps ?? [],
      });
    } catch (error) {
      const err = error as { msg?: string };
      setRunError(err.msg || t('bots.dryRunFailed'));
    } finally {
      setIsRunning(false);
    }
  }

  async function dispatchTestEvent() {
    setRunError(null);
    setDispatchResult(null);

    const payload = parsePayload();
    if (payload === null) return;

    if (!botId) {
      setRunError(t('bots.dryRunNeedsSavedBot'));
      return;
    }

    setIsDispatching(true);
    try {
      const testResult = await backendClient.testBotEventRoute(botId, {
        event_type: eventType,
        payload,
      });
      setDispatchResult(testResult);
      onRouteStatusUpdate?.(testResult.route_status?.routes || []);
      if (!testResult.dispatched) {
        setRunError(
          localizedFailureReason(
            testResult.failure_code,
            testResult.reason,
            t,
          ) || t('bots.routeTestFailed'),
        );
      }
    } catch (error) {
      const err = error as { msg?: string };
      setRunError(err.msg || t('bots.routeTestFailed'));
    } finally {
      setIsDispatching(false);
    }
  }

  const targetName = result ? resolveTargetName(result.target) : '';

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
      >
        <Play className="h-4 w-4 mr-1" />
        {t('bots.testRoute')}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('bots.dryRunTitle')}</DialogTitle>
            <DialogDescription>{t('bots.dryRunDescription')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  {t('bots.dryRunEventType')}
                </label>
                <Select value={eventType} onValueChange={setEventType}>
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {eventOptions.map((event) => (
                      <SelectItem key={event} value={event}>
                        {eventLabel(event, t)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="rounded-md border bg-muted/20 px-3 py-2.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">
                      {t('bots.dryRunSampleReady')}
                    </p>
                    <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                      {t('bots.dryRunSampleDescription', {
                        event: eventLabel(eventType, t),
                      })}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-8 shrink-0 px-2 text-xs"
                    onClick={() => setAdvancedPayloadOpen((value) => !value)}
                  >
                    {advancedPayloadOpen ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5" />
                    )}
                    {advancedPayloadOpen
                      ? t('bots.dryRunHidePayload')
                      : t('bots.dryRunEditPayload')}
                  </Button>
                </div>
                {advancedPayloadOpen && (
                  <div className="mt-3 space-y-1.5 border-t pt-3">
                    <label className="text-xs font-medium">
                      {t('bots.dryRunPayload')}
                    </label>
                    <Textarea
                      value={payloadText}
                      onChange={(e) => setPayloadText(e.target.value)}
                      className="min-h-[118px] font-mono text-xs"
                      spellCheck={false}
                      placeholder='{"message_text": "hello"}'
                    />
                    {payloadError ? (
                      <p className="text-xs text-destructive">{payloadError}</p>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        {t('bots.dryRunPayloadHint')}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>

            {runError && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{runError}</AlertDescription>
              </Alert>
            )}

            {result && (
              <div className="rounded-lg border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  {result.matched ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <XCircle className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span className="text-sm font-medium">
                    {result.matched
                      ? t('bots.dryRunMatched')
                      : t('bots.dryRunNotMatched')}
                  </span>
                  {result.failure_code && (
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {result.failure_code}
                    </Badge>
                  )}
                </div>

                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-md bg-muted/40 p-2">
                    <p className="text-xs text-muted-foreground">
                      {t('bots.dryRunTarget')}
                    </p>
                    <p className="mt-1 truncate text-sm font-medium">
                      {result.target
                        ? `${targetTypeLabel(result.target.target_type, t)}${
                            targetName ? ` · ${targetName}` : ''
                          }`
                        : t('bots.dryRunNoTarget')}
                    </p>
                  </div>
                  <div className="rounded-md bg-muted/40 p-2">
                    <p className="text-xs text-muted-foreground">
                      {t('bots.dryRunMatchedRule')}
                    </p>
                    <p className="mt-1 truncate text-sm font-medium">
                      {result.matched_binding_index !== undefined &&
                      result.matched_binding_index !== null
                        ? t('bots.dryRunRuleIndex', {
                            index: result.matched_binding_index + 1,
                          })
                        : result.matched_binding_id || t('bots.dryRunNoRule')}
                    </p>
                  </div>
                </div>

                {(result.diagnostic_details?.length ||
                  result.diagnostic_steps.length > 0) && (
                  <div className="mt-3">
                    <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                      <ListChecks className="h-3.5 w-3.5" />
                      {t('bots.dryRunDiagnostics')}
                    </div>
                    <ol className="space-y-1 pl-5 text-xs text-muted-foreground">
                      {result.diagnostic_details?.length
                        ? result.diagnostic_details.map((detail, index) => (
                            <li
                              key={`${index}:${String(detail.binding_id ?? '')}`}
                              className="list-decimal"
                            >
                              {diagnosticDetailLabel(detail, index, t)}
                            </li>
                          ))
                        : result.diagnostic_steps.map((step, index) => (
                            <li
                              key={`${index}:${step}`}
                              className="list-decimal"
                            >
                              {step}
                            </li>
                          ))}
                    </ol>
                  </div>
                )}
              </div>
            )}

            {dispatchResult?.dispatched && (
              <Alert>
                <CheckCircle2 className="h-4 w-4" />
                <AlertDescription>
                  {t('bots.routeTestDispatched', {
                    count: dispatchResult.suppressed_outputs?.length || 0,
                  })}
                </AlertDescription>
              </Alert>
            )}

            <Alert className="border-amber-200 bg-amber-50/60 text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-200">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {t('bots.routeTestSideEffectWarning')}
              </AlertDescription>
            </Alert>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              {t('common.close')}
            </Button>
            <Button
              type="button"
              onClick={runDryRun}
              disabled={isRunning || isDispatching}
            >
              <Play className="h-4 w-4 mr-1" />
              {isRunning ? t('bots.dryRunRunning') : t('bots.dryRunAction')}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={dispatchTestEvent}
              disabled={isRunning || isDispatching}
            >
              <Activity className="h-4 w-4 mr-1" />
              {isDispatching
                ? t('bots.routeTestRunning')
                : t('bots.routeTestAction')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ── single binding card ───────────────────────────────────────────────────────

interface BindingCardProps {
  binding: EventBinding;
  globalIndex: number;
  routeStatus?: BotEventRouteStatus;
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
  routeStatus,
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
  const statusTime = formatRouteStatusTime(routeStatus?.timestamp);
  const statusDetail = routeStatusDetail(routeStatus, t);

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
                    <span className="text-[11px] text-muted-foreground">
                      {eventDescription(event, t)}
                    </span>
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

        <div className="hidden min-w-[132px] max-w-[220px] flex-col items-end gap-1 lg:flex">
          <Badge
            variant="outline"
            className={`rounded-md px-2 py-0.5 text-[10px] font-medium ${routeStatusBadgeClass(
              routeStatus?.last_status,
            )}`}
          >
            {routeStatusLabel(routeStatus?.last_status, t)}
          </Badge>
          <span
            className="max-w-full truncate text-[11px] text-muted-foreground"
            title={
              statusTime ? `${statusDetail} · ${statusTime}` : statusDetail
            }
          >
            {statusDetail || statusTime}
          </span>
        </div>

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

      <div className="flex items-center gap-2 border-t px-3 py-1.5 lg:hidden">
        <Badge
          variant="outline"
          className={`rounded-md px-2 py-0.5 text-[10px] font-medium ${routeStatusBadgeClass(
            routeStatus?.last_status,
          )}`}
        >
          {routeStatusLabel(routeStatus?.last_status, t)}
        </Badge>
        <span
          className="min-w-0 truncate text-[11px] text-muted-foreground"
          title={routeStatus?.reason || routeStatus?.message || statusTime}
        >
          {routeStatus?.failure_code || routeStatus?.reason || statusTime}
        </span>
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
  botId,
  supportedEvents,
  agentOptions,
}: EventBindingsEditorProps) {
  const { t } = useTranslation();
  const bindings: EventBinding[] = form.watch('event_bindings') || [];
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [disabledSectionOpen, setDisabledSectionOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [routeStatuses, setRouteStatuses] = useState<BotEventRouteStatus[]>([]);
  const [routeStatusLoading, setRouteStatusLoading] = useState(false);
  const [routeStatusError, setRouteStatusError] = useState<string | null>(null);

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
  const dryRunEventOptions = useMemo(
    () => (supportedEvents.length > 0 ? supportedEvents : DEFAULT_EVENTS),
    [supportedEvents],
  );
  const routeStatusByBinding = useMemo(() => {
    const map = new Map<string, BotEventRouteStatus>();
    routeStatuses.forEach((status) => {
      if (status.binding_id) map.set(String(status.binding_id), status);
    });
    return map;
  }, [routeStatuses]);

  const refreshRouteStatuses = useCallback(async () => {
    if (!botId) {
      setRouteStatuses([]);
      setRouteStatusError(null);
      return;
    }
    setRouteStatusLoading(true);
    setRouteStatusError(null);
    try {
      const response = await backendClient.getBotEventRouteStatuses(botId);
      setRouteStatuses(response.routes || []);
    } catch (error) {
      const err = error as { msg?: string };
      setRouteStatusError(err.msg || t('bots.routeStatusRefreshFailed'));
    } finally {
      setRouteStatusLoading(false);
    }
  }, [botId, t]);

  useEffect(() => {
    refreshRouteStatuses();
  }, [refreshRouteStatuses]);

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
      if (s.has(id)) {
        s.delete(id);
      } else {
        s.add(id);
      }
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
      <AdapterCapabilitySummary
        supportedEvents={supportedEvents}
        eventOptions={eventOptions}
      />

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
                  routeStatus={
                    binding.id
                      ? routeStatusByBinding.get(String(binding.id))
                      : undefined
                  }
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
              routeStatus={
                activeBinding.id
                  ? routeStatusByBinding.get(String(activeBinding.id))
                  : undefined
              }
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

      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={addBinding}>
          <Plus className="h-4 w-4 mr-1" />
          {t('bots.addEventBinding')}
        </Button>
        <RouteDryRunDialog
          botId={botId}
          bindings={bindings}
          eventOptions={dryRunEventOptions}
          agentOptions={agentOptions}
          onRouteStatusUpdate={setRouteStatuses}
        />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={refreshRouteStatuses}
          disabled={!botId || routeStatusLoading}
        >
          <RefreshCw
            className={`h-4 w-4 mr-1 ${routeStatusLoading ? 'animate-spin' : ''}`}
          />
          {t('bots.refreshRouteStatus')}
        </Button>
      </div>
      {routeStatusError && (
        <p className="text-xs text-destructive">{routeStatusError}</p>
      )}

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
                  routeStatus={
                    b.id ? routeStatusByBinding.get(String(b.id)) : undefined
                  }
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
