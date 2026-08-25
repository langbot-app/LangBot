import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Bot, Info, Power, SlidersHorizontal, Trash2, Zap } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Agent, ApiRespPluginSystemStatus } from '@/app/infra/entities/api';
import {
  PipelineConfigStage,
  PipelineConfigTab,
} from '@/app/infra/entities/pipeline';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import EmojiPicker from '@/components/ui/emoji-picker';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';

export interface AgentRunnerStatus {
  label: string;
  description?: string;
  tone: 'neutral' | 'success' | 'warning' | 'error';
}

interface AgentFormComponentProps {
  agentId: string;
  onFinish: () => void;
  onDeleted: () => void;
  onDirtyChange?: (dirty: boolean) => void;
  onSavingChange?: (saving: boolean) => void;
  onRunnerStatusChange?: (status: AgentRunnerStatus) => void;
}

type AgentConfigSection = 'events' | 'runner' | 'runner_config' | 'basic';

export default function AgentFormComponent({
  agentId,
  onFinish,
  onDeleted,
  onDirtyChange,
  onSavingChange,
  onRunnerStatusChange,
}: AgentFormComponentProps) {
  const { t } = useTranslation();
  const [runnerConfigSchema, setRunnerConfigSchema] =
    useState<PipelineConfigTab | null>(null);
  const [pluginSystemStatus, setPluginSystemStatus] =
    useState<ApiRespPluginSystemStatus | null>(null);
  const [pluginStatusLoading, setPluginStatusLoading] = useState(true);
  const [pluginStatusError, setPluginStatusError] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [activeSection, setActiveSection] =
    useState<AgentConfigSection>('basic');
  const isSavingRef = useRef(false);

  const formSchema = z.object({
    basic: z.object({
      name: z.string().min(1, { message: t('agents.nameRequired') }),
      description: z.string().optional(),
      emoji: z.string().optional(),
      enabled: z.boolean().optional(),
    }),
    runner: z.record(z.string(), z.any()),
    runner_config: z.record(z.string(), z.any()),
    supported_event_patterns_text: z.string(),
  });
  type FormValues = z.infer<typeof formSchema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      basic: {
        name: '',
        description: '',
        emoji: '🤖',
        enabled: true,
      },
      runner: {},
      runner_config: {},
      supported_event_patterns_text: '*',
    },
  });

  const savedSnapshotRef = useRef('');
  const initializedStagesRef = useRef<Set<string>>(new Set());
  const watchedValues = form.watch();
  const hasUnsavedChanges = (() => {
    if (!savedSnapshotRef.current) return false;
    return JSON.stringify(watchedValues) !== savedSnapshotRef.current;
  })();

  useEffect(() => {
    onDirtyChange?.(hasUnsavedChanges);
  }, [hasUnsavedChanges, onDirtyChange]);

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
            enabled: agent.enabled ?? true,
          },
          runner: (config.runner as Record<string, unknown>) ?? {},
          runner_config:
            (config.runner_config as Record<string, unknown>) ?? {},
          supported_event_patterns_text: (
            agent.supported_event_patterns ??
            agent.capability?.supported_event_patterns ?? ['*']
          ).join('\n'),
        };
        form.reset(loadedValues);
        savedSnapshotRef.current = JSON.stringify(loadedValues);
        initializedStagesRef.current.clear();
      })
      .catch((err) => {
        toast.error(t('agents.loadError') + err.msg);
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, form, t]);

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
  const primarySections: Array<{
    name: AgentConfigSection;
    label: string;
    icon: React.ElementType;
  }> = [
    {
      name: 'basic',
      label: t('agents.basicInfo'),
      icon: Info,
    },
    {
      name: 'events',
      label: t('agents.bindableEvents'),
      icon: Zap,
    },
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

  function normalizeEventPatterns(value: string): string[] {
    const patterns = value
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean);
    return patterns.length > 0 ? patterns : ['*'];
  }

  function handleSubmit(values: FormValues) {
    if (isSavingRef.current) return;
    const submittedSnapshot = JSON.stringify(values);
    const runner = values.runner || {};
    const agent: Partial<Agent> = {
      name: values.basic.name,
      description: values.basic.description ?? '',
      emoji: values.basic.emoji,
      enabled: values.basic.enabled ?? true,
      component_ref: (runner.id as string) || null,
      supported_event_patterns: normalizeEventPatterns(
        values.supported_event_patterns_text,
      ),
      config: {
        runner,
        runner_config: values.runner_config ?? {},
      },
    };

    isSavingRef.current = true;
    setIsSaving(true);
    onSavingChange?.(true);
    httpClient
      .updateAgent(agentId, agent)
      .then(() => {
        savedSnapshotRef.current = submittedSnapshot;
        onFinish();
        toast.success(t('agents.saveSuccess'));
      })
      .catch((err) => {
        toast.error(t('agents.saveError') + err.msg);
      })
      .finally(() => {
        isSavingRef.current = false;
        setIsSaving(false);
        onSavingChange?.(false);
      });
  }

  function confirmDelete() {
    httpClient
      .deleteAgent(agentId)
      .then(() => {
        toast.success(t('agents.deleteSuccess'));
        setShowDeleteConfirm(false);
        onDeleted();
      })
      .catch((err) => {
        toast.error(t('agents.deleteError') + err.msg);
      });
  }

  return (
    <>
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
                <div className="overflow-x-auto">
                  <TabsList className="grid min-w-[44rem] w-full grid-cols-4">
                    {primarySections.map((section) => {
                      const Icon = section.icon;
                      return (
                        <TabsTrigger key={section.name} value={section.name}>
                          <Icon />
                          {section.label}
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
                              <CardTitle>
                                {t('agents.runnerSettings')}
                              </CardTitle>
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
                    {activeRunnerStage ? (
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
                        name="supported_event_patterns_text"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>{t('agents.supportedEvents')}</FormLabel>
                            <FormControl>
                              <Textarea
                                {...field}
                                className="min-h-32 font-mono text-sm"
                                placeholder={'*\nmessage.received\ngroup.*'}
                              />
                            </FormControl>
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

                {activeSection === 'basic' && (
                  <div className="space-y-6">
                    <Card>
                      <CardHeader>
                        <CardTitle>{t('agents.basicInfo')}</CardTitle>
                        <CardDescription>
                          {t('agents.basicInfoDescription')}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="flex items-start gap-4">
                          <FormField
                            control={form.control}
                            name="basic.name"
                            render={({ field }) => (
                              <FormItem className="flex-1">
                                <FormLabel>
                                  {t('common.name')}
                                  <span className="text-destructive">*</span>
                                </FormLabel>
                                <FormControl>
                                  <Input {...field} value={field.value ?? ''} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name="basic.emoji"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>{t('common.icon')}</FormLabel>
                                <FormControl>
                                  <EmojiPicker
                                    value={field.value}
                                    onChange={field.onChange}
                                    ariaLabel={t('common.icon')}
                                  />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>

                        <FormField
                          control={form.control}
                          name="basic.description"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>{t('common.description')}</FormLabel>
                              <FormControl>
                                <Input {...field} value={field.value ?? ''} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />

                        <FormField
                          control={form.control}
                          name="basic.enabled"
                          render={({ field }) => (
                            <FormItem className="flex items-center justify-between rounded-lg border p-4">
                              <div className="space-y-0.5">
                                <FormLabel className="flex items-center gap-2">
                                  <Power className="size-4" />
                                  {t('agents.enabled')}
                                </FormLabel>
                                <FormDescription>
                                  {t('agents.enabledDescription')}
                                </FormDescription>
                              </div>
                              <FormControl>
                                <Switch
                                  checked={field.value ?? true}
                                  onCheckedChange={field.onChange}
                                />
                              </FormControl>
                            </FormItem>
                          )}
                        />
                      </CardContent>
                    </Card>

                    <Card className="border-destructive/50">
                      <CardHeader>
                        <CardTitle className="text-destructive">
                          {t('agents.dangerZone')}
                        </CardTitle>
                        <CardDescription>
                          {t('agents.dangerZoneDescription')}
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="flex items-center justify-between gap-4">
                          <div className="space-y-1">
                            <p className="text-sm font-medium">
                              {t('agents.deleteAgentAction')}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {t('agents.deleteAgentHint')}
                            </p>
                          </div>
                          <Button
                            type="button"
                            variant="destructive"
                            size="sm"
                            disabled={isSaving}
                            onClick={() => setShowDeleteConfirm(true)}
                          >
                            <Trash2 className="mr-1.5 size-4" />
                            {t('common.delete')}
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}
              </div>
            </div>
          </form>
        </Form>
      </div>

      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
          </DialogHeader>
          <div className="py-4">{t('agents.deleteConfirmation')}</div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteConfirm(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
