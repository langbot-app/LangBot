import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  AlertCircle,
  AlertTriangle,
  ChevronDown,
  CircleHelp,
  LoaderCircle,
  Play,
} from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import type { AgentPlatformTool } from '@/app/infra/entities/api';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  eventGroupLabel,
  eventPatternDescription,
  eventPatternLabel,
  groupEventPatterns,
} from '@/app/home/components/event-patterns/event-pattern-groups';
import EventSelectOptionContent from '@/app/home/components/event-patterns/EventSelectOptionContent';
import AgentExecutionTrace from './AgentExecutionTrace';
import { executionSteps, type DebugExecutionEvent } from './debug-execution';

interface AgentDebugPanelProps {
  agentId: string;
  availableEventTypes: string[];
  platformTools?: AgentPlatformTool[];
  supportedEventPatterns?: string[];
  beforeRun?: () => Promise<boolean>;
  hasUnsavedChanges?: boolean;
  onOpenRunnerConfig?: () => void;
}

interface DebugEntry {
  id: string;
  direction: 'input' | 'output' | 'error';
  eventType: string;
  text: string;
  errorCode?: string;
  detail?: string;
  events?: DebugExecutionEvent[];
  finished?: boolean;
}

const EVENT_PRESET_DATA: Record<
  string,
  { text: string; data: Record<string, unknown> }
> = {
  'message.received': {
    text: '',
    data: {},
  },
  'group.member_joined': {
    text: 'A new member joined the group.',
    data: {
      group_id: 'debug-group',
      member_id: 'debug-user',
      member_name: 'Debug User',
    },
  },
  'group.member_left': {
    text: 'A member left the group.',
    data: {
      group_id: 'debug-group',
      member_id: 'debug-user',
      member_name: 'Debug User',
    },
  },
  'friend.request_received': {
    text: 'A user sent a friend request.',
    data: {
      requester_id: 'debug-user',
      requester_name: 'Debug User',
      request_id: 'debug-friend-request',
      message: 'Hello',
    },
  },
  'feedback.received': {
    text: 'The user submitted feedback.',
    data: {
      rating: 5,
      content: 'Debug feedback',
    },
  },
  'friend.added': {
    text: 'A friend was added.',
    data: { user_id: 'debug-user', user_name: 'Debug User' },
  },
  'group.member_banned': {
    text: 'A member was banned.',
    data: {
      group_id: 'debug-group',
      member_id: 'debug-user',
      member_name: 'Debug User',
    },
  },
  'bot.invited_to_group': {
    text: 'The bot was invited to a group.',
    data: {
      group_id: 'debug-group',
      request_id: 'debug-group-request',
      requester_id: 'debug-user',
    },
  },
  'bot.muted': {
    text: 'The bot was muted.',
    data: { group_id: 'debug-group', duration: 60 },
  },
  'bot.unmuted': {
    text: 'The bot was unmuted.',
    data: { group_id: 'debug-group' },
  },
  'bot.removed_from_group': {
    text: 'The bot was removed from the group.',
    data: { group_id: 'debug-group' },
  },
  'message.edited': {
    text: 'A message was edited.',
    data: {
      group_id: 'debug-group',
      message_id: 'debug-message',
      text: 'Edited message',
    },
  },
  'message.deleted': {
    text: 'A message was deleted.',
    data: { group_id: 'debug-group', message_id: 'debug-message' },
  },
  'message.reaction': {
    text: 'A reaction was added.',
    data: {
      group_id: 'debug-group',
      message_id: 'debug-message',
      reaction: '👍',
    },
  },
  'platform.specific': {
    text: 'A platform-specific event occurred.',
    data: { event_name: 'debug-platform-event' },
  },
};

function createDebugSessionId(agentId: string) {
  const nonce = globalThis.crypto?.randomUUID?.() ?? String(Date.now());
  return `webui:${agentId}:${nonce}`;
}

function matchesEventPattern(pattern: string, eventType: string) {
  const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`^${escaped.replaceAll('*', '.*')}$`).test(eventType);
}

