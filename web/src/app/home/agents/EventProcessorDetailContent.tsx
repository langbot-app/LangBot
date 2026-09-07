import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { eventPatternLabel } from '@/app/home/components/event-patterns/event-pattern-groups';
import { RefreshCw, Trash2, ScrollText } from 'lucide-react';
import isEqual from 'lodash/isEqual';
import { toast } from 'sonner';
import type {
  Agent,
  AgentPlatformTool,
  EventProcessorDescriptor,
  ProcessorRun,
  ProcessorRunEvent,
} from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Button } from '@/components/ui/button';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ScrollArea } from '@/components/ui/scroll-area';
import ProcessorDetailWorkbench from '@/app/home/components/processor-detail/ProcessorDetailWorkbench';
import EntityTitleEditButton from '@/app/home/components/entity-basic-info/EntityTitleEditButton';
import AgentDebugPanel from './components/AgentDebugPanel';
import EventProcessorTrace, {
  ProcessorPayload,
} from './components/EventProcessorTrace';
import ProcessorRunList from './components/ProcessorRunList';
import EventProcessorSettings from './components/EventProcessorSettings';

export default function EventProcessorDetailContent({
  agent,
  id,
  canManage,
  canOperate,
  availableEventTypes,
  onDelete,
  onEdit,
  onSaved,
}: {
  agent: Agent;
  id: string;
  canManage: boolean;
  canOperate: boolean;
  availableEventTypes: string[];
  onDelete: () => void;
  onEdit: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [platformTools, setPlatformTools] = useState<AgentPlatformTool[]>([]);
  const toolLabels = Object.fromEntries(
    platformTools.map((tool) => [tool.name, extractI18nObject(tool.label)]),
  );
  const [components, setComponents] = useState<EventProcessorDescriptor[]>([]);
  const [componentRef, setComponentRef] = useState(agent.component_ref ?? '');
  const initialParameters =
    (
      (agent.config?.runner_config ?? {}) as Record<
        string,
        Record<string, unknown>
      >
    )[agent.component_ref ?? ''] ?? {};
  const [parameters, setParameters] = useState(initialParameters);
  const [savedConfig, setSavedConfig] = useState({
    componentRef,
    parameters: initialParameters,
  });
  const dirty =
    componentRef !== savedConfig.componentRef ||
    !isEqual(parameters, savedConfig.parameters);
  const [runs, setRuns] = useState<ProcessorRun[]>([]);
  const [cursor, setCursor] = useState<number | null>(null);
  const [selected, setSelected] = useState<ProcessorRun | null>(null);
  const [events, setEvents] = useState<ProcessorRunEvent[]>([]);
  const [eventCursor, setEventCursor] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pagingRuns, setPagingRuns] = useState(false);
  const [pagingEvents, setPagingEvents] = useState(false);
  const [failed, setFailed] = useState(false);
  const validate = useRef<(() => Promise<boolean>) | null>(null);
  const requestVersion = useRef(0);
  const component = components.find((item) => item.id === componentRef);
  const available = Boolean(component);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const [metadata, page] = await Promise.all([
        httpClient.getAgentMetadata(),
        httpClient.getProcessorRuns(id),
      ]);
      setComponents(metadata.event_processors ?? []);
      setPlatformTools(metadata.platform_tools ?? []);
      setRuns(page.items);
      setCursor(page.has_more ? page.next_cursor : null);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [id]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(
    () => () => {
      requestVersion.current += 1;
    },
    [id],
  );

  const openRun = useCallback(
    async (run: ProcessorRun) => {
      const version = ++requestVersion.current;
      setSelected(run);
      setEvents([]);
      setEventCursor(null);
      try {
        const page = await httpClient.getProcessorRunEvents(id, run.run_id);
        if (version !== requestVersion.current) return;
        setSelected(page.run);
        setEvents(page.items);
        setEventCursor(page.has_more ? page.next_cursor : null);
      } catch {
        if (version === requestVersion.current)
          toast.error(t('agents.eventProcessor.loadError'));
      }
    },
    [id, t],
  );

  useEffect(() => {
    if (!selected && runs.length > 0) void openRun(runs[0]);
  }, [selected, runs, openRun]);

  async function refreshLatestRun() {
    try {
      const page = await httpClient.getProcessorRuns(id);
      setRuns(page.items);
      setCursor(page.has_more ? page.next_cursor : null);
      if (page.items[0]) await openRun(page.items[0]);
    } catch {
      toast.error(t('agents.eventProcessor.loadError'));
    }
  }

  async function loadMoreEvents() {
    if (!selected || eventCursor === null || pagingEvents) return;
    setPagingEvents(true);
    const runId = selected.run_id;
    const version = requestVersion.current;
    try {
      const page = await httpClient.getProcessorRunEvents(
        id,
        runId,
        eventCursor,
      );
      if (version !== requestVersion.current) return;
      setEvents((current) => [...current, ...page.items]);
      setEventCursor(page.has_more ? page.next_cursor : null);
    } catch {
      toast.error(t('agents.eventProcessor.loadError'));
    } finally {
      setPagingEvents(false);
    }
  }

  async function loadMoreRuns() {
    if (cursor === null || pagingRuns) return;
    setPagingRuns(true);
    try {
      const page = await httpClient.getProcessorRuns(id, cursor);
      setRuns((current) => [
        ...new Map(
          [...current, ...page.items].map((run) => [run.run_id, run]),
        ).values(),
      ]);
      setCursor(page.has_more ? page.next_cursor : null);
    } catch {
      toast.error(t('agents.eventProcessor.loadError'));
    } finally {
      setPagingRuns(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    let busy = false;
    const timer = window.setInterval(async () => {
      if (busy || document.hidden) return;
      busy = true;
      try {
        const page = await httpClient.getProcessorRuns(id);
        if (cancelled) return;
        setRuns((current) =>
          [
            ...new Map(
              [...current, ...page.items].map((run) => [run.run_id, run]),
            ).values(),
          ].sort((a, b) => b.created_at - a.created_at),
        );
        if (
          selected &&
          !['completed', 'failed', 'cancelled'].includes(selected.status) &&
          eventCursor === null
        ) {
          const trace = await httpClient.getProcessorRunEvents(
            id,
            selected.run_id,
            events.at(-1)?.sequence,
          );
          if (cancelled) return;
          setSelected(trace.run);
          setEvents((current) => [
            ...new Map(
              [...current, ...trace.items].map((event) => [
                event.sequence,
                event,
              ]),
            ).values(),
          ]);
          setEventCursor(trace.has_more ? trace.next_cursor : null);
        }
      } catch {
        /* Keep existing records visible across transient refresh failures. */
      } finally {
        busy = false;
      }
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [id, selected, eventCursor, events]);

  async function save() {
    if (
      !canManage ||
      saving ||
      !component ||
      !((await validate.current?.()) ?? true)
    )
      return false;
    setSaving(true);
    try {
      await httpClient.updateAgent(id, {
        component_ref: componentRef,
        config: {
          ...agent.config,
          runner: { id: componentRef },
          runner_config: { [componentRef]: parameters },
        },
      });
      toast.success(t('agents.saveSuccess'));
      onSaved();
      setSavedConfig({ componentRef, parameters });
      await load();
      return true;
    } catch {
      toast.error(t('agents.saveError'));
      return false;
    } finally {
      setSaving(false);
    }
  }

  return (
    <ProcessorDetailWorkbench
      title={`${agent.emoji || '⚡'} ${agent.name}`}
      titleAction={
        canManage ? <EntityTitleEditButton onClick={onEdit} /> : undefined
      }
      titleControls={
        <EventProcessorSettings
          components={components}
          value={componentRef}
          parameters={parameters}
          disabled={!canManage || saving || loading}
          onChange={(value) => {
            setComponentRef(value);
            const descriptor = components.find((item) => item.id === value);
            setParameters(
              Object.fromEntries(
                (descriptor?.config_schema ?? [])
                  .filter((field) => field.default !== undefined)
                  .map((field) => [field.name, field.default]),
              ),
            );
            validate.current = null;
          }}
          onParametersChange={setParameters}
          onValidate={(fn) => {
            validate.current = fn;
          }}
        />
      }
      status={
        !loading && componentRef && !available
          ? { label: t('agents.eventProcessor.unavailable'), tone: 'error' }
          : undefined
      }
      saveLabel={t('common.save')}
      saveFormId="event-processor-form"
      canSave={canManage && available}
      isDirty={dirty}
      isSaving={saving}
      headerActions={
        canManage ? (
          <Button variant="destructive" disabled={saving} onClick={onDelete}>
            <Trash2 className="size-4" />
            {t('common.delete')}
          </Button>
        ) : undefined
      }
      configTitle={t('agents.eventProcessor.trace')}
      configIcon={<ScrollText className="size-4" />}
      configContent={
        <div className="flex h-full min-h-0 flex-col gap-3">
          <form
            id="event-processor-form"
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          />
          {failed && (
            <Alert variant="destructive">
              <AlertDescription>
                {t('agents.eventProcessor.loadError')}
              </AlertDescription>
            </Alert>
          )}
          <div className="flex shrink-0 items-center justify-between gap-2">
            <span className="text-sm font-medium">
              {t('agents.eventProcessor.runs')}{' '}
              <span className="text-muted-foreground">({runs.length})</span>
            </span>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t('agents.eventProcessor.refresh')}
              onClick={() => void refreshLatestRun()}
            >
              <RefreshCw className="size-4" />
            </Button>
          </div>
          {runs.length > 0 && (
            <ProcessorRunList
              runs={runs}
              selectedId={selected?.run_id}
              onSelect={(run) => void openRun(run)}
              footer={
                cursor !== null ? (
                  <Button
                    className="w-full"
                    variant="ghost"
                    disabled={pagingRuns}
                    onClick={() => void loadMoreRuns()}
                  >
                    {t('agents.eventProcessor.loadMore')}
                  </Button>
                ) : undefined
              }
            />
          )}
          <ScrollArea className="min-h-0 flex-1">
            <div className="space-y-2 pr-3">
              {!selected ? (
                <Alert>
                  <AlertDescription>
                    {loading
                      ? t('common.loading')
                      : t('agents.eventProcessor.noRuns')}
                    <Button asChild variant="link" className="h-auto px-0">
                      <Link to="/home/bots">
                        {t('agents.eventProcessor.bindBot')}
                      </Link>
                    </Button>
                  </AlertDescription>
                </Alert>
              ) : (
                <>
                  <div className="border-b pb-2">
                    <p className="text-sm font-medium">
                      {eventPatternLabel(selected.metadata.event_type ?? '', t)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(selected.created_at * 1000).toLocaleString()}
                    </p>
                  </div>
                  <Badge
                    variant={
                      selected.status === 'failed' ? 'destructive' : 'outline'
                    }
                  >
                    {t(`agents.eventProcessor.status_${selected.status}`, {
                      defaultValue: selected.status,
                    })}
                  </Badge>
                  <ProcessorPayload
                    title={t('agents.eventProcessor.input')}
                    value={selected.metadata.input_event}
                  />
                  {selected.metadata.delivery != null && (
                    <ProcessorPayload
                      title={t('agents.eventProcessor.destination')}
                      value={selected.metadata.delivery}
                    />
                  )}
                  <EventProcessorTrace
                    events={events}
                    toolLabels={toolLabels}
                  />
                  {selected.status === 'failed' && selected.status_reason && (
                    <Alert variant="destructive">
                      <AlertDescription className="break-words">
                        {selected.status_reason}
                      </AlertDescription>
                    </Alert>
                  )}
                  {eventCursor !== null && (
                    <Button
                      variant="ghost"
                      disabled={pagingEvents}
                      onClick={() => void loadMoreEvents()}
                    >
                      {t('agents.eventProcessor.loadMore')}
                    </Button>
                  )}
                </>
              )}
            </div>
          </ScrollArea>
        </div>
      }
      debugTitle={canOperate ? t('agents.debugTab') : undefined}
      debugDescription={t('agents.eventProcessor.debugNotice')}
      debugContent={
        canOperate ? (
          !component ? (
            <Alert className="m-3 w-auto">
              <AlertDescription>
                {t('agents.eventProcessor.selectToDebug')}
              </AlertDescription>
            </Alert>
          ) : (
            <AgentDebugPanel
              agentId={id}
              processor
              platformTools={platformTools}
              hasUnsavedChanges={dirty}
              beforeRun={save}
              onRunFinished={() => {
                void refreshLatestRun();
              }}
              supportedEventPatterns={component.supported_event_patterns}
              availableEventTypes={availableEventTypes}
            />
          )
        ) : undefined
      }
      unsavedLabel={t('pipelines.unsavedChanges')}
    />
  );
}
