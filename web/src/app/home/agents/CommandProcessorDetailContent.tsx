import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { SquareTerminal, Terminal, Trash2 } from 'lucide-react';
import isEqual from 'lodash/isEqual';
import { toast } from 'sonner';
import type {
  Agent,
  CommandProcessorDescriptor,
} from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import EntityLoadState from '@/components/EntityLoadState';
import ProcessorDetailWorkbench from '@/app/home/components/processor-detail/ProcessorDetailWorkbench';
import EntityTitleEditButton from '@/app/home/components/entity-basic-info/EntityTitleEditButton';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { commandProcessorPluginId } from '@/app/home/bots/components/bot-form/PluginCommandBindings';

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

export default function CommandProcessorDetailContent({
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

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const metadata = await httpClient.getAgentMetadata();
      setComponents(metadata.command_processors ?? []);
      setLoaded(true);
    } catch {
      setFailed(true);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const component = components.find((item) => item.plugin_id === pluginId);
  const available = Boolean(component);
  const dirty =
    pluginId !== saved.pluginId || !isEqual(parameters, saved.parameters);

  async function save() {
    if (!canManage || saving || !component) return;
    for (const validate of Object.values(validators.current)) {
      if (!(await validate())) return;
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
    } catch {
      toast.error(t('agents.saveError'));
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) return <EntityLoadState error={failed} onRetry={load} />;

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
            <Select
              value={pluginId}
              disabled={!canManage || saving}
              onValueChange={(value) => {
                const next = components.find(
                  (item) => item.plugin_id === value,
                );
                setPluginId(value);
                setParameters(schemaDefaults(next));
                validators.current = {};
              }}
            >
              <SelectTrigger aria-label={t('agents.commandProcessor.plugin')}>
                <SelectValue
                  placeholder={t('agents.commandProcessor.selectPlugin')}
                />
              </SelectTrigger>
              <SelectContent>
                {components.map((item) => (
                  <SelectItem key={item.plugin_id} value={item.plugin_id}>
                    {item.plugin_id}
                  </SelectItem>
                ))}
                {pluginId && !available && (
                  <SelectItem value={pluginId}>
                    {t('agents.commandProcessor.unavailable')}
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
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
                        {extractI18nObject(command.label)}
                      </span>
                    </div>
                    {command.description && (
                      <p className="text-xs text-muted-foreground">
                        {extractI18nObject(command.description)}
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
        unsavedLabel={t('pipelines.unsavedChanges')}
      />
    </>
  );
}
