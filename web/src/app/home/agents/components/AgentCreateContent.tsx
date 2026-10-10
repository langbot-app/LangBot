import { useCallback, useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Bot, Workflow, Puzzle } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { AgentKind } from '@/app/infra/entities/api';
import { Button } from '@/components/ui/button';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import EmojiPicker from '@/components/ui/emoji-picker';
import ProcessorTypeDiagram from './ProcessorTypeDiagram';
import RunnerSelect from './RunnerSelect';
import type { GetAgentMetadataResponseData } from '@/app/infra/entities/api';
import { getDefaultValues } from '@/app/home/components/dynamic-form/DynamicFormItemConfig';
import { extractI18nObject } from '@/i18n/I18nProvider';

export default function AgentCreateContent({
  onCreated,
  allowedKinds,
  embedded = false,
}: {
  onCreated: (agentId: string) => void;
  allowedKinds?: AgentKind[];
  embedded?: boolean;
}) {
  const { t } = useTranslation();
  const [kind, setKind] = useState<AgentKind>(allowedKinds?.[0] ?? 'pipeline');
  const [metadata, setMetadata] = useState<GetAgentMetadataResponseData>();
  const [runner, setRunner] = useState('');
  const [loading, setLoading] = useState(true);
  const createdPipeline = useRef<string | null>(null);
  const loadMetadata = useCallback(async () => {
    setLoading(true);
    try { setMetadata(await httpClient.getAgentMetadata()); }
    catch { toast.error(t('agents.createError')); }
    finally { setLoading(false); }
  }, [t]);
  useEffect(() => { void loadMetadata(); }, [loadMetadata]);
  const runnerOptions = kind === 'event_processor'
    ? (metadata?.event_processors ?? []).map((item) => ({ name: item.id, label: { en_US: item.id, zh_Hans: item.id, ...item.label } }))
    : metadata?.runner_config?.stages.find((stage) => stage.name === 'runner')?.config.find((item) => item.name === 'id')?.options ?? [];
  const selectorLabel = t(kind === 'event_processor' ? 'agents.selectProcessorPlugin' : 'agents.selectAgentRunner');
  const formSchema = z.object({
    name: z.string().min(1, { message: t('agents.nameRequired') }),
    emoji: z.string().optional(),
  });
  type FormValues = z.infer<typeof formSchema>;
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      emoji: '⚙️',
    },
  });

  function selectRunner(value: string, name?: string) {
    setRunner(value);
    if (!form.getValues('name').trim()) {
      const option = runnerOptions.find((item) => item.name === value);
      const displayName = name || (option ? extractI18nObject(option.label) : '');
      if (displayName) {
        form.setValue('name', displayName, { shouldDirty: true, shouldValidate: true });
      }
    }
  }

  function handleKindChange(nextKind: AgentKind) {
    const previousDefaultEmoji =
      kind === 'pipeline' ? '⚙️' : kind === 'event_processor' ? '🧩' : '🤖';
    const nextDefaultEmoji =
      nextKind === 'pipeline'
        ? '⚙️'
        : nextKind === 'event_processor'
          ? '🧩'
          : '🤖';
    if ((kind === 'event_processor') !== (nextKind === 'event_processor')) {
      setRunner('');
    }
    setKind(nextKind);
    const currentEmoji = form.getValues('emoji');
    if (!currentEmoji || currentEmoji === previousDefaultEmoji) {
      form.setValue('emoji', nextDefaultEmoji);
    }
  }

  async function handleSubmit(values: FormValues) {
    if (!runner) { toast.error(selectorLabel); return; }
    const runnerStage = metadata?.runner_config?.stages.find((stage) => stage.name === runner);
    const parameters = runnerStage ? getDefaultValues(runnerStage.config) : {};
    const config = { runner: { id: runner }, runner_config: { [runner]: parameters } };
    try {
      if (kind === 'pipeline' && runnerStage?.config.some((field) => ['llm-model-selector', 'select-llm-model', 'model-fallback-selector'].includes(field.type))) {
        const { uuid } = await httpClient.getDefaultModel();
        if (uuid) {
          for (const field of runnerStage.config) {
            if (['llm-model-selector', 'select-llm-model'].includes(field.type) && !parameters[field.name]) parameters[field.name] = uuid;
            if (field.type === 'model-fallback-selector' && !parameters[field.name]?.primary) {
              parameters[field.name] = { ...parameters[field.name], primary: uuid, fallbacks: parameters[field.name]?.fallbacks ?? [] };
            }
          }
        }
      }
      if (kind === 'pipeline') {
        // Keep the created ID if configuration fails, so retry does not create duplicates.
        const uuid = createdPipeline.current ?? (await httpClient.createAgent({ kind, name: values.name, description: '', emoji: values.emoji })).uuid;
        createdPipeline.current = uuid;
        const { pipeline } = await httpClient.getPipeline(uuid);
        await httpClient.updatePipeline(uuid, {
          name: values.name, emoji: values.emoji,
          config: { ...pipeline.config, ai: { ...pipeline.config.ai, ...config } },
        });
        toast.success(t('agents.createSuccess'));
        onCreated(uuid);
      } else {
        const response = await httpClient.createAgent({
          kind, name: values.name, description: '', emoji: values.emoji,
          component_ref: runner, ...(kind === 'event_processor' ? {} : { config }),
        });
        toast.success(t('agents.createSuccess'));
        onCreated(response.uuid);
      }
    } catch (error) {
      toast.error(t('agents.createError') + String((error as { msg?: string }).msg ?? error));
    }
  }
  const typeOptions = [
    {
      kind: 'pipeline' as const,
      icon: Workflow,
      title: t('agents.pipelineType'),
      description: t('agents.pipelineTypeDescription'),
    },
    {
      kind: 'agent' as const,
      icon: Bot,
      title: t('agents.agentType'),
      description: t('agents.agentTypeDescription'),
    },
    {
      kind: 'event_processor' as const,
      icon: Puzzle,
      title: t('agents.eventProcessor.type'),
      description: t('agents.eventProcessor.description'),
    },
  ];
  return (
    <div className="flex h-full flex-col">
      <div className={embedded ? 'order-last flex justify-end border-t pt-4 shrink-0' : 'flex items-center justify-between pb-4 shrink-0'}>
        {!embedded && (
        <h1 className="text-xl font-semibold">
          {t('agents.eventProcessor.createPageTitle')}
        </h1>
        )}
        <Button
          type="submit"
          form="agent-create-form"
          disabled={form.formState.isSubmitting || loading || !runner}
        >
          {t('common.submit')}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="mx-auto max-w-6xl pb-6">
          <div className="grid items-stretch gap-5 lg:grid-cols-[minmax(340px,0.78fr)_minmax(0,1.22fr)]">
            <div className="space-y-5">
              <section
                aria-labelledby="processor-kind-heading"
                className="space-y-3"
              >
                <div>
                  <h2
                    id="processor-kind-heading"
                    className="text-base font-semibold"
                  >
                    {t('agents.chooseType')}
                  </h2>
                  {!embedded && <p className="mt-1 text-sm text-muted-foreground">
                    {t('agents.chooseTypeDescription')}
                  </p>}
                </div>

                <ToggleGroup
                  type="single"
                  value={kind}
                  onValueChange={(value) => {
                    if (value) handleKindChange(value as AgentKind);
                  }}
                  variant="outline"
                  spacing={3}
                  className="grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-1"
                >
                  {typeOptions.filter((option) => !allowedKinds || allowedKinds.includes(option.kind)).map((option) => {
                    const Icon = option.icon;
                    return (
                      <div key={option.kind} className="relative w-full">
                      <ToggleGroupItem
                        value={option.kind}
                        data-processor-kind={option.kind}
                        aria-label={`${option.title} ${option.description}`}
                        className="h-auto min-h-28 w-full items-start justify-start gap-3 rounded-lg border px-4 py-4 text-left whitespace-normal shadow-none hover:bg-muted/40 data-[state=on]:border-[#2288ee]/50 data-[state=on]:bg-blue-50/60 data-[state=on]:text-foreground data-[state=on]:shadow-none dark:data-[state=on]:border-blue-500/50 dark:data-[state=on]:bg-blue-500/10"
                      >
                        <span className="flex size-9 shrink-0 items-center justify-center rounded-md border bg-background text-[#2288ee] shadow-xs">
                          <Icon className="size-4" />
                        </span>
                        <span className="min-w-0 space-y-1.5">
                          <span className="block text-sm font-medium text-foreground">
                            {option.title}
                          </span>
                          <span className="block text-sm font-normal leading-relaxed text-muted-foreground">
                            {option.description}
                          </span>
                        </span>
                      </ToggleGroupItem>
                      </div>
                    );
                  })}
                </ToggleGroup>
              </section>

              <Card>
                <CardHeader>
                  <CardTitle>{t('agents.basicInfo')}</CardTitle>
                  <CardDescription>
                    {t('agents.createBasicInfoDescription')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Form {...form}>
                    <form
                      id="agent-create-form"
                      onSubmit={form.handleSubmit(handleSubmit)}
                      className="space-y-4"
                    >
                      <div className="space-y-2">
                        <p className="text-sm font-medium">{selectorLabel}</p>
                        <RunnerSelect
                          key={kind === 'event_processor' ? 'event' : 'agent'}
                          usage={kind === 'event_processor' ? 'event' : 'agent'}
                          options={runnerOptions}
                          label={selectorLabel}
                          value={runner}
                          onValueChange={selectRunner}
                          disabled={loading || form.formState.isSubmitting}
                          installScope={`processor-create-${kind === 'event_processor' ? 'event' : 'agent'}`}
                          onInstalled={(installed) => {
                            setMetadata((previous) => previous ? { ...previous, runner_config: installed.configTab } : previous);
                            selectRunner(installed.runner.name, extractI18nObject(installed.runner.label));
                          }}
                          onEventProcessorInstalled={(component) => {
                            setMetadata((previous) => previous ? { ...previous, event_processors: [...(previous.event_processors ?? []).filter((item) => item.id !== component.id), component] } : previous);
                            selectRunner(component.id, extractI18nObject({ en_US: component.id, zh_Hans: component.id, ...component.label }));
                          }}
                        />
                      </div>
                      <div className="flex gap-4 items-start">
                        <FormField
                          control={form.control}
                          name="name"
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
                          name="emoji"
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

                    </form>
                  </Form>

                </CardContent>
              </Card>
            </div>

            <Card className={embedded ? 'min-h-[360px] overflow-hidden py-0 dark:border-white/16 lg:min-h-[480px]' : 'min-h-[600px] overflow-hidden py-0 dark:border-white/16 lg:min-h-[680px]'}>
              <CardContent className="flex h-full items-center p-0">
                <ProcessorTypeDiagram kind={kind} />
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
