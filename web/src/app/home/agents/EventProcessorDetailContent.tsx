import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { FileCode2, RefreshCw, Settings2, Trash2, Pencil } from 'lucide-react';
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
import EventProcessorSettings from './components/EventProcessorSettings';

export default function EventProcessorDetailContent({
  agent,
  id,
  canManage,
  onDelete,
  onEdit,
  onSaved,
}: {
  agent: Agent;
  id: string;
  canManage: boolean;
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
  const [runs, setRuns] = useState<ProcessorRun[]>([]);
  const [cursor, setCursor] = useState<number | null>(null);
  const [selected, setSelected] = useState<ProcessorRun | null>(null);
  const [events, setEvents] = useState<ProcessorRunEvent[]>([]);
  const [eventCursor, setEventCursor] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pagingRuns, setPagingRuns] = useState(false);
  const [pagingEvents, setPagingEvents] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  const validate = useRef<(() => Promise<boolean>) | null>(null);
  const requestVersion = useRef(0);
  const available = components.some((item) => item.id === agent.component_ref);

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

  async function openRun(run: ProcessorRun) {
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
    if (!componentRef || !((await validate.current?.()) ?? true)) return;
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
      setConfigOpen(false);
      await load();
    } catch {
      toast.error(t('agents.saveError'));
    } finally {
      setSaving(false);
    }
  }

  function payload(value: unknown) {
    return (
      <pre className="mt-2 whitespace-pre-wrap break-all rounded-md bg-muted/50 p-3 text-xs">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <header className="flex flex-wrap items-center gap-3">
        <FileCode2 className="size-6" />
        <h1 className="text-2xl font-semibold">{agent.name}</h1>
        {canManage && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onEdit}
            aria-label={t('common.edit')}
          >
            <Pencil className="size-4" />
          </Button>
        )}
        <Badge variant="outline">{t('agents.eventProcessor.type')}</Badge>
        {!loading && !failed && !available && (
          <Badge variant="destructive">
            {t('agents.eventProcessor.unavailable')}
          </Badge>
        )}
        <div className="ml-auto flex gap-2">
          <Button
            variant="outline"
            onClick={() => {
              void load();
              if (selected) void openRun(selected);
            }}
            aria-label={t('agents.eventProcessor.refresh')}
          >
            <RefreshCw className="size-4" />
          </Button>
          {canManage && (
            <>
              <Button
                variant="outline"
                onClick={() => setConfigOpen(!configOpen)}
              >
                <Settings2 className="size-4" />
                {t('pipelines.configuration')}
              </Button>
              <Button variant="destructive" onClick={onDelete}>
                <Trash2 className="size-4" />
                {t('common.delete')}
              </Button>
            </>
          )}
        </div>
      </header>
      <p className="shrink-0 break-all text-xs text-muted-foreground">
        {agent.component_ref}
      </p>
      {configOpen && (
        <div className="max-h-[45vh] shrink-0 overflow-y-auto rounded-xl border p-4">
          <EventProcessorSettings
            components={components}
            value={componentRef}
            parameters={parameters}
            onChange={(value) => {
              setComponentRef(value);
              setParameters({});
              validate.current = null;
            }}
            onParametersChange={setParameters}
            onValidate={(fn) => {
              validate.current = fn;
            }}
          />
          <Button
            className="mt-4"
            disabled={
              saving || !components.some((item) => item.id === componentRef)
            }
            onClick={() => void save()}
          >
            {t('common.save')}
          </Button>
        </div>
      )}
      {failed && (
        <p role="alert" className="text-destructive">
          {t('agents.eventProcessor.loadError')}
        </p>
      )}
      <div className="grid min-h-0 flex-1 gap-4 md:grid-cols-[minmax(240px,0.7fr)_minmax(0,1.3fr)]">
        <section className="min-h-0 overflow-y-auto rounded-xl border p-4">
          <h2 className="mb-3 font-semibold">
            {t('agents.eventProcessor.runs')}
          </h2>
          {loading ? (
            <p>{t('common.loading')}</p>
          ) : runs.length === 0 && !failed ? (
            <div className="space-y-3 text-sm text-muted-foreground">
              <p>{t('agents.eventProcessor.noRuns')}</p>
              <Link className="text-primary underline" to="/home/bots">
                {t('agents.eventProcessor.bindBot')}
              </Link>
            </div>
          ) : (
            runs.map((run) => (
              <button
                key={run.run_id}
                onClick={() => void openRun(run)}
                className={`mb-2 block w-full rounded-lg border p-3 text-left text-sm ${selected?.run_id === run.run_id ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'}`}
              >
                <span className="block break-all font-medium">
                  {run.metadata.event_type}
                </span>
                <span className="mt-1 flex flex-wrap justify-between gap-1 text-xs text-muted-foreground">
                  <span>
                    {new Date(run.created_at * 1000).toLocaleString()}
                  </span>
                  <span>
                    {t(`agents.eventProcessor.status_${run.status}`, {
                      defaultValue: run.status,
                    })}
                  </span>
                </span>
              </button>
            ))
          )}
          {cursor !== null && (
            <Button
              variant="ghost"
              disabled={pagingRuns}
              onClick={() => void loadMoreRuns()}
            >
              {t('agents.eventProcessor.loadMore')}
            </Button>
          )}
        </section>
        <section className="min-h-0 overflow-y-auto rounded-xl border p-4">
          <h2 className="mb-3 font-semibold">
            {t('agents.eventProcessor.trace')}
          </h2>
          {!selected ? (
            <p className="text-sm text-muted-foreground">
              {t('agents.eventProcessor.selectRun')}
            </p>
          ) : (
            <div className="space-y-3">
              <details className="rounded-lg border p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  {t('agents.eventProcessor.input')}
                </summary>
                {payload(selected.metadata.input_event)}
              </details>
              {selected.metadata.delivery != null && (
                <details className="rounded-lg border p-3">
                  <summary className="cursor-pointer text-sm font-medium">
                    {t('agents.eventProcessor.destination')}
                  </summary>
                  {payload(selected.metadata.delivery)}
                </details>
              )}
              {events.map((event) =>
                event.type === 'processor.log' ? (
                  <div
                    key={event.sequence}
                    className="rounded-lg bg-muted/40 p-3 text-sm"
                  >
                    <span className="mr-2 text-xs text-muted-foreground">
                      {String(event.data.level)}
                    </span>
                    <span className="whitespace-pre-wrap break-words">
                      {String(event.data.text)}
                    </span>
                  </div>
                ) : (
                  <details
                    key={event.sequence}
                    className="rounded-lg border p-3"
                  >
                    <summary className="cursor-pointer break-all text-sm font-medium">
                      {t(
                        `agents.eventProcessor.trace_${event.type.replaceAll('.', '_')}`,
                        { defaultValue: event.type },
                      )}
                      {typeof event.data.tool_name === 'string' && (
                        <span className="ml-2 text-muted-foreground">
                          {toolLabels[event.data.tool_name] ||
                            event.data.tool_name}
                        </span>
                      )}
                    </summary>
                    {payload(event.data)}
                  </details>
                ),
              )}
              {selected.status === 'failed' && selected.status_reason && (
                <p className="break-words text-sm text-destructive">
                  {selected.status_reason}
                </p>
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
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