export default function AgentDebugPanel({
  agentId,
  availableEventTypes,
  platformTools = [],
  supportedEventPatterns = ['*'],
  beforeRun,
  hasUnsavedChanges = false,
  onOpenRunnerConfig,
}: AgentDebugPanelProps) {
  const { t } = useTranslation();
  const toolLabels = Object.fromEntries(
    platformTools.map((tool) => [tool.name, extractI18nObject(tool.label)]),
  );
  const [preset, setPreset] = useState('message.received');
  const [customEventType, setCustomEventType] = useState('custom.event');
  const [inputText, setInputText] = useState('');
  const [eventDataText, setEventDataText] = useState('{}');
  const [mockOptionsText, setMockOptionsText] = useState('{}');
  const [running, setRunning] = useState(false);
  const [entries, setEntries] = useState<DebugEntry[]>([]);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef(createDebugSessionId(agentId));
  const requestRef = useRef<AbortController | null>(null);

  useEffect(() => () => requestRef.current?.abort(), [agentId]);

  useLayoutEffect(() => {
    const transcript = transcriptRef.current;
    if (transcript) {
      transcript.scrollTop = transcript.scrollHeight;
    }
  }, [entries]);

  const eventType = preset === 'custom' ? customEventType.trim() : preset;
  const isMessageEvent = eventType.startsWith('message.');
  const supportedLabel = useMemo(
    () => supportedEventPatterns.join(', '),
    [supportedEventPatterns],
  );
  const availableEvents = useMemo(() => {
    const concretePatterns = supportedEventPatterns.filter(
      (pattern) => pattern !== '*' && !pattern.endsWith('.*'),
    );
    return Array.from(new Set([...availableEventTypes, ...concretePatterns]))
      .filter((candidate) =>
        supportedEventPatterns.some((pattern) =>
          matchesEventPattern(pattern, candidate),
        ),
      )
      .sort();
  }, [availableEventTypes, supportedEventPatterns]);
  const eventGroups = useMemo(
    () => groupEventPatterns(availableEvents),
    [availableEvents],
  );
  const supportsCustomEvent = supportedEventPatterns.some(
    (pattern) => pattern === '*' || pattern.endsWith('.*'),
  );

  useEffect(() => {
    if (
      availableEvents.includes(preset) ||
      (preset === 'custom' && supportsCustomEvent)
    ) {
      return;
    }
    selectPreset(availableEvents[0] ?? 'custom');
  }, [availableEvents, preset, supportsCustomEvent]);

  function selectPreset(value: string) {
    setPreset(value);
    const nextPreset = EVENT_PRESET_DATA[value] ?? { text: '', data: {} };
    setInputText(nextPreset.text);
    setEventDataText(JSON.stringify(nextPreset.data, null, 2));
  }

  async function runDebugEvent() {
    if (!eventType) {
      toast.error(t('agents.debugEventTypeRequired'));
      return;
    }
    if (isMessageEvent && !inputText.trim()) {
      toast.error(t('agents.debugInputRequired'));
      return;
    }
    if (
      !supportedEventPatterns.some((pattern) =>
        matchesEventPattern(pattern, eventType),
      )
    ) {
      toast.error(t('agents.debugUnsupportedEvent'));
      return;
    }

    let eventData: Record<string, unknown>;
    let mockOptions: Record<string, unknown>;
    try {
      const parsed = JSON.parse(eventDataText || '{}');
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
        throw new Error('payload must be an object');
      }
      eventData = parsed as Record<string, unknown>;
    } catch {
      toast.error(t('agents.debugInvalidPayload'));
      return;
    }
    try {
      const parsed = JSON.parse(mockOptionsText || '{}');
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object')
        throw new Error('Mock options must be an object');
      mockOptions = parsed;
    } catch {
      toast.error(t('agents.debugInvalidMock'));
      return;
    }

    setRunning(true);
    if (hasUnsavedChanges && beforeRun && !(await beforeRun())) {
      setRunning(false);
      return;
    }

    const requestId = globalThis.crypto?.randomUUID?.() ?? String(Date.now());
    const controller = new AbortController();
    requestRef.current = controller;
    const outputId = `execution:${requestId}`;
    setEntries((current) => [
      ...current,
      {
        id: `input:${requestId}`,
        direction: 'input',
        eventType,
        text: inputText.trim() || JSON.stringify(eventData, null, 2),
      },
    ]);
    try {
      const result = await httpClient.streamDebugAgent(
        agentId,
        {
          event_type: eventType,
          text: inputText.trim(),
          data: eventData,
          mock: mockOptions,
          conversation_id: sessionIdRef.current,
        },
        (event) => {
          if (controller.signal.aborted) return;
          setEntries((current) => {
            const existing = current.find((entry) => entry.id === outputId);
            if (existing)
              return current.map((entry) =>
                entry.id === outputId
                  ? { ...entry, events: [...(entry.events ?? []), event] }
                  : entry,
              );
            return [
              ...current,
              {
                id: outputId,
                direction: 'output',
                eventType,
                text: '',
                events: [event],
              },
            ];
          });
        },
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setEntries((current) =>
        current.some((entry) => entry.id === outputId)
          ? current.map((entry) =>
              entry.id === outputId
                ? {
                    ...entry,
                    finished: true,
                    text: executionSteps(entry.events ?? []).some(
                      (step) =>
                        step.kind === 'tool' || step.text || step.reasoning,
                    )
                      ? ''
                      : result.final_text || t('agents.debugNoTextOutput'),
                  }
                : entry,
            )
          : [
              ...current,
              {
                id: outputId,
                direction: 'output',
                eventType,
                text: result.final_text || t('agents.debugNoTextOutput'),
              },
            ],
      );
      if (isMessageEvent)
        setInputText((current) => (current === inputText ? '' : current));
    } catch (error) {
      if (controller.signal.aborted) {
        if (controller.signal.reason === 'user') {
          setEntries((current) => [
            ...current.map((entry) =>
              entry.id === outputId ? { ...entry, finished: true } : entry,
            ),
            {
              id: `cancel:${requestId}`,
              direction: 'error',
              eventType,
              text: t('agents.debugCancelled'),
            },
          ]);
        }
        return;
      }
      const errorCode =
        typeof error === 'object' && error && 'code' in error
          ? String((error as { code?: string }).code || '')
          : '';
      const message =
        typeof error === 'object' && error && 'msg' in error
          ? String((error as { msg?: string }).msg || '')
          : t('agents.debugRunFailed');
      const isConfigError = errorCode.endsWith('.config_invalid');
      const isExecutionError = errorCode === 'runner_execution_failed';
      const isTimeout = errorCode === 'runner.timeout';
      const friendlyMessage = isConfigError
        ? t('agents.debugRunnerConfigInvalidDescription', {
            message:
              message === 'api-key is required'
                ? t('agents.debugApiKeyRequired')
                : message,
          })
        : isExecutionError
          ? t('agents.debugRunnerExecutionFailedDescription')
          : isTimeout
            ? t('agents.debugRunnerTimeoutDescription')
            : message || t('agents.debugRunFailed');
      setEntries((current) => [
        ...current.map((entry) =>
          entry.id === outputId ? { ...entry, finished: true } : entry,
        ),
        {
          id: `error:${requestId}`,
          direction: 'error',
          eventType,
          text: friendlyMessage,
          errorCode,
          detail:
            isExecutionError || isTimeout
              ? message || t('agents.debugRunFailed')
              : undefined,
        },
      ]);
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setRunning(false);
      }
    }
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col">
      <div ref={transcriptRef} className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="mb-3">
          <p className="text-sm font-medium">{t('agents.debugTranscript')}</p>
          <p className="text-xs text-muted-foreground">
            {t('agents.debugTranscriptDescription')}
          </p>
        </div>
        {entries.length === 0 ? (
          <Alert className="my-4 bg-muted/20">
            <CircleHelp className="size-4" />
            <AlertTitle>{t('agents.debugEmptyTitle')}</AlertTitle>
            <AlertDescription>
              {t('agents.debugEmptyTranscript')}
            </AlertDescription>
          </Alert>
        ) : (
          <div className="space-y-3">
            {entries
              .filter(
                (entry) =>
                  entry.direction !== 'output' ||
                  entry.text ||
                  executionSteps(entry.events ?? []).some(
                    (step) =>
                      step.kind === 'tool' || step.text || step.reasoning,
                  ),
              )
              .map((entry) => (
                <Alert
                  key={entry.id}
                  variant={
                    entry.direction === 'error' ? 'destructive' : 'default'
                  }
                  className={
                    entry.direction === 'output'
                      ? 'border-primary/20 bg-primary/5'
                      : entry.direction === 'input'
                        ? 'bg-muted/40'
                        : undefined
                  }
                >
                  {entry.direction === 'error' && <AlertCircle />}
                  <div className="col-start-2 min-w-0">
                    <div className="mb-2 flex min-w-0 flex-wrap items-center justify-between gap-2">
                      <Badge
                        variant="outline"
                        className="max-w-full overflow-hidden text-ellipsis"
                      >
                        {entry.eventType}
                      </Badge>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {entry.direction === 'output'
                          ? t('agents.debugAgentOutput')
                          : entry.direction === 'error'
                            ? t('common.error')
                            : t('agents.debugTestInput')}
                      </span>
                    </div>
                    {entry.events && (
                      <AgentExecutionTrace
                        events={entry.events}
                        finished={entry.finished}
                        toolLabels={toolLabels}
                      />
                    )}
                    {entry.text && (
                      <pre className="min-w-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere] font-sans text-sm leading-relaxed">
                        {entry.text}
                      </pre>
                    )}
                    {entry.detail && (
                      <Collapsible className="mt-3">
                        <CollapsibleTrigger asChild>
                          <Button type="button" variant="ghost" size="sm">
                            {t('agents.debugErrorDetails')}
                            <ChevronDown className="size-3.5" />
                          </Button>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                          <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-words [overflow-wrap:anywhere] rounded-md bg-muted p-2 font-mono text-xs text-muted-foreground">
                            {entry.detail}
                          </pre>
                        </CollapsibleContent>
                      </Collapsible>
                    )}
                    {(entry.errorCode?.endsWith('.config_invalid') ||
                      entry.errorCode === 'runner_execution_failed' ||
                      entry.errorCode === 'runner.timeout') &&
                      onOpenRunnerConfig && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="mt-3"
                          onClick={onOpenRunnerConfig}
                        >
                          {t('agents.debugReviewRunnerConfig')}
                        </Button>
                      )}
                  </div>
                </Alert>
              ))}
          </div>
        )}
      </div>

      <div className="shrink-0 space-y-3 border-t p-3">
        {supportedEventPatterns.length === 0 ? (
          <Alert className="bg-amber-500/5 text-amber-800 dark:text-amber-200">
            <AlertTriangle className="size-4" />
            <AlertTitle>{t('agents.debugNoEventsTitle')}</AlertTitle>
            <AlertDescription>
              {t('agents.debugNoEventsDescription')}
            </AlertDescription>
          </Alert>
        ) : (
          <>
            <div className="space-y-1.5">
              <Label>{t('agents.debugEventType')}</Label>
              <Select value={preset} onValueChange={selectPreset}>
                <SelectTrigger
                  className="w-full"
                  aria-label={t('agents.debugEventType')}
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="w-[var(--radix-select-trigger-width)] max-w-[calc(100vw-2rem)]">
                  {eventGroups.map((group) => (
                    <SelectGroup key={group.namespace}>
                      <SelectLabel>
                        {eventGroupLabel(group.namespace, t)}
                      </SelectLabel>
                      {group.patterns.map((event) => (
                        <SelectItem
                          key={event}
                          value={event}
                          description={eventPatternDescription(event, t)}
                          className="py-2"
                        >
                          <EventSelectOptionContent
                            event={event}
                            label={eventPatternLabel(event, t)}
                          />
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  ))}
                  {supportsCustomEvent && (
                    <SelectGroup>
                      <SelectLabel>{t('agents.debugCustomEvent')}</SelectLabel>
                      <SelectItem
                        value="custom"
                        description={t('bots.eventDescriptions.custom')}
                        className="py-2"
                      >
                        <EventSelectOptionContent
                          event="custom.event"
                          label={t('agents.debugCustomEvent')}
                        />
                      </SelectItem>
                    </SelectGroup>
                  )}
                </SelectContent>
              </Select>
            </div>

            {preset === 'custom' && (
              <div className="space-y-1.5">
                <Label htmlFor="agent-debug-custom-event">
                  {t('agents.debugCustomEventType')}
                </Label>
                <Input
                  id="agent-debug-custom-event"
                  value={customEventType}
                  onChange={(event) => setCustomEventType(event.target.value)}
                  placeholder="custom.event"
                />
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="agent-debug-input">
                {isMessageEvent
                  ? t('agents.debugMessageInput')
                  : t('agents.debugEventSummary')}
              </Label>
              <Textarea
                id="agent-debug-input"
                value={inputText}
                onChange={(event) => setInputText(event.target.value)}
                className="min-h-20 resize-y"
                placeholder={t('agents.debugInputPlaceholder')}
              />
            </div>

            <details className="rounded-md border bg-muted/20 px-3 py-2">
              <summary className="cursor-pointer text-xs font-medium">
                {t('agents.debugEventPayload')}
              </summary>
              <div className="mt-2 space-y-2">
                <p className="text-xs text-muted-foreground">
                  {t('agents.debugSupportedEvents')}: {supportedLabel}
                </p>
                <Textarea
                  id="agent-debug-payload"
                  value={eventDataText}
                  onChange={(event) => setEventDataText(event.target.value)}
                  className="min-h-28 resize-y font-mono text-xs"
                  spellCheck={false}
                />
              </div>
            </details>

            <details className="rounded-md border bg-muted/20 px-3 py-2">
              <summary className="cursor-pointer text-xs font-medium">
                {t('agents.debugMockOptions')}
              </summary>
              <p className="my-2 text-xs text-muted-foreground">
                {t('agents.debugMockOptionsHelp')}
              </p>
              <Textarea
                aria-label={t('agents.debugMockOptions')}
                value={mockOptionsText}
                onChange={(event) => setMockOptionsText(event.target.value)}
                className="min-h-24 font-mono text-xs"
                spellCheck={false}
              />
            </details>
            <Button
              type="button"
              className="w-full"
              onClick={() =>
                running ? requestRef.current?.abort('user') : runDebugEvent()
              }
            >
              {running ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Play className="size-4" />
              )}
              {running
                ? t('agents.debugStop')
                : hasUnsavedChanges
                  ? t('agents.debugSaveAndRun')
                  : t('agents.debugRun')}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
