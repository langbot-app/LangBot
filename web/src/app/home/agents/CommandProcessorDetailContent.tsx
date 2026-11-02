import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import {
  Clock3,
  RefreshCw,
  SquareTerminal,
  Terminal,
  Trash2,
} from 'lucide-react';
import isEqual from 'lodash/isEqual';
import { toast } from 'sonner';
import type {
  Agent,
  CommandOutput,
  CommandProcessorDescriptor,
  ProcessorRun,
  ProcessorRunEvent,
} from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import EntityLoadState from '@/components/EntityLoadState';
import ProcessorDetailWorkbench from '@/app/home/components/processor-detail/ProcessorDetailWorkbench';
import EntityTitleEditButton from '@/app/home/components/entity-basic-info/EntityTitleEditButton';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { commandProcessorPluginId } from '@/app/home/bots/components/bot-form/PluginCommandBindings';
import RunnerSelect from './components/RunnerSelect';
import ProcessorRunList from './components/ProcessorRunList';
import CommandDebugPanel, {
  CommandOutputView,
} from './components/CommandDebugPanel';
import {
  formatRunDuration,
  processorRunDuration,
} from './components/processor-run-timing';

type CommandParameters = Record<string, Record<string, unknown>>;

function initialCommandConfig(agent: Agent): CommandParameters {
  const config = agent.config?.command_config;
  return config && typeof config === 'object'
    ? (config as CommandParameters)
    : {};
}

function schemaDefaults(component?: CommandProcessorDescriptor) {
  return Object.fromEntries(
    (component?.commands ?? []).map((command) => [
      command.name,
      Object.fromEntries(
        command.config_schema
          .filter((field) => field.default !== undefined)
          .map((field) => [field.name, field.default]),
      ),
    ]),
  ) as CommandParameters;
}

function runInputText(run: ProcessorRun) {
  const input = run.metadata.input_event as { text?: string } | undefined;
  return input?.text ?? run.metadata.command ?? '';
}

