import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
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
import EventProcessorTrace from './EventProcessorTrace';
import AgentExecutionTrace from './AgentExecutionTrace';
import AgentEventDataEditor from './AgentEventDataEditor';
import {
  createDebugEventData,
  debugEventInputText,
  invalidDebugEventField,
  parseDebugEventData,
  processorDebugEventTypes,
} from './debug-event-data';
import { executionSteps, type DebugExecutionEvent } from './debug-execution';

interface AgentDebugPanelProps {
  agentId: string;
  processor?: boolean;
  availableEventTypes: string[];
  platformTools?: AgentPlatformTool[];
  supportedEventPatterns?: string[];
  beforeRun?: () => Promise<boolean>;
  onRunFinished?: () => void;
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
  processor = false,
  availableEventTypes,
  platformTools = [],
  supportedEventPatterns = ['*'],
  beforeRun,
  onRunFinished,
  hasUnsavedChanges = false,
  onOpenRunnerConfig,
}: AgentDebugPanelProps) {
  const { t } = useTranslation();
  const toolLabels = Object.fromEntries(
    platformTools.map((tool) => [tool.name, extractI18nObject(tool.label)]),
  );
  const [preset, setPreset] = useState('message.received');
  const [customEventType, setCustomEventType] = useState('custom.event');
  const newEventData = useCallback(
    (type: string) =>
      JSON.stringify(
        createDebugEventData(
          type,
          {
            user: t('agents.debugData.sampleUser'),
            message: t('agents.debugData.sampleMessage'),
            feedback: t('agents.debugData.sampleFeedback'),
          },
          processor,
        ),
        null,
        2,
      ),
    [t, processor],
  );
  const [eventDataText, setEventDataText] = useState(() =>
    newEventData('message.received'),
  );
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
  const eventDataValid = parseDebugEventData(eventDataText) !== null;
  const availableEvents = useMemo(() => {
    const concretePatterns = supportedEventPatterns.filter(
      (pattern) => pattern !== '*' && !pattern.endsWith('.*'),
    );
    return Array.from(
      new Set([
        ...(processor ? processorDebugEventTypes : availableEventTypes),
        ...concretePatterns,
      ]),
    )
      .filter((candidate) =>
        supportedEventPatterns.some((pattern) =>
          matchesEventPattern(pattern, candidate),
        ),
      )
      .sort();
  }, [availableEventTypes, supportedEventPatterns, processor]);
  const eventGroups = useMemo(
    () => groupEventPatterns(availableEvents),
    [availableEvents],
  );
  const supportsCustomEvent =
    !processor &&
    supportedEventPatterns.some(
      (pattern) => pattern === '*' || pattern.endsWith('.*'),
    );

  const selectPreset = useCallback(
    (value: string) => {
      setPreset(value);
      setEventDataText(newEventData(value));
    },
    [newEventData],
  );

  useEffect(() => {
    if (
      availableEvents.includes(preset) ||
      (preset === 'custom' && supportsCustomEvent)
    ) {
      return;
    }
    selectPreset(availableEvents[0] ?? 'custom');
  }, [availableEvents, preset, supportsCustomEvent, selectPreset]);

  async function runDebugEvent() {
    if (!eventType) {
      toast.error(t('agents.debugEventTypeRequired'));
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

    const eventData = parseDebugEventData(eventDataText);
    if (!eventData) {
      toast.error(t('agents.debugInvalidPayload'));
      return;
    }
    const invalidField = invalidDebugEventField(
      eventType,
      eventData,
      processor,
    );
    if (invalidField) {
      toast.error(
        t('agents.debugData.invalidField', {
          field: t(`agents.debugData.${invalidField.label}`),
        }),
      );
      return;
    }
    const inputText = debugEventInputText(eventType, eventData, processor);
    let mockOptions: Record<string, unknown>;
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
                    text:
                      processor ||
                      executionSteps(entry.events ?? []).some(
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
        onRunFinished?.();
      }
    }
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col">
      <div ref={transcriptRef} className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="mb-3">
          <p className="text-sm font-medium">{t('agents.debugTranscript')}</p>
          <p className="text-xs text-muted-foreground">
            {t(
              processor
                ? 'agents.eventProcessor.debugDescription'
                : 'agents.debugTranscriptDescription',
            )}
          </p>
        </div>
        {entries.length === 0 ? (
          !processor && (
            <Alert className="my-4 bg-muted/20">
              <CircleHelp className="size-4" />
              <AlertTitle>{t('agents.debugEmptyTitle')}</AlertTitle>
              <AlertDescription>
                {t('agents.debugEmptyTranscript')}
              </AlertDescription>
            </Alert>
          )
        ) : (
          <div className="space-y-3">
            {entries
              .filter(
                (entry) =>
                  entry.direction !== 'output' ||
                  entry.text ||
                  processor ||
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
                          ? t(
                              processor
                                ? 'agents.eventProcessor.debugOutput'
                                : 'agents.debugAgentOutput',
                            )
                          : entry.direction === 'error'
                            ? t('common.error')
                            : t('agents.debugTestInput')}
                      </span>
                    </div>
                    {entry.events &&
                      (processor ? (
                        <EventProcessorTrace
                          events={entry.events}
                          toolLabels={toolLabels}
                        />
                      ) : (
                        <AgentExecutionTrace
                          events={entry.events}
                          finished={entry.finished}
                          toolLabels={toolLabels}
                        />
                      ))}
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

      <div className="flex max-h-[60%] min-h-0 shrink-0 flex-col border-t">
        <div className="min-h-0 space-y-3 overflow-y-auto p-3">
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
                        <SelectLabel>
                          {t('agents.debugCustomEvent')}
                        </SelectLabel>
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

              <AgentEventDataEditor
                key={eventType}
                eventType={eventType}
                processor={processor}
                custom={preset === 'custom'}
                value={eventDataText}
                onChange={setEventDataText}
              />

              <Collapsible>
                <CollapsibleTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="group"
                  >
                    <ChevronDown className="size-3.5 transition-transform group-data-[state=open]:rotate-180" />
                    {t('agents.debugMockOptions')}
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent>
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
                </CollapsibleContent>
              </Collapsible>
            </>
          )}
        </div>
        {supportedEventPatterns.length > 0 && (
          <div className="shrink-0 px-3 pb-3">
            <Button
              type="button"
              className="w-full"
              disabled={!running && !eventDataValid}
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
          </div>
        )}
      </div>
    </div>
  );
}
