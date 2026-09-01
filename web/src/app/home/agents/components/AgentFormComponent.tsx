import {
  forwardRef,
  type ForwardedRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Bot, Loader2, SlidersHorizontal, Zap } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Agent, ApiRespPluginSystemStatus } from '@/app/infra/entities/api';
import {
  PipelineConfigStage,
  PipelineConfigTab,
} from '@/app/infra/entities/pipeline';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import {
  getErrorMessage,
  readPendingAgentRunnerInstall,
  resumePendingAgentRunnerInstall,
  type InstalledAgentRunner,
} from '@/app/home/agents/agent-runner-marketplace';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Form,
  FormDescription,
  FormField,
  FormItem,
  FormMessage,
} from '@/components/ui/form';
import AgentEventPatternPicker from './AgentEventPatternPicker';
import AgentRunnerSelect from './AgentRunnerSelect';

export interface AgentRunnerStatus {
  label: string;
  description?: string;
  tone: 'neutral' | 'success' | 'warning' | 'error';
}

interface AgentFormComponentProps {
  agentId: string;
  availableEventTypes: string[];
  onFinish: (agent?: Partial<Agent>) => void;
  onDirtyChange?: (dirty: boolean) => void;
  onSavingChange?: (saving: boolean) => void;
  onRunnerStatusChange?: (status: AgentRunnerStatus) => void;
  onSupportedEventPatternsChange?: (patterns: string[]) => void;
}

export type AgentConfigSection = 'events' | 'runner' | 'runner_config';

export interface AgentFormHandle {
  openSection: (section: AgentConfigSection) => void;
  save: () => Promise<boolean>;
  syncBasicInfo: (values: {
    name: string;
    description: string;
    emoji?: string;
  }) => void;
}

function isRequiredRunnerValueMissing(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim() === '';
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object' && 'primary' in value) {
    return !String((value as { primary?: unknown }).primary || '').trim();
  }
  return false;
}

function isRunnerFieldVisible(
  field: PipelineConfigStage['config'][number],
  values: Record<string, unknown>,
) {
  if (!field.show_if || field.show_if.field.startsWith('__system.')) {
    return true;
  }
  const dependentValue = values[field.show_if.field];
  if (field.show_if.operator === 'eq') {
    return dependentValue === field.show_if.value;
  }
  if (field.show_if.operator === 'neq') {
    return dependentValue !== field.show_if.value;
  }
  return (
    Array.isArray(field.show_if.value) &&
    field.show_if.value.includes(dependentValue)
  );
}