export default function CommandProcessorDetailContent({
  agent,
  id,
  canManage,
  canOperate,
  onDelete,
  onEdit,
  onSaved,
}: {
  agent: Agent;
  id: string;
  canManage: boolean;
  canOperate: boolean;
  onDelete: () => void;
  onEdit: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [components, setComponents] = useState<CommandProcessorDescriptor[]>(
    [],
  );
  const [pluginId, setPluginId] = useState(commandProcessorPluginId(agent));
  const [parameters, setParameters] = useState<CommandParameters>(
    initialCommandConfig(agent),
  );
  const [saved, setSaved] = useState({
    pluginId: commandProcessorPluginId(agent),
    parameters: initialCommandConfig(agent),
  });
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const validators = useRef<Record<string, () => Promise<boolean>>>({});

  const [runs, setRuns] = useState<ProcessorRun[]>([]);
  const [cursor, setCursor] = useState<number | null>(null);
  const [selected, setSelected] = useState<ProcessorRun | null>(null);
  const [events, setEvents] = useState<ProcessorRunEvent[]>([]);
  const requestVersion = useRef(0);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const metadata = await httpClient.getAgentMetadata();
      setComponents(metadata.command_processors ?? []);
      setLoaded(true);
    } catch {
      setFailed(true);
      return;
    }
    // Run history is secondary; its failure must not block configuration.
    try {
      const page = await httpClient.getProcessorRuns(id);
      setRuns(page.items ?? []);
      setCursor(page.has_more ? page.next_cursor : null);
    } catch {
      setRuns([]);
    }
  }, [id]);
  useEffect(() => {
    void load();
  }, [load]);

  const openRun = useCallback(
    async (run: ProcessorRun) => {
      const version = ++requestVersion.current;
      setSelected(run);
      setEvents([]);
      try {
        const page = await httpClient.getProcessorRunEvents(id, run.run_id);
        if (version !== requestVersion.current) return;
        setSelected(page.run);
        setEvents(page.items ?? []);
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

  const refreshRuns = useCallback(async () => {
    try {
      const page = await httpClient.getProcessorRuns(id);
      setRuns(page.items ?? []);
      setCursor(page.has_more ? page.next_cursor : null);
      if (page.items?.[0]) await openRun(page.items[0]);
    } catch {
      toast.error(t('agents.eventProcessor.loadError'));
    }
  }, [id, openRun, t]);

  async function loadMoreRuns() {
    if (cursor === null) return;
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
    }
  }

  const component = components.find((item) => item.plugin_id === pluginId);
  const available = Boolean(component);
  const dirty =
    pluginId !== saved.pluginId || !isEqual(parameters, saved.parameters);

  async function save() {
    if (!canManage || saving || !component) return false;
    for (const validate of Object.values(validators.current)) {
      if (!(await validate())) return false;
    }
    setSaving(true);
    try {
      await httpClient.updateAgent(id, {
        component_ref: component.id,
        config: {
          plugin: { id: component.plugin_id },
          command_config: parameters,
        },
      });
      toast.success(t('agents.saveSuccess'));
      setSaved({ pluginId, parameters });
      onSaved();
      return true;
    } catch {
      toast.error(t('agents.saveError'));
      return false;
    } finally {
      setSaving(false);
    }
  }

  function selectPlugin(value: string, next?: CommandProcessorDescriptor) {
    const descriptor =
      next ??
      components.find((item) => item.id === value || item.plugin_id === value);
    const nextPluginId = descriptor?.plugin_id ?? value.replace(/^plugin:/, '');
    setPluginId(nextPluginId);
    setParameters(schemaDefaults(descriptor));
    validators.current = {};
  }

  if (!loaded) return <EntityLoadState error={failed} onRetry={load} />;

  const options = components.map((item) => ({
    name: item.id,
    label: { en_US: item.plugin_id, zh_Hans: item.plugin_id },
  }));
  const selectedRef = pluginId ? `plugin:${pluginId}` : '';
  if (pluginId && !available)
    options.push({
      name: selectedRef,
      label: {
        en_US: t('agents.commandProcessor.unavailable'),
        zh_Hans: t('agents.commandProcessor.unavailable'),
      },
    });
  const outputs = events
    .filter((event) => event.type === 'command.output')
    .map((event) => event.data as CommandOutput);

  const logsContent = (
    <div className="flex h-full min-h-0 flex-col gap-4 p-4">
      <div className="flex shrink-0 items-center justify-between gap-2">
        <span className="text-sm font-medium">
          {t('agents.eventProcessor.runs')}{' '}
          <span className="text-muted-foreground">({runs.length})</span>
        </span>
        <Button
          variant="outline"
          size="sm"
          aria-label={t('agents.eventProcessor.refresh')}
          onClick={() => void refreshRuns()}
        >
          <RefreshCw className="size-4" />
          {t('agents.eventProcessor.refresh')}
        </Button>
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-6 lg:grid-cols-[18rem_minmax(0,1fr)]">
        {runs.length > 0 && (
          <ProcessorRunList
            className="max-h-64 overflow-y-auto rounded-lg border lg:max-h-none lg:h-full"
            runs={runs}
            selectedId={selected?.run_id}
            onSelect={(run) => void openRun(run)}
            runLabel={(run) => runInputText(run)}
            footer={
              cursor !== null ? (
                <Button
                  className="w-full"
                  variant="ghost"
                  onClick={() => void loadMoreRuns()}
                >
                  {t('agents.eventProcessor.loadMore')}
                </Button>
              ) : undefined
            }
          />
        )}
        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-4 pr-2">
            {!selected ? (
              <Alert>
                <AlertDescription>
                  {t('agents.commandProcessor.noRuns')}
                  <Button asChild variant="link" className="h-auto px-0">
                    <Link to="/home/bots">
                      {t('agents.commandProcessor.bindBot')}
                    </Link>
                  </Button>
                </AlertDescription>
              </Alert>
            ) : (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-3">
                  <div className="space-y-1.5">
                    <code className="text-sm font-medium">
                      {runInputText(selected)}
                    </code>
                    <p className="text-xs text-muted-foreground">
                      {new Date(selected.created_at * 1000).toLocaleString()}
                      {' · '}
                      {t(
                        selected.metadata.source === 'debug'
                          ? 'agents.commandProcessor.sourceDebug'
                          : 'agents.commandProcessor.sourcePlatform',
                      )}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {processorRunDuration(selected) !== null && (
                      <span className="flex items-center gap-1.5 text-xs tabular-nums text-muted-foreground">
                        <Clock3 className="size-3.5" />
                        {formatRunDuration(processorRunDuration(selected)!)}
                      </span>
                    )}
                    <Badge status={selected.status}>
                      {t(`agents.eventProcessor.status_${selected.status}`, {
                        defaultValue: selected.status,
                      })}
                    </Badge>
                  </div>
                </div>
                <section className="space-y-2">
                  <h3 className="text-sm font-medium">
                    {t('agents.commandProcessor.outputs')}
                  </h3>
                  {outputs.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      {t('agents.commandProcessor.noOutput')}
                    </p>
                  ) : (
                    outputs.map((output, index) => (
                      <div
                        key={index}
                        className="rounded-md border bg-muted/30 px-3 py-2"
                      >
                        <CommandOutputView output={output} />
                      </div>
                    ))
                  )}
                </section>
                {selected.status === 'failed' && selected.status_reason && (
                  <Alert variant="destructive">
                    <AlertDescription className="break-words">
                      {selected.status_reason}
                    </AlertDescription>
                  </Alert>
                )}
              </>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );

  return (
    <>
      <form
        id="command-processor-form"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      />
      <ProcessorDetailWorkbench
        title={`${agent.emoji || '⌨️'} ${agent.name}`}
        titleBadge={
          <Badge
            variant="outline"
            className="gap-1.5 border-sky-500/20 bg-sky-500/10 text-sky-700 dark:text-sky-300"
          >
            <SquareTerminal className="size-3.5" />
            {t('agents.commandProcessor.type')}
          </Badge>
        }
        titleAction={
          canManage ? <EntityTitleEditButton onClick={onEdit} /> : undefined
        }
        titleControls={
          <div className="w-[20rem] max-w-[calc(100vw-8rem)]">
            <RunnerSelect
              usage="command"
              options={options}
              value={selectedRef}
              label={t('agents.commandProcessor.plugin')}
              disabled={!canManage || saving}
              installScope={`command-processor:${id}`}
              onValueChange={(value) => selectPlugin(value)}
              onCommandProcessorInstalled={(installed) => {
                setComponents((current) => [
                  ...current.filter((item) => item.id !== installed.id),
                  installed,
                ]);
                selectPlugin(installed.id, installed);
              }}
            />
          </div>
        }
        status={
          pluginId && !available
            ? { label: t('agents.commandProcessor.unavailable'), tone: 'error' }
            : undefined
        }
        saveLabel={t('common.save')}
        saveFormId="command-processor-form"
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
        configTitle={t('agents.commandProcessor.type')}
        configIcon={
          <SquareTerminal className="size-4 text-sky-600 dark:text-sky-400" />
        }
        monitoring={{
          label: t('pipelines.monitoring.title'),
          workbenchLabel: t('pipelines.monitoring.workbench'),
          content: logsContent,
        }}
        configContent={
          <div className="h-full space-y-4 overflow-y-auto">
            <Alert>
              <AlertDescription className="text-xs">
                {t('agents.commandProcessor.notice')}{' '}
                <Button asChild variant="link" className="h-auto px-0 text-xs">
                  <Link to="/home/bots">
                    {t('agents.commandProcessor.bindBot')}
                  </Link>
                </Button>
              </AlertDescription>
            </Alert>
            {!component ? (
              <p className="text-sm text-muted-foreground">
                {t('agents.commandProcessor.selectPlugin')}
              </p>
            ) : (
              <fieldset disabled={!canManage || saving} className="space-y-4">
                {component.commands.map((command) => (
                  <section
                    key={command.name}
                    className="space-y-3 rounded-lg border p-4"
                  >
                    <div className="flex items-center gap-2">
                      <Terminal className="size-4 text-muted-foreground" />
                      <span className="font-mono text-sm font-medium">
                        {command.name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {extractI18nObject({
                          en_US: command.name,
                          zh_Hans: command.name,
                          ...command.label,
                        })}
                      </span>
                    </div>
                    {command.description && (
                      <p className="text-xs text-muted-foreground">
                        {extractI18nObject({
                          en_US: '',
                          zh_Hans: '',
                          ...command.description,
                        })}
                      </p>
                    )}
                    {command.config_schema.length === 0 ? (
                      <p className="text-xs text-muted-foreground">
                        {t('agents.commandProcessor.noSettings')}
                      </p>
                    ) : (
                      <DynamicFormComponent
                        key={`${pluginId}:${command.name}`}
                        itemConfigList={command.config_schema}
                        initialValues={parameters[command.name] ?? {}}
                        onSubmit={(values) =>
                          setParameters((current) => ({
                            ...current,
                            [command.name]: values as Record<string, unknown>,
                          }))
                        }
                        onValidate={(fn) => {
                          validators.current[command.name] = fn;
                        }}
                      />
                    )}
                  </section>
                ))}
              </fieldset>
            )}
          </div>
        }
        debugTitle={
          canOperate ? t('agents.commandProcessor.debugTitle') : undefined
        }
        debugDescription={t('agents.commandProcessor.debugNotice')}
        debugContent={
          canOperate ? (
            !component ? (
              <Alert className="m-3 w-auto">
                <AlertDescription>
                  {t('agents.commandProcessor.selectPlugin')}
                </AlertDescription>
              </Alert>
            ) : (
              <CommandDebugPanel
                key={component.id}
                processorId={id}
                component={component}
                hasUnsavedChanges={dirty}
                beforeRun={save}
                onRunFinished={() => void refreshRuns()}
              />
            )
          ) : undefined
        }
        unsavedLabel={t('pipelines.unsavedChanges')}
      />
    </>
  );
}
