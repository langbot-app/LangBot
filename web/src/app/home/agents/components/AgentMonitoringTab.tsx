import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Brain, ChevronRight, RefreshCw, Wrench } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import type {
  AgentPlatformTool,
  ProcessorRun,
  ProcessorRunEvent,
} from '@/app/infra/entities/api';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { eventPatternLabel } from '@/app/home/components/event-patterns/event-pattern-groups';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from '@/components/ui/collapsible';
import { executionSteps } from './debug-execution';
import { ProcessorPayload } from './PluginProcessorTrace';
import {
  formatRunDuration,
  processorRunDuration,
} from './processor-run-timing';

const activeStatuses = new Set([
  'created',
  'pending',
  'queued',
  'claimed',
  'running',
  'waiting',
]);
const failedStatuses = new Set(['failed', 'timeout']);
const json = (value: unknown) =>
  typeof value === 'string' ? value : JSON.stringify(value, null, 2);
const textClass =
  'whitespace-pre-wrap break-words [overflow-wrap:anywhere] text-sm';

export default function AgentMonitoringTab({
  agentId,
  platformTools,
}: {
  agentId: string;
  platformTools: AgentPlatformTool[];
}) {
  const { t } = useTranslation();
  const [runs, setRuns] = useState<ProcessorRun[]>([]);
  const [total, setTotal] = useState<number>();
  const [cursor, setCursor] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState<string>();
  const [selected, setSelected] = useState<ProcessorRun>();
  const [events, setEvents] = useState<ProcessorRunEvent[]>([]);
  const [eventCursor, setEventCursor] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingTrace, setLoadingTrace] = useState(false);
  const [listError, setListError] = useState(false);
  const [traceError, setTraceError] = useState(false);
  const [paging, setPaging] = useState(false);
  const [traceRevision, setTraceRevision] = useState(0);
  const generation = useRef(0);
  const listBusy = useRef(false);
  const listInitialized = useRef(false);
  const traceBusy = useRef(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      generation.current += 1;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (listBusy.current) return;
    listBusy.current = true;
    try {
      const page = await httpClient.getProcessorRuns(agentId);
      if (!alive.current) return;
      setRuns((current) => {
        const merged = new Map(page.items.map((run) => [run.run_id, run]));
        current.forEach((run) => {
          if (!merged.has(run.run_id)) merged.set(run.run_id, run);
        });
        return [...merged.values()];
      });
      if (!listInitialized.current) {
        setCursor(page.has_more ? page.next_cursor : null);
        listInitialized.current = true;
      }
      setTotal(page.total);
      setSelectedId((current) => current ?? page.items[0]?.run_id);
      setListError(false);
    } catch {
      if (alive.current) setListError(true);
    } finally {
      listBusy.current = false;
      if (alive.current) setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    if (!selectedId) return;
    const version = ++generation.current;
    setEvents([]);
    setSelected(undefined);
    setEventCursor(null);
    setLoadingTrace(true);
    setPaging(false);
    setTraceError(false);
    traceBusy.current = false;
    void httpClient
      .getProcessorRunEvents(agentId, selectedId)
      .then((page) => {
        if (generation.current !== version) return;
        setSelected(page.run);
        setEvents(page.items);
        setEventCursor(page.has_more ? page.next_cursor : null);
      })
      .catch(() => {
        if (generation.current === version) setTraceError(true);
      })
      .finally(() => {
        if (generation.current === version) setLoadingTrace(false);
      });
    return () => {
      generation.current += 1;
    };
  }, [agentId, selectedId, traceRevision]);

  const nextEvents = useCallback(async () => {
    if (!selectedId || traceBusy.current || loadingTrace) return;
    const version = generation.current;
    traceBusy.current = true;
    setPaging(true);
    try {
      const page = await httpClient.getProcessorRunEvents(
        agentId,
        selectedId,
        eventCursor ?? events.at(-1)?.sequence,
      );
      if (generation.current !== version) return;
      setSelected(page.run);
      setEvents((current) => [
        ...new Map(
          [...current, ...page.items].map((event) => [event.sequence, event]),
        ).values(),
      ]);
      setEventCursor(page.has_more ? page.next_cursor : null);
      setTraceError(false);
    } catch {
      if (generation.current === version) setTraceError(true);
    } finally {
      if (generation.current === version) {
        traceBusy.current = false;
        setPaging(false);
      }
    }
  }, [agentId, selectedId, eventCursor, events, loadingTrace]);

  useEffect(() => {
    if (
      !selected ||
      !activeStatuses.has(selected.status) ||
      eventCursor !== null
    )
      return;
    const timer = window.setInterval(() => {
      if (!document.hidden) void nextEvents();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [selected, eventCursor, nextEvents]);

  async function moreRuns() {
    if (cursor === null || listBusy.current) return;
    listBusy.current = true;
    setLoading(true);
    try {
      const page = await httpClient.getProcessorRuns(agentId, cursor);
      if (!alive.current) return;
      setRuns((current) => [
        ...new Map(
          [...current, ...page.items].map((run) => [run.run_id, run]),
        ).values(),
      ]);
      setCursor(page.has_more ? page.next_cursor : null);
      setListError(false);
    } catch {
      if (alive.current) setListError(true);
    } finally {
      listBusy.current = false;
      if (alive.current) setLoading(false);
    }
  }

  const labels = Object.fromEntries(
    platformTools.map((tool) => [tool.name, extractI18nObject(tool.label)]),
  );
  const steps = executionSteps(events);
  const duration = selected ? processorRunDuration(selected) : null;
  const failureReason =
    selected?.status_reason ||
    events.findLast((event) => event.type === 'run.failed')?.data.error;
  const models = [
    ...new Set(
      events.flatMap((event) => {
        const message = event.data.message ?? event.data.chunk;
        return message &&
          typeof message === 'object' &&
          'model' in message &&
          typeof message.model === 'string' &&
          message.model
          ? [message.model]
          : [];
      }),
    ),
  ];
  const stateLabel = (run: ProcessorRun) =>
    t(
      `agents.eventProcessor.status_${({ created: 'pending', claimed: 'queued' } as Record<string, string>)[run.status] ?? run.status}`,
      {
        defaultValue: run.status,
      },
    );
  const debugRun = (run: ProcessorRun) =>
    run.binding_id?.startsWith('debug:') || run.metadata.source === 'webui';

  return (
    <div
      className="flex min-h-0 flex-1 flex-col gap-4"
      data-testid="agent-monitoring"
    >
      <div className="flex shrink-0 items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {t('agents.monitoring.description')}
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            void refresh();
            setTraceRevision((value) => value + 1);
          }}
        >
          <RefreshCw className="size-4" />
          {t('monitoring.refreshData')}
        </Button>
      </div>
      {listError && (
        <Alert variant="destructive">
          <AlertDescription>{t('monitoring.loadError')}</AlertDescription>
        </Alert>
      )}
      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(16rem,0.8fr)_minmax(0,2fr)]">
        <section
          className="flex min-h-0 min-w-0 flex-col gap-2"
          aria-label={t('agents.eventProcessor.runs')}
        >
          <p className="text-sm font-medium">
            {t('agents.eventProcessor.runs')}
            {total !== undefined && (
              <span className="ml-2 text-muted-foreground">{total}</span>
            )}
          </p>
          <div className="max-h-72 min-h-0 overflow-y-auto rounded-md border lg:max-h-none lg:flex-1">
            {runs.map((run) => (
              <Button
                key={run.run_id}
                variant="ghost"
                aria-pressed={selectedId === run.run_id}
                onClick={() => setSelectedId(run.run_id)}
                className="h-auto w-full flex-col items-stretch gap-2 rounded-none border-b p-3 text-left font-normal last:border-b-0 aria-pressed:bg-accent"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium">
                    {eventPatternLabel(run.metadata.event_type ?? '', t)}
                  </span>
                  <Badge
                    variant={
                      failedStatuses.has(run.status) ? 'destructive' : 'outline'
                    }
                  >
                    {stateLabel(run)}
                  </Badge>
                </span>
                {run.metadata.input?.text && (
                  <span className="truncate text-sm">
                    {run.metadata.input.text}
                  </span>
                )}
                <span className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <time>
                    {new Date(run.created_at * 1000).toLocaleString()}
                  </time>
                  {debugRun(run) && (
                    <Badge variant="secondary">{t('agents.debugTab')}</Badge>
                  )}
                  {processorRunDuration(run) !== null && (
                    <span>{formatRunDuration(processorRunDuration(run)!)}</span>
                  )}
                </span>
              </Button>
            ))}
            {!runs.length && (
              <p className="p-4 text-sm text-muted-foreground">
                {loading ? t('common.loading') : t('agents.monitoring.empty')}
              </p>
            )}
            {cursor !== null && (
              <Button
                variant="ghost"
                className="w-full"
                disabled={loading}
                onClick={() => void moreRuns()}
              >
                {t('agents.eventProcessor.loadMore')}
              </Button>
            )}
          </div>
        </section>
        <section
          aria-label={t('agents.monitoring.execution')}
          className="min-h-0 min-w-0 space-y-4 overflow-y-auto lg:pr-2"
        >
          {loadingTrace ? (
            <p role="status">{t('common.loading')}</p>
          ) : (
            selected && (
              <>
                <div className="space-y-2 border-b pb-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-medium">
                      {eventPatternLabel(selected.metadata.event_type ?? '', t)}
                    </h2>
                    <Badge
                      variant={
                        failedStatuses.has(selected.status)
                          ? 'destructive'
                          : 'outline'
                      }
                    >
                      {stateLabel(selected)}
                    </Badge>
                    {debugRun(selected) && (
                      <Badge variant="secondary">{t('agents.debugTab')}</Badge>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <time>
                      {new Date(selected.created_at * 1000).toLocaleString()}
                    </time>
                    {duration !== null && (
                      <span>
                        {t('monitoring.llmCalls.duration')}:{' '}
                        {formatRunDuration(duration)}
                      </span>
                    )}
                    {models.length > 0 && <span>{models.join(', ')}</span>}
                    {selected.usage?.total_tokens != null && (
                      <span>
                        {t('monitoring.llmCalls.totalTokens')}:{' '}
                        {selected.usage.total_tokens.toLocaleString()}
                      </span>
                    )}
                  </div>
                  <p className="break-all text-xs text-muted-foreground">
                    {selected.runner_id}
                  </p>
                </div>
                {failedStatuses.has(selected.status) && failureReason && (
                  <Alert variant="destructive">
                    <AlertDescription className={textClass}>
                      {json(failureReason)}
                    </AlertDescription>
                  </Alert>
                )}
                <Card className="gap-2 py-3">
                  <CardHeader className="px-3">
                    <CardTitle className="text-sm">
                      {t('agents.monitoring.input')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 px-3">
                    {selected.metadata.input?.text && (
                      <p className={textClass}>
                        {selected.metadata.input.text}
                      </p>
                    )}
                    {(selected.metadata.input ??
                      selected.metadata.input_event) != null ? (
                      <ProcessorPayload
                        title={t('agents.monitoring.eventData')}
                        value={
                          selected.metadata.input_event
                            ? {
                                ...selected.metadata.input,
                                event: selected.metadata.input_event,
                              }
                            : selected.metadata.input
                        }
                      />
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        {t('agents.monitoring.inputUnavailable')}
                      </p>
                    )}
                  </CardContent>
                </Card>
                <h3 className="text-sm font-medium">
                  {t('agents.monitoring.execution')}
                </h3>
                {steps.map((step, index) => (
                  <Card key={index} className="gap-2 py-3">
                    <CardHeader className="px-3">
                      <CardTitle className="flex min-w-0 items-center gap-2 text-sm">
                        {step.kind === 'tool' ? (
                          <>
                            <Wrench className="size-4 shrink-0" />
                            <span className="break-all">
                              {labels[step.name] || step.name}
                            </span>
                            <Badge
                              variant={
                                step.status === 'failed'
                                  ? 'destructive'
                                  : 'outline'
                              }
                            >
                              {t(
                                `agents.debugTool${step.status === 'running' ? (activeStatuses.has(selected.status) || eventCursor !== null ? 'Running' : 'Interrupted') : step.result && typeof step.result === 'object' && 'mock' in step.result && step.result.mock === true ? (step.status === 'failed' ? 'MockFailed' : 'Simulated') : step.status === 'failed' ? 'Failed' : 'Completed'}`,
                              )}
                            </Badge>
                          </>
                        ) : (
                          <>
                            <Brain className="size-4" />
                            {t('agents.debugTextOutput')}
                          </>
                        )}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 px-3">
                      {step.kind === 'message' ? (
                        <>
                          {step.text && (
                            <p className={textClass}>{step.text}</p>
                          )}
                          {step.reasoning && (
                            <ProcessorPayload
                              title={t('agents.debugReasoning')}
                              value={step.reasoning}
                            />
                          )}
                        </>
                      ) : (
                        <>
                          {step.error && (
                            <p className={`${textClass} text-destructive`}>
                              {step.error}
                            </p>
                          )}
                          <ProcessorPayload
                            title={t('agents.debugToolArguments')}
                            value={step.parameters}
                          />
                          {step.result !== undefined && (
                            <ProcessorPayload
                              title={t('agents.debugToolResult')}
                              value={step.result}
                            />
                          )}
                        </>
                      )}
                    </CardContent>
                  </Card>
                ))}
                {events
                  .filter((event) => event.type === 'processor.log')
                  .map((event) => (
                    <Alert
                      key={event.sequence}
                      variant={
                        event.data.level === 'error' ? 'destructive' : 'default'
                      }
                    >
                      <AlertDescription className={textClass}>
                        {String(event.data.text ?? '')}
                      </AlertDescription>
                    </Alert>
                  ))}
                {eventCursor !== null && (
                  <Button
                    variant="outline"
                    disabled={paging}
                    onClick={() => void nextEvents()}
                  >
                    {t('agents.eventProcessor.loadMore')}
                  </Button>
                )}
                <Collapsible>
                  <CollapsibleTrigger asChild>
                    <Button variant="ghost" className="group">
                      <ChevronRight className="size-4 group-data-[state=open]:rotate-90" />
                      {t('agents.monitoring.rawEvents')}
                    </Button>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <pre
                      className={`${textClass} rounded-md bg-muted p-3 font-mono text-xs`}
                    >
                      {json({
                        run_id: selected.run_id,
                        usage: selected.usage,
                        events,
                      })}
                    </pre>
                  </CollapsibleContent>
                </Collapsible>
              </>
            )
          )}
          {traceError && (
            <Alert variant="destructive">
              <AlertDescription>
                {t('monitoring.loadError')}
                <Button
                  variant="link"
                  onClick={() => setTraceRevision((value) => value + 1)}
                >
                  {t('common.retry')}
                </Button>
              </AlertDescription>
            </Alert>
          )}
        </section>
      </div>
    </div>
  );
}
