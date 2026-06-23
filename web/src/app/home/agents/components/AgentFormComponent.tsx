import { useEffect, useMemo, useRef, useState } from 'react';
import type React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Brain, FileJson2, Info, Power, Trash2 } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Agent } from '@/app/infra/entities/api';
import {
  PipelineConfigStage,
  PipelineConfigTab,
} from '@/app/infra/entities/pipeline';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
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

interface AgentFormComponentProps {
  agentId: string;
  onFinish: () => void;
  onDeleted: () => void;
  onDirtyChange?: (dirty: boolean) => void;
}

interface SectionItem {
  label: string;
  name: 'basic' | 'runner' | 'events';
  icon: React.ElementType;
}

export default function AgentFormComponent({
  agentId,
  onFinish,
  onDeleted,
  onDirtyChange,
}: AgentFormComponentProps) {
  const { t } = useTranslation();
  const [activeSection, setActiveSection] =
    useState<SectionItem['name']>('basic');
  const [runnerConfigSchema, setRunnerConfigSchema] =
    useState<PipelineConfigTab | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

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
  const hasUnsavedChanges = useMemo(() => {
    if (!savedSnapshotRef.current) return false;
    return JSON.stringify(watchedValues) !== savedSnapshotRef.current;
  }, [watchedValues]);

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

  const sections: SectionItem[] = [
    { label: t('agents.basicInfo'), name: 'basic', icon: Info },
    { label: t('agents.runnerSettings'), name: 'runner', icon: Brain },
    { label: t('agents.eventCapability'), name: 'events', icon: FileJson2 },
  ];

  const currentRunner = (form.watch('runner') as Record<string, any>)?.id;

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

    httpClient
      .updateAgent(agentId, agent)
      .then(() => {
        const snapshotValues = form.getValues();
        savedSnapshotRef.current = JSON.stringify(snapshotValues);
        onFinish();
        toast.success(t('agents.saveSuccess'));
      })
      .catch((err) => {
        toast.error(t('agents.saveError') + err.msg);
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
            className="h-full flex flex-col flex-1 min-h-0 mb-2"
          >
            <div className="flex-1 flex flex-col md:flex-row min-h-0">
              <nav className="shrink-0 mb-4 md:mb-0 md:w-44 md:pr-4 md:mr-4 md:border-r overflow-x-auto md:overflow-x-visible md:overflow-y-auto">
                <ul className="flex md:flex-col gap-1 md:space-y-1">
                  {sections.map((section) => {
                    const Icon = section.icon;
                    return (
                      <li key={section.name}>
                        <button
                          type="button"
                          onClick={() => setActiveSection(section.name)}
                          className={cn(
                            'w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors text-left cursor-pointer whitespace-nowrap',
                            activeSection === section.name
                              ? 'bg-accent text-accent-foreground'
                              : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                          )}
                        >
                          <Icon className="size-4 shrink-0" />
                          {section.label}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </nav>

              <div className="flex-1 overflow-y-auto min-h-0">
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
                        <div className="flex gap-4 items-start">
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
                        <div className="flex items-center justify-between">
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
                            onClick={() => setShowDeleteConfirm(true)}
                          >
                            <Trash2 className="size-4 mr-1.5" />
                            {t('common.delete')}
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {activeSection === 'runner' && (
                  <div className="space-y-6">
                    {runnerConfigSchema?.stages.map((stage) =>
                      renderDynamicStage(stage),
                    )}
                    {!runnerConfigSchema && (
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
                      <CardTitle>{t('agents.eventCapability')}</CardTitle>
                      <CardDescription>
                        {t('agents.eventCapabilityDescription')}
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