function AgentFormComponent(
  {
    agentId,
    availableEventTypes,
    onFinish,
    onDirtyChange,
    onSavingChange,
    onRunnerStatusChange,
    onSupportedEventPatternsChange,
  }: AgentFormComponentProps,
  ref: ForwardedRef<AgentFormHandle>,
) {
  const { t } = useTranslation();
  const [runnerConfigSchema, setRunnerConfigSchema] =
    useState<PipelineConfigTab | null>(null);
  const [pluginSystemStatus, setPluginSystemStatus] =
    useState<ApiRespPluginSystemStatus | null>(null);
  const [pluginStatusLoading, setPluginStatusLoading] = useState(true);
  const [pluginStatusError, setPluginStatusError] = useState(false);
  const [initialDataLoaded, setInitialDataLoaded] = useState(false);
  const [runnerInstallRecovering, setRunnerInstallRecovering] = useState(false);
  const [activeSection, setActiveSection] =
    useState<AgentConfigSection>('runner');
  const isSavingRef = useRef(false);
  const hasUnsavedChangesRef = useRef(false);

  const formSchema = z.object({
    basic: z.object({
      name: z.string().min(1, { message: t('agents.nameRequired') }),
      description: z.string().optional(),
      emoji: z.string().optional(),
    }),
    runner: z.record(z.string(), z.any()),
    runner_config: z.record(z.string(), z.any()),
    supported_event_patterns: z.array(z.string()).min(1),
  });
  type FormValues = z.infer<typeof formSchema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      basic: {
        name: '',
        description: '',
        emoji: '🤖',
      },
      runner: {},
      runner_config: {},
      supported_event_patterns: ['*'],
    },
  });
  const runnerInstallScope = `agent:${agentId}`;

  const applyInstalledRunner = useCallback(
    (installed: InstalledAgentRunner) => {
      setRunnerConfigSchema(installed.configTab);
    },
    [],
  );

  const savedSnapshotRef = useRef('');
  const initializedStagesRef = useRef<Set<string>>(new Set());
  const watchedValues = form.watch();
  const hasUnsavedChanges = (() => {
    if (!savedSnapshotRef.current) return false;
    return JSON.stringify(watchedValues) !== savedSnapshotRef.current;
  })();
  hasUnsavedChangesRef.current = hasUnsavedChanges;

  useEffect(() => {
    onDirtyChange?.(hasUnsavedChanges);
  }, [hasUnsavedChanges, onDirtyChange]);

  const supportedEventPatterns = form.watch('supported_event_patterns');
  useEffect(() => {
    onSupportedEventPatternsChange?.(supportedEventPatterns);
  }, [onSupportedEventPatternsChange, supportedEventPatterns]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([httpClient.getAgentMetadata(), httpClient.getAgent(agentId)])
      .then(([metadata, resp]) => {
        if (cancelled) return;
        setRunnerConfigSchema(metadata.runner_config ?? null);
        const agent = resp.agent;
        const config = (agent.config ?? {}) as Record<string, any>;
        const loadedValues: FormValues = {
          basic: {
            name: agent.name ?? '',
            description: agent.description ?? '',
            emoji: agent.emoji || '🤖',
          },
          runner: (config.runner as Record<string, unknown>) ?? {},
          runner_config:
            (config.runner_config as Record<string, unknown>) ?? {},
          supported_event_patterns: agent.supported_event_patterns ??
            agent.capability?.supported_event_patterns ?? ['*'],
        };
        form.reset(loadedValues);
        savedSnapshotRef.current = JSON.stringify(loadedValues);
        initializedStagesRef.current.clear();
        setInitialDataLoaded(true);
      })
      .catch((err) => {
        toast.error(t('agents.loadError') + err.msg);
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, form, t]);

  useEffect(() => {
    if (
      !initialDataLoaded ||
      !readPendingAgentRunnerInstall(runnerInstallScope)
    ) {
      return;
    }
    let cancelled = false;
    setRunnerInstallRecovering(true);
    void resumePendingAgentRunnerInstall(runnerInstallScope)
      .then((installed) => {
        if (cancelled || !installed) return;
        applyInstalledRunner(installed);
        toast.success(
          t('agents.runnerInstallSuccess', {
            runner: extractI18nObject(installed.runner.label),
          }),
        );
      })
      .catch((error) => {
        if (!cancelled) {
          toast.error(
            getErrorMessage(error) || t('wizard.aiEngine.installFailed'),
          );
        }
      })
      .finally(() => {
        if (!cancelled) setRunnerInstallRecovering(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applyInstalledRunner, initialDataLoaded, runnerInstallScope, t]);

  const loadPluginSystemStatus = useCallback(async () => {
    setPluginStatusLoading(true);
    setPluginStatusError(false);
    try {
      setPluginSystemStatus(await httpClient.getPluginSystemStatus());
    } catch {
      setPluginSystemStatus(null);
      setPluginStatusError(true);
    } finally {
      setPluginStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPluginSystemStatus();
  }, [loadPluginSystemStatus]);

  const currentRunner = (form.watch('runner') as Record<string, any>)?.id;
  const runnerOptions = useMemo(() => {
    const runnerStage = runnerConfigSchema?.stages.find(
      (stage) => stage.name === 'runner',
    );
    return (
      runnerStage?.config.find((item) => item.name === 'id')?.options ?? []
    );
  }, [runnerConfigSchema]);
  const selectedRunnerOption = runnerOptions.find(
    (option) => option.name === currentRunner,
  );
  const runnerSelectorStage = runnerConfigSchema?.stages.find(
    (stage) => stage.name === 'runner',
  );
  const activeRunnerStage = runnerConfigSchema?.stages.find(
    (stage) => stage.name === currentRunner,
  );
  const runnerConfigValues = form.watch('runner_config') as Record<
    string,
    Record<string, unknown>
  >;
  const activeRunnerValues = useMemo(
    () => runnerConfigValues?.[currentRunner] ?? {},
    [currentRunner, runnerConfigValues],
  );
  const missingRunnerFields = useMemo(
    () =>
      (activeRunnerStage?.config ?? []).filter(
        (field) =>
          field.required &&
          isRunnerFieldVisible(field, activeRunnerValues) &&
          isRequiredRunnerValueMissing(activeRunnerValues[field.name]),
      ),
    [activeRunnerStage, activeRunnerValues],
  );
  const primarySections: Array<{
    name: AgentConfigSection;
    label: string;
    icon: React.ElementType;
  }> = [
    {
      name: 'runner',
      label: t('agents.runnerSettings'),
      icon: Bot,
    },
    {
      name: 'runner_config',
      label: selectedRunnerOption
        ? extractI18nObject(selectedRunnerOption.label)
        : t('pipelines.configuration'),
      icon: SlidersHorizontal,
    },
    {
      name: 'events',
      label: t('agents.bindableEvents'),
      icon: Zap,
    },
  ];

  const runnerStatus = useMemo<AgentRunnerStatus>(() => {
    if (pluginStatusLoading) {
      return {
        label: t('agents.runnerStatusLoading'),
        tone: 'neutral',
      };
    }

    if (pluginStatusError || !pluginSystemStatus) {
      return {
        label: t('agents.runnerStatusCheckFailed'),
        description: t('agents.runnerStatusCheckFailedDescription'),
        tone: 'error',
      };
    }

    if (!pluginSystemStatus.is_enable) {
      return {
        label: t('plugins.systemDisabled'),
        description: t('plugins.systemDisabledDesc'),
        tone: 'error',
      };
    }

    if (!pluginSystemStatus.is_connected) {
      return {
        label: t('plugins.connectionError'),
        description: t('plugins.connectionErrorDesc'),
        tone: 'error',
      };
    }

    if (runnerOptions.length === 0) {
      return {
        label: t('agents.noRunnersAvailable'),
        description: t('agents.noRunnersAvailableDescription'),
        tone: 'error',
      };
    }

    if (!currentRunner || !selectedRunnerOption) {
      return {
        label: t('agents.selectedRunnerUnavailable'),
        description: t('agents.selectedRunnerUnavailableDescription', {
          runner: currentRunner || t('agents.noRunnerSelected'),
        }),
        tone: 'warning',
      };
    }

    if (missingRunnerFields.length > 0) {
      return {
        label: t('agents.runnerConfigIncomplete'),
        description: t('agents.runnerConfigIncompleteDescription', {
          fields: missingRunnerFields
            .map((field) => extractI18nObject(field.label))
            .join(', '),
        }),
        tone: 'warning',
      };
    }

    return {
      label: t('agents.runnerReady'),
      description: t('agents.runnerReadyDescription', {
        runner: extractI18nObject(selectedRunnerOption.label),
      }),
      tone: 'success',
    };
  }, [
    currentRunner,
    pluginStatusError,
    pluginStatusLoading,
    pluginSystemStatus,
    runnerOptions.length,
    missingRunnerFields,
    selectedRunnerOption,
    t,
  ]);

  useEffect(() => {
    onRunnerStatusChange?.(runnerStatus);
  }, [onRunnerStatusChange, runnerStatus]);

  function updateSnapshotIfInitial(stageKey: string) {
    if (!initializedStagesRef.current.has(stageKey)) {
      initializedStagesRef.current.add(stageKey);
      if (!hasUnsavedChanges) {
        savedSnapshotRef.current = JSON.stringify(form.getValues());
      }
    }
  }

  function handleDynamicFormEmit(
    formName: 'runner' | 'runner_config',
    stageName: string,
    values: object,
  ) {
    if (formName === 'runner') {
      form.setValue('runner', values, { shouldDirty: true });
      updateSnapshotIfInitial(`runner.${stageName}`);
      return;
    }

    const currentRunnerConfigs =
      (form.getValues('runner_config') as Record<string, unknown>) || {};
    form.setValue(
      'runner_config',
      {
        ...currentRunnerConfigs,
        [stageName]: values,
      },
      { shouldDirty: true },
    );
    updateSnapshotIfInitial(`runner_config.${stageName}`);
  }

  function renderDynamicStage(stage: PipelineConfigStage) {
    const isRunnerSelector = stage.name === 'runner';
    if (!isRunnerSelector && stage.name !== currentRunner) return null;

    const initialValues = isRunnerSelector
      ? (form.watch('runner') as Record<string, unknown>) || {}
      : ((form.watch('runner_config') as Record<string, any>) || {})[
          stage.name
        ] || {};

    return (
      <Card key={stage.name}>
        <CardHeader>
          <CardTitle>{extractI18nObject(stage.label)}</CardTitle>
          {stage.description && (
            <CardDescription>
              {extractI18nObject(stage.description)}
            </CardDescription>
          )}
        </CardHeader>
        <CardContent className="space-y-6">
          <DynamicFormComponent
            itemConfigList={stage.config}
            initialValues={initialValues}
            renderItem={
              isRunnerSelector
                ? ({ config, field }) =>
                    config.name === 'id' ? (
                      <AgentRunnerSelect
                        options={config.options ?? []}
                        label={extractI18nObject(config.label)}
                        value={String(field.value ?? '')}
                        onValueChange={field.onChange}
                        installScope={runnerInstallScope}
                        onInstalled={applyInstalledRunner}
                      />
                    ) : undefined
                : undefined
            }
            onSubmit={(values) =>
              handleDynamicFormEmit(
                isRunnerSelector ? 'runner' : 'runner_config',
                stage.name,
                values,
              )
            }
          />
        </CardContent>
      </Card>
    );
  }

  const saveValues = useCallback(
    async (values: FormValues) => {
      if (isSavingRef.current) return false;
      const submittedSnapshot = JSON.stringify(values);
      const runner = values.runner || {};
      const agent: Partial<Agent> = {
        name: values.basic.name,
        description: values.basic.description ?? '',
        emoji: values.basic.emoji,
        component_ref: (runner.id as string) || null,
        supported_event_patterns: values.supported_event_patterns,
        config: {
          runner,
          runner_config: values.runner_config ?? {},
        },
      };

      isSavingRef.current = true;
      onSavingChange?.(true);
      try {
        await httpClient.updateAgent(agentId, agent);
        savedSnapshotRef.current = submittedSnapshot;
        onFinish(agent);
        toast.success(t('agents.saveSuccess'));
        return true;
      } catch (err) {
        const message =
          typeof err === 'object' && err && 'msg' in err
            ? String((err as { msg?: string }).msg || '')
            : '';
        toast.error(t('agents.saveError') + message);
        return false;
      } finally {
        isSavingRef.current = false;
        onSavingChange?.(false);
      }
    },
    [agentId, onFinish, onSavingChange, t],
  );

  function handleSubmit(values: FormValues) {
    void saveValues(values);
  }

  useImperativeHandle(
    ref,
    () => ({
      openSection: setActiveSection,
      syncBasicInfo(values) {
        form.setValue('basic', {
          ...form.getValues('basic'),
          name: values.name,
          description: values.description,
          emoji: values.emoji || '🤖',
        });
        if (savedSnapshotRef.current) {
          const snapshot = JSON.parse(savedSnapshotRef.current) as FormValues;
          snapshot.basic = {
            ...snapshot.basic,
            name: values.name,
            description: values.description,
            emoji: values.emoji || '🤖',
          };
          savedSnapshotRef.current = JSON.stringify(snapshot);
        }
      },
      async save() {
        if (!hasUnsavedChangesRef.current) return true;
        if (isSavingRef.current) return false;
        const valid = await form.trigger();
        if (!valid) return false;
        return (await saveValues(form.getValues())) ?? false;
      },
    }),
    [form, saveValues],
  );

  return (
    <div className="h-full p-0 flex flex-col">
      <Form {...form}>
        <form
          id="agent-form"
          onSubmit={form.handleSubmit(handleSubmit)}
          className="mb-2 flex h-full min-h-0 min-w-0 flex-1 flex-col"
        >
          <nav className="mb-4 shrink-0 space-y-2 border-b pb-4">
            <Tabs
              value={activeSection}
              onValueChange={(value) =>
                setActiveSection(value as AgentConfigSection)
              }
            >
              <div className="min-w-0">
                <TabsList className="grid h-auto w-full min-w-0 grid-cols-3">
                  {primarySections.map((section) => {
                    const Icon = section.icon;
                    return (
                      <TabsTrigger
                        key={section.name}
                        value={section.name}
                        className="min-w-0 gap-1.5 px-2"
                      >
                        <Icon className="size-4 shrink-0" />
                        <span className="truncate">{section.label}</span>
                      </TabsTrigger>
                    );
                  })}
                </TabsList>
              </div>
            </Tabs>
          </nav>

          <div className="min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden">
            <div className="mx-auto w-full min-w-0 max-w-5xl space-y-6 pb-8">
              {activeSection === 'runner' && (
                <div className="space-y-6">
                  {runnerSelectorStage
                    ? renderDynamicStage(runnerSelectorStage)
                    : !runnerConfigSchema && (
                        <Card>
                          <CardHeader>
                            <CardTitle>{t('agents.runnerSettings')}</CardTitle>
                            <CardDescription>
                              {t('agents.noRunnerMetadata')}
                            </CardDescription>
                          </CardHeader>
                        </Card>
                      )}
                </div>
              )}

              {activeSection === 'runner_config' && (
                <div className="space-y-6">
                  {runnerInstallRecovering ? (
                    <Card>
                      <CardHeader>
                        <CardTitle>{t('agents.runnerSettings')}</CardTitle>
                        <CardDescription className="flex items-center gap-2">
                          <Loader2 className="size-4 animate-spin" />
                          {t('agents.restoringRunnerInstall')}
                        </CardDescription>
                      </CardHeader>
                    </Card>
                  ) : activeRunnerStage ? (
                    renderDynamicStage(activeRunnerStage)
                  ) : (
                    <Card>
                      <CardHeader>
                        <CardTitle>{t('agents.runnerSettings')}</CardTitle>
                        <CardDescription>
                          {t('agents.noRunnerMetadata')}
                        </CardDescription>
                      </CardHeader>
                    </Card>
                  )}
                </div>
              )}

              {activeSection === 'events' && (
                <Card>
                  <CardHeader>
                    <CardTitle>{t('agents.bindableEvents')}</CardTitle>
                    <CardDescription>
                      {t('agents.bindableEventsDescription')}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <FormField
                      control={form.control}
                      name="supported_event_patterns"
                      render={({ field }) => (
                        <FormItem>
                          <AgentEventPatternPicker
                            events={availableEventTypes}
                            value={field.value}
                            onChange={field.onChange}
                          />
                          <FormDescription>
                            {t('agents.supportedEventsDescription')}
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </form>
      </Form>
    </div>
  );
}

export default forwardRef(AgentFormComponent);
