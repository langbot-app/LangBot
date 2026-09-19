import EntityLoadState from '@/components/EntityLoadState';
import { showBotError } from '../../bot-error';
import React, {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';
import i18n from 'i18next';
import { IChooseAdapterEntity } from '@/app/home/bots/components/bot-form/ChooseEntity';
import {
  DynamicFormItemConfig,
  getDefaultValues,
  parseDynamicFormItemType,
} from '@/app/home/components/dynamic-form/DynamicFormItemConfig';
import {
  DynamicFormItemType,
  IDynamicFormItemSchema,
} from '@/app/infra/entities/form/dynamic';
import { UUID } from 'uuidjs';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { httpClient } from '@/app/infra/http/HttpClient';
import { systemInfo } from '@/app/infra/http';
import { Agent, Bot } from '@/app/infra/entities/api';
import { getAdapterDocUrl } from '@/app/infra/entities/adapter-docs';
import {
  Cable,
  Check,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Webhook,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import EventBindingsEditor from './EventBindingsEditor';
import PluginProcessorBindings from './PluginProcessorBindings';

import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { CustomApiError } from '@/app/infra/entities/common';
import {
  groupByCategory,
  getCategoryLabel,
} from '@/app/infra/entities/adapter-categories';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import GuidedTour, {
  GuidedTourStep,
} from '@/app/home/components/guided-tour/GuidedTour';

type ConnectionMode = 'webhook' | 'persistent';

function supportsConnectionMode(
  config: IDynamicFormItemSchema[],
  mode: ConnectionMode,
) {
  const webhookField = config.find(
    (item) =>
      item.name === 'webhook_url' ||
      item.name === '__system.webhook_url' ||
      item.type === DynamicFormItemType.WEBHOOK_URL,
  );
  if (!webhookField) return mode === 'persistent';
  if (webhookField.show_if) return true;
  return mode === 'webhook';
}

function getSupportedConnectionModes(config: IDynamicFormItemSchema[]) {
  return (['webhook', 'persistent'] as const).filter((mode) =>
    supportsConnectionMode(config, mode),
  );
}

function conditionMatches(
  condition: NonNullable<IDynamicFormItemSchema['show_if']>,
  value: unknown,
) {
  if (condition.operator === 'eq') return value === condition.value;
  if (condition.operator === 'neq') return value !== condition.value;
  return Array.isArray(condition.value) && condition.value.includes(value);
}

function applyConnectionMode(
  config: IDynamicFormItemSchema[],
  values: Record<string, unknown>,
  mode: ConnectionMode,
) {
  const webhookField = config.find(
    (item) => item.type === DynamicFormItemType.WEBHOOK_URL,
  );
  const condition = webhookField?.show_if;
  if (!condition) return values;

  const controller = config.find((item) => item.name === condition.field);
  const candidates: unknown[] = [
    controller?.default,
    ...(controller?.options?.map((option) => option.name) ?? []),
    true,
    false,
    '',
  ];
  const shouldMatch = mode === 'webhook';
  const nextValue = candidates.find(
    (candidate) =>
      candidate !== undefined &&
      conditionMatches(condition, candidate) === shouldMatch,
  );
  if (nextValue === undefined) return values;
  return { ...values, [condition.field]: nextValue };
}

function detectConnectionMode(
  config: IDynamicFormItemSchema[],
  values: Record<string, unknown>,
): ConnectionMode {
  const webhookField = config.find(
    (item) => item.type === DynamicFormItemType.WEBHOOK_URL,
  );
  if (!webhookField) return 'persistent';
  if (!webhookField.show_if) return 'webhook';
  return conditionMatches(
    webhookField.show_if,
    values[webhookField.show_if.field],
  )
    ? 'webhook'
    : 'persistent';
}

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('bots.botNameRequired') }),
    description: z.string().optional(),
    adapter: z.string().min(1, { message: t('bots.adapterRequired') }),
    adapter_config: z.record(z.string(), z.any()),
    enable: z.boolean().optional(),
    plugin_processors: z
      .array(z.object({ processor_uuid: z.string(), enabled: z.boolean() }))
      .optional(),
    event_bindings: z
      .array(
        z.object({
          id: z.string().optional(),
          event_pattern: z.string(),
          target_type: z.enum([
            'agent',
            'pipeline',
            'event_processor',
            'discard',
          ]),
          target_uuid: z.string(),
          filters: z.array(z.record(z.string(), z.any())).optional(),
          priority: z.number(),
          enabled: z.boolean(),
          description: z.string().optional(),
          order: z.number().optional(),
        }),
      )
      .optional(),
  });

export interface BotFormHandle {
  syncBasicInfo: (values: { name: string; description: string }) => void;
}

interface BotFormProps {
  initBotId?: string;
  onFormSubmit: (value: z.infer<ReturnType<typeof getFormSchema>>) => void;
  onNewBotCreated: (botId: string) => void;
  onDirtyChange?: (dirty: boolean) => void;
  onAdapterLabelChange?: (label: string) => void;
  guideEnabled?: boolean;
}

const BotForm = forwardRef<BotFormHandle, BotFormProps>(function BotForm(
  {
    initBotId,
    onFormSubmit,
    onNewBotCreated,
    onDirtyChange,
    onAdapterLabelChange,
    guideEnabled = true,
  },
  ref,
) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: '',
      adapter: '',
      adapter_config: {},
      enable: true,
      event_bindings: [],
      plugin_processors: [],
    },
  });

  // Track whether initial data loading is complete.
  // setValue calls during init should NOT mark the form as dirty.
  const [loadFailed, setLoadFailed] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [initialDataLoaded, setInitialDataLoaded] = useState(false);
  const isInitializing = useRef(true);

  const [adapterNameToDynamicConfigMap, setAdapterNameToDynamicConfigMap] =
    useState(new Map<string, IDynamicFormItemSchema[]>());
  const [showDynamicForm, setShowDynamicForm] = useState<boolean>(false);
  const [adapterNameList, setAdapterNameList] = useState<
    IChooseAdapterEntity[]
  >([]);
  const [adapterDescriptionList, setAdapterDescriptionList] = useState<
    Record<string, string>
  >({});
  const [adapterHelpLinks, setAdapterHelpLinks] = useState<
    Record<string, Record<string, string>>
  >({});
  const [adapterSupportedEvents, setAdapterSupportedEvents] = useState<
    Record<string, string[]>
  >({});

  const [agentNameList, setAgentNameList] = useState<Agent[]>([]);

  const [dynamicFormConfigList, setDynamicFormConfigList] = useState<
    IDynamicFormItemSchema[]
  >([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [webhookUrl, setWebhookUrl] = useState<string>('');
  const [extraWebhookUrl, setExtraWebhookUrl] = useState<string>('');
  const [connectionMode, setConnectionMode] = useState<ConnectionMode | null>(
    null,
  );

  // Watch adapter and adapter_config for filtering
  const currentAdapter = form.watch('adapter');
  const adapterLabel =
    adapterNameList.find((adapter) => adapter.value === currentAdapter)
      ?.label ?? '';
  useEffect(() => {
    onAdapterLabelChange?.(adapterLabel);
  }, [adapterLabel, onAdapterLabelChange]);
  const currentAdapterConfig = form.watch('adapter_config');

  // Group adapters by category for the Select dropdown. Legacy adapters are
  // split out and shown in a collapsed group at the bottom so they're
  // de-emphasized but still usable for existing configurations.
  const activeAdapters = useMemo(
    () => adapterNameList.filter((a) => !a.legacy),
    [adapterNameList],
  );
  const legacyAdapters = useMemo(
    () => adapterNameList.filter((a) => a.legacy),
    [adapterNameList],
  );
  const groupedAdapters = useMemo(
    () => groupByCategory(activeAdapters),
    [activeAdapters],
  );

  // Whether the collapsed legacy adapter group is expanded in the Select.
  const [showLegacyAdapters, setShowLegacyAdapters] = useState(false);

  // Auto-expand the legacy group when the selected adapter is itself legacy,
  // so editing an existing bot on a legacy adapter still reveals the choice.
  useEffect(() => {
    if (
      currentAdapter &&
      legacyAdapters.some((a) => a.value === currentAdapter)
    ) {
      setShowLegacyAdapters(true);
    }
  }, [currentAdapter, legacyAdapters]);

  // Notify parent when dirty state changes
  const { isDirty } = form.formState;
  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  useImperativeHandle(ref, () => ({
    syncBasicInfo(values) {
      form.reset(
        {
          ...form.getValues(),
          name: values.name,
          description: values.description,
        },
        { keepDirtyValues: true },
      );
    },
  }));

  useEffect(() => {
    setBotFormValues();
  }, [initBotId, loadAttempt]);

  function setBotFormValues() {
    setInitialDataLoaded(false);
    setLoadFailed(false);
    isInitializing.current = true;
    initBotFormComponent()
      .then(() => {
        if (initBotId) {
          return getBotConfig(initBotId)
            .then((val) => {
              // Use form.reset() to set values AND update the dirty baseline,
              // so isDirty stays false after initial load.
              form.reset({
                name: val.name,
                description: val.description,
                adapter: val.adapter,
                adapter_config: val.adapter_config,
                enable: val.enable,
                event_bindings: val.event_bindings || [],
                plugin_processors: val.plugin_processors || [],
              });
              handleAdapterSelect(val.adapter, true);

              if (val.webhook_full_url) {
                setWebhookUrl(val.webhook_full_url);
              } else {
                setWebhookUrl('');
              }
              setExtraWebhookUrl(val.extra_webhook_full_url || '');
            })
            .catch((err) => {
              setLoadFailed(true);
              toast.error(
                t('bots.getBotConfigError') + (err as CustomApiError).msg,
              );
            })
            .finally(() => {
              isInitializing.current = false;
            });
        } else {
          form.reset();
          setWebhookUrl('');
          setExtraWebhookUrl('');
          isInitializing.current = false;
        }
      })
      .catch(() => setLoadFailed(true))
      .finally(() => setInitialDataLoaded(true));
  }

  async function initBotFormComponent() {
    const agentsRes = await httpClient.getAgents();
    setAgentNameList(agentsRes.agents);

    const adaptersRes = await httpClient.getAdapters();
    setAdapterNameList(
      adaptersRes.adapters.map((item) => {
        return {
          label: extractI18nObject(item.label),
          value: item.name,
          categories: item.spec.categories,
          legacy: item.spec.legacy,
        };
      }),
    );

    setAdapterDescriptionList(
      adaptersRes.adapters.reduce(
        (acc, item) => {
          acc[item.name] = extractI18nObject(item.description);
          return acc;
        },
        {} as Record<string, string>,
      ),
    );

    setAdapterHelpLinks(
      adaptersRes.adapters.reduce(
        (acc, item) => {
          if (item.spec.help_links) {
            acc[item.name] = item.spec.help_links;
          }
          return acc;
        },
        {} as Record<string, Record<string, string>>,
      ),
    );

    setAdapterSupportedEvents(
      adaptersRes.adapters.reduce(
        (acc, item) => {
          acc[item.name] = item.spec.supported_events || [];
          return acc;
        },
        {} as Record<string, string[]>,
      ),
    );

    adaptersRes.adapters.forEach((rawAdapter) => {
      adapterNameToDynamicConfigMap.set(
        rawAdapter.name,
        rawAdapter.spec.config.map(
          (item) =>
            new DynamicFormItemConfig({
              default: item.default,
              id: UUID.generate(),
              label: item.label,
              description: item.description,
              name: item.name,
              required: item.required,
              type: parseDynamicFormItemType(item.type),
              options: item.options,
              show_if: item.show_if,
              login_platform: item.login_platform,
              url: item.url,
              download_filename: item.download_filename,
              help_links: item.help_links,
              help_label: item.help_label,
            }),
        ),
      );
    });
    setAdapterNameToDynamicConfigMap(adapterNameToDynamicConfigMap);
  }

  async function getBotConfig(botId: string): Promise<
    z.infer<typeof formSchema> & {
      webhook_full_url?: string;
      extra_webhook_full_url?: string;
    }
  > {
    return new Promise((resolve, reject) => {
      httpClient
        .getBot(botId)
        .then((res) => {
          const bot = res.bot;
          const runtimeValues = bot.adapter_runtime_values as
            | Record<string, unknown>
            | undefined;
          resolve({
            adapter: bot.adapter,
            description: bot.description,
            name: bot.name,
            adapter_config: bot.adapter_config,
            enable: bot.enable ?? true,
            event_bindings: bot.event_bindings ?? [],
            plugin_processors: bot.plugin_processors ?? [],
            webhook_full_url: runtimeValues?.webhook_full_url as
              | string
              | undefined,
            extra_webhook_full_url: runtimeValues?.extra_webhook_full_url as
              | string
              | undefined,
          });
        })
        .catch((err) => {
          reject(err);
        });
    });
  }

  function handleAdapterSelect(adapterName: string, preserveConfig = false) {
    if (adapterName) {
      const adapterConfig = adapterNameToDynamicConfigMap.get(adapterName);
      if (adapterConfig) {
        setDynamicFormConfigList(adapterConfig);
        if (!preserveConfig) {
          const defaultValues = getDefaultValues(adapterConfig);
          const supportedModes = getSupportedConnectionModes(adapterConfig);
          const nextMode =
            supportedModes.length === 1 ? supportedModes[0] : null;
          setConnectionMode(nextMode);
          form.setValue(
            'adapter_config',
            nextMode
              ? applyConnectionMode(adapterConfig, defaultValues, nextMode)
              : defaultValues,
          );
        } else {
          setConnectionMode(
            detectConnectionMode(
              adapterConfig,
              form.getValues('adapter_config') || {},
            ),
          );
        }
      }
      setShowDynamicForm(true);
    } else {
      setConnectionMode(null);
      setShowDynamicForm(false);
    }
  }

  function selectAdapter(adapterName: string) {
    form.setValue('adapter', adapterName, {
      shouldDirty: !isInitializing.current,
      shouldValidate: true,
    });
    handleAdapterSelect(adapterName, false);
  }

  function handleConnectionModeChange(mode: ConnectionMode) {
    if (!currentAdapter) return;
    const adapterConfig =
      adapterNameToDynamicConfigMap.get(currentAdapter) ?? [];
    if (!supportsConnectionMode(adapterConfig, mode)) return;
    setConnectionMode(mode);
    form.setValue(
      'adapter_config',
      applyConnectionMode(adapterConfig, currentAdapterConfig, mode),
      { shouldDirty: true },
    );
  }

  const supportedConnectionModes = useMemo(
    () =>
      currentAdapter
        ? getSupportedConnectionModes(
            adapterNameToDynamicConfigMap.get(currentAdapter) ?? [],
          )
        : [],
    [adapterNameToDynamicConfigMap, currentAdapter],
  );

  const botGuideSteps = useMemo<GuidedTourStep[]>(() => {
    const steps: GuidedTourStep[] = [];

    if (supportedConnectionModes.length > 1) {
      steps.push({
        id: 'connection',
        target: '[data-guide="bot-connection-mode"]',
        title: t('guidedTour.bot.connection.title'),
        description: t('guidedTour.bot.connection.description'),
      });
    }

    if (dynamicFormConfigList.length > 0) {
      const docsUrl = getAdapterDocUrl(
        currentAdapter ? adapterHelpLinks[currentAdapter] : undefined,
        i18n.language,
      );
      steps.push({
        id: 'parameters',
        target: '[data-guide="bot-adapter-parameters"]',
        title: t('guidedTour.bot.parameters.title'),
        description: t('guidedTour.bot.parameters.description'),
        action: docsUrl
          ? {
              href: docsUrl,
              label: t('guidedTour.bot.parameters.action'),
            }
          : undefined,
      });
    }

    steps.push({
      id: 'routing',
      target: '[data-guide="bot-routing"]',
      title: t('guidedTour.bot.routing.title'),
      description: t('guidedTour.bot.routing.description'),
    });
    steps.push({
      id: 'save',
      target: '[data-guide="bot-config-save"]',
      title: t('guidedTour.bot.save.title'),
      description: t('guidedTour.bot.save.description'),
    });
    return steps;
  }, [
    adapterHelpLinks,
    currentAdapter,
    dynamicFormConfigList,
    supportedConnectionModes.length,
    t,
  ]);

  async function createDraft() {
    if (initBotId || !currentAdapter) return;
    setIsLoading(true);
    const newBot: Bot = {
      name: form.getValues('name'),
      description: form.getValues('description') ?? '',
      adapter: currentAdapter,
      adapter_config: form.getValues('adapter_config') || {},
      enable: false,
      event_bindings: [],
      plugin_processors: [],
    };

    try {
      const res = await httpClient.createBot(newBot);
      toast.success(t('bots.createSuccess'));
      onNewBotCreated(res.uuid);
    } catch (error) {
      const err = error as CustomApiError & {
        code?: string;
        data?: { uuid?: string };
      };
      showBotError(err, t('bots.createError'), t);
      if (err.code === 'bot_apply_failed' && err.data?.uuid) {
        onNewBotCreated(err.data.uuid);
        return;
      }
      throw error;
    } finally {
      setIsLoading(false);
    }
  }

  function onDynamicFormSubmit() {
    if (!initBotId) {
      void createDraft();
      return;
    }
    setIsLoading(true);
    const updateBot: Bot = {
      uuid: initBotId,
      name: form.getValues().name,
      description: form.getValues().description ?? '',
      adapter: form.getValues().adapter,
      adapter_config: form.getValues().adapter_config,
      enable: form.getValues().enable,
      event_bindings: form.getValues().event_bindings ?? [],
      plugin_processors: form.getValues().plugin_processors ?? [],
    };
    httpClient
      .updateBot(initBotId, updateBot)
      .then(() => {
        // Reset dirty baseline to current values so isDirty becomes false
        form.reset(form.getValues());
        onFormSubmit(form.getValues());
        toast.success(t('bots.saveSuccess'));
      })
      .catch((err) => {
        showBotError(err, t('bots.saveError'), t);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }

  if (loadFailed)
    return (
      <EntityLoadState error onRetry={() => setLoadAttempt((n) => n + 1)} />
    );
  if (!initialDataLoaded) return <EntityLoadState />;

  return (
    <Form {...form}>
      <form
        id="bot-form"
        onSubmit={form.handleSubmit(onDynamicFormSubmit)}
        aria-busy={isLoading}
        className={cn('w-full min-w-0 max-w-full', initBotId && 'lg:h-full')}
      >
        <fieldset
          className={cn(
            'w-full min-w-0 max-w-full',
            initBotId
              ? 'grid gap-4 lg:h-full lg:min-h-0 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:grid-rows-[minmax(0,1fr)]'
              : 'grid items-start gap-6 lg:grid-cols-[minmax(16rem,0.7fr)_minmax(0,2fr)]',
          )}
          disabled={isLoading}
        >
          {/* Create: basic information and adapter selection */}
          {!initBotId ? (
            <>
              <Card data-guide="bot-basic" className="lg:sticky lg:top-0">
                <CardHeader>
                  <CardTitle>{t('bots.basicInfo')}</CardTitle>
                  <CardDescription>
                    {t('bots.basicInfoDescription')}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          {t('bots.botName')}
                          <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="description"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('bots.botDescription')}</FormLabel>
                        <FormControl>
                          <Input {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              <section
                data-guide="bot-adapter"
                data-testid="adapter-gallery"
                className="min-w-0 space-y-8 py-2"
              >
                <div className="max-w-2xl">
                  <h2 className="text-xl font-semibold">
                    {t('guidedTour.bot.adapter.title')}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {t('guidedTour.bot.adapter.description')}
                  </p>
                </div>

                <div className="space-y-8">
                  {groupedAdapters.map((group) => (
                    <section
                      key={group.categoryId ?? 'uncategorized'}
                      data-adapter-category={
                        group.categoryId ?? 'uncategorized'
                      }
                      className="space-y-3"
                    >
                      <div className="flex items-center gap-3">
                        <h3 className="text-sm font-semibold">
                          {group.categoryId
                            ? getCategoryLabel(t, group.categoryId)
                            : t('bots.selectAdapter')}
                        </h3>
                        <span className="text-xs tabular-nums text-muted-foreground">
                          {group.items.length}
                        </span>
                      </div>
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {group.items.map((item) => (
                          <button
                            key={`${group.categoryId ?? 'uncategorized'}:${item.value}`}
                            type="button"
                            onClick={() => selectAdapter(item.value)}
                            aria-pressed={currentAdapter === item.value}
                            className={cn(
                              'group flex min-h-28 min-w-0 items-center gap-4 rounded-lg border bg-background p-4 text-left shadow-xs transition-colors hover:border-primary/50 hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                              currentAdapter === item.value &&
                                'border-primary bg-primary/5 ring-1 ring-primary',
                            )}
                          >
                            <img
                              src={httpClient.getAdapterIconURL(item.value)}
                              alt=""
                              className="size-11 shrink-0 rounded-md border bg-background object-contain p-1"
                            />
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-sm font-medium">
                                {item.label}
                              </span>
                              <span className="mt-1 line-clamp-2 block text-xs leading-5 text-muted-foreground">
                                {adapterDescriptionList[item.value]}
                              </span>
                            </span>
                            {currentAdapter === item.value ? (
                              <Check className="size-4 shrink-0 text-primary" />
                            ) : (
                              <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                            )}
                          </button>
                        ))}
                      </div>
                    </section>
                  ))}

                  {legacyAdapters.length > 0 && (
                    <section
                      className="border-t pt-5"
                      data-adapter-category="legacy"
                    >
                      <button
                        type="button"
                        onClick={() => setShowLegacyAdapters((value) => !value)}
                        className="flex w-full items-center gap-2 py-2 text-left text-sm font-medium text-muted-foreground hover:text-foreground"
                        aria-expanded={showLegacyAdapters}
                      >
                        {showLegacyAdapters ? (
                          <ChevronDown className="size-4" />
                        ) : (
                          <ChevronRight className="size-4" />
                        )}
                        {t('bots.legacyAdapters')}
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
                          {legacyAdapters.length}
                        </span>
                      </button>
                      {showLegacyAdapters && (
                        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                          {legacyAdapters.map((item) => (
                            <button
                              key={`legacy:${item.value}`}
                              type="button"
                              onClick={() => selectAdapter(item.value)}
                              aria-pressed={currentAdapter === item.value}
                              className={cn(
                                'group flex min-h-28 min-w-0 items-center gap-4 rounded-lg border bg-background p-4 text-left opacity-75 transition-colors hover:border-primary/50 hover:bg-accent/40 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                                currentAdapter === item.value &&
                                  'border-primary bg-primary/5 opacity-100 ring-1 ring-primary',
                              )}
                            >
                              <img
                                src={httpClient.getAdapterIconURL(item.value)}
                                alt=""
                                className="size-11 shrink-0 rounded-md border bg-background object-contain p-1 grayscale"
                              />
                              <span className="min-w-0 flex-1">
                                <span className="flex min-w-0 items-center gap-2">
                                  <span className="truncate text-sm font-medium">
                                    {item.label}
                                  </span>
                                  <span className="shrink-0 rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300">
                                    {t('bots.legacyAdapterBadge')}
                                  </span>
                                </span>
                                <span className="mt-1 line-clamp-2 block text-xs leading-5 text-muted-foreground">
                                  {adapterDescriptionList[item.value]}
                                </span>
                              </span>
                              {currentAdapter === item.value ? (
                                <Check className="size-4 shrink-0 text-primary" />
                              ) : (
                                <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                              )}
                            </button>
                          ))}
                        </div>
                      )}
                    </section>
                  )}
                </div>
              </section>
            </>
          ) : (
            <Card
              className={cn(
                'min-w-0',
                initBotId && 'lg:min-h-0 lg:overflow-hidden',
              )}
            >
              <CardHeader>
                <CardTitle>{t('bots.adapterConfig')}</CardTitle>
                <CardDescription>
                  {t('bots.adapterConfigDescription')}
                </CardDescription>
              </CardHeader>
              <CardContent
                className={cn(
                  'min-w-0 space-y-4',
                  initBotId && 'lg:min-h-0 lg:flex-1 lg:overflow-y-auto',
                )}
              >
                <div data-guide="bot-adapter">
                  <FormField
                    control={form.control}
                    name="adapter"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          {t('bots.platformAdapter')}
                          <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <div className="flex flex-wrap items-center gap-2">
                            <Select
                              onValueChange={(value) => {
                                selectAdapter(value);
                              }}
                              value={field.value}
                            >
                              <SelectTrigger className="w-full min-w-0 overflow-hidden sm:w-[240px]">
                                {field.value ? (
                                  <div className="flex min-w-0 items-center gap-2">
                                    <img
                                      src={httpClient.getAdapterIconURL(
                                        field.value,
                                      )}
                                      alt=""
                                      className="h-5 w-5 shrink-0 rounded"
                                    />
                                    {(() => {
                                      const selectedAdapter =
                                        adapterNameList.find(
                                          (a) => a.value === field.value,
                                        );

                                      return (
                                        <>
                                          <span className="min-w-0 truncate">
                                            {selectedAdapter?.label ??
                                              field.value}
                                          </span>
                                          {selectedAdapter?.legacy && (
                                            <span className="shrink-0 rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300">
                                              {t('bots.legacyAdapterBadge')}
                                            </span>
                                          )}
                                        </>
                                      );
                                    })()}
                                  </div>
                                ) : (
                                  <SelectValue
                                    placeholder={t('bots.selectAdapter')}
                                  />
                                )}
                              </SelectTrigger>
                              <SelectContent className="z-[70]">
                                {groupedAdapters.map((group) => (
                                  <SelectGroup
                                    key={group.categoryId ?? 'uncategorized'}
                                  >
                                    {group.categoryId && (
                                      <SelectLabel>
                                        {getCategoryLabel(t, group.categoryId)}
                                      </SelectLabel>
                                    )}
                                    {group.items.map((item) => (
                                      <SelectItem
                                        key={`${group.categoryId ?? 'uncategorized'}:${item.value}`}
                                        value={item.value}
                                      >
                                        <div className="flex min-w-0 w-full items-center gap-2">
                                          <img
                                            src={httpClient.getAdapterIconURL(
                                              item.value,
                                            )}
                                            alt=""
                                            className="h-5 w-5 shrink-0 rounded"
                                          />
                                          <span className="min-w-0 truncate">
                                            {item.label}
                                          </span>
                                        </div>
                                      </SelectItem>
                                    ))}
                                  </SelectGroup>
                                ))}
                                {legacyAdapters.length > 0 && (
                                  <>
                                    <div
                                      role="button"
                                      tabIndex={0}
                                      onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        setShowLegacyAdapters((v) => !v);
                                      }}
                                      onKeyDown={(e) => {
                                        if (
                                          e.key === 'Enter' ||
                                          e.key === ' '
                                        ) {
                                          e.preventDefault();
                                          setShowLegacyAdapters((v) => !v);
                                        }
                                      }}
                                      className="flex cursor-pointer items-center gap-1 px-2 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground border-t mt-1 pt-2"
                                    >
                                      {showLegacyAdapters ? (
                                        <ChevronDown className="h-3.5 w-3.5" />
                                      ) : (
                                        <ChevronRight className="h-3.5 w-3.5" />
                                      )}
                                      {t('bots.legacyAdapters')}
                                      <span className="ml-1 rounded bg-muted px-1.5 py-0.5 text-[10px]">
                                        {legacyAdapters.length}
                                      </span>
                                    </div>
                                    {showLegacyAdapters && (
                                      <>
                                        <p className="whitespace-pre-line px-2 pb-1 text-[11px] leading-snug text-muted-foreground">
                                          {t('bots.legacyAdaptersHint')}
                                        </p>
                                        <SelectGroup>
                                          {legacyAdapters.map((item) => (
                                            <SelectItem
                                              key={`legacy:${item.value}`}
                                              value={item.value}
                                            >
                                              <div className="flex min-w-0 w-full items-center gap-2 opacity-70">
                                                <img
                                                  src={httpClient.getAdapterIconURL(
                                                    item.value,
                                                  )}
                                                  alt=""
                                                  className="h-5 w-5 shrink-0 rounded grayscale"
                                                />
                                                <span className="min-w-0 truncate">
                                                  {item.label}
                                                </span>
                                                <span className="ml-auto shrink-0 rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300">
                                                  {t('bots.legacyAdapterBadge')}
                                                </span>
                                              </div>
                                            </SelectItem>
                                          ))}
                                        </SelectGroup>
                                      </>
                                    )}
                                  </>
                                )}
                              </SelectContent>
                            </Select>
                            {currentAdapter &&
                              (() => {
                                const docUrl = getAdapterDocUrl(
                                  adapterHelpLinks[currentAdapter],
                                  i18n.language,
                                );
                                return docUrl ? (
                                  <a
                                    href={docUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex shrink-0 items-center gap-1 text-xs text-primary hover:underline"
                                  >
                                    {t('bots.viewAdapterDocs')}
                                    <ExternalLink className="h-3 w-3" />
                                  </a>
                                ) : null;
                              })()}
                          </div>
                        </FormControl>
                        {currentAdapter &&
                          adapterDescriptionList[currentAdapter] && (
                            <FormDescription>
                              {adapterDescriptionList[currentAdapter]}
                            </FormDescription>
                          )}
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                {currentAdapter && supportedConnectionModes.length > 1 && (
                  <div
                    data-guide="bot-connection-mode"
                    className="space-y-3 rounded-md border bg-muted/20 p-4"
                  >
                    <div>
                      <h3 className="text-sm font-medium">
                        {t('bots.connectionMode')}
                      </h3>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {t('bots.connectionModeDescription')}
                      </p>
                    </div>
                    <ToggleGroup
                      type="single"
                      value={connectionMode ?? ''}
                      onValueChange={(value) => {
                        if (value) {
                          handleConnectionModeChange(value as ConnectionMode);
                        }
                      }}
                      variant="outline"
                      className="grid w-full grid-cols-1 gap-3 sm:grid-cols-2"
                      spacing={3}
                    >
                      <ToggleGroupItem
                        value="webhook"
                        disabled={!supportedConnectionModes.includes('webhook')}
                        className="h-auto min-h-20 justify-start gap-3 whitespace-normal px-4 py-3 text-left data-[state=on]:border-blue-500/50 data-[state=on]:bg-blue-50 dark:data-[state=on]:bg-blue-500/10"
                      >
                        <Webhook className="size-5 shrink-0 text-primary" />
                        <span>
                          <span className="block font-medium">
                            {t('bots.connectionWebhook')}
                          </span>
                          <span className="mt-1 block text-xs font-normal text-muted-foreground">
                            {t('bots.connectionWebhookDescription')}
                          </span>
                        </span>
                      </ToggleGroupItem>
                      <ToggleGroupItem
                        value="persistent"
                        disabled={
                          !supportedConnectionModes.includes('persistent')
                        }
                        className="h-auto min-h-20 justify-start gap-3 whitespace-normal px-4 py-3 text-left data-[state=on]:border-blue-500/50 data-[state=on]:bg-blue-50 dark:data-[state=on]:bg-blue-500/10"
                      >
                        <Cable className="size-5 shrink-0 text-primary" />
                        <span>
                          <span className="block font-medium">
                            {t('bots.connectionPersistent')}
                          </span>
                          <span className="mt-1 block text-xs font-normal text-muted-foreground">
                            {t('bots.connectionPersistentDescription')}
                          </span>
                        </span>
                      </ToggleGroupItem>
                    </ToggleGroup>
                  </div>
                )}

                {showDynamicForm && dynamicFormConfigList.length > 0 && (
                  <div data-guide="bot-adapter-parameters">
                    <DynamicFormComponent
                      itemConfigList={dynamicFormConfigList}
                      initialValues={currentAdapterConfig}
                      onSubmit={(values) => {
                        form.setValue('adapter_config', values, {
                          shouldDirty: !isInitializing.current,
                        });
                      }}
                      systemContext={{
                        webhook_url: webhookUrl,
                        extra_webhook_url: extraWebhookUrl,
                        bot_uuid: initBotId || '',
                        adapter_config: form.getValues('adapter_config') || {},
                        outbound_ips: systemInfo.outbound_ips,
                      }}
                    />
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Card 2: Event Routing */}
          {initBotId && currentAdapter && (
            <Card
              data-guide="bot-routing"
              className={cn(
                'min-w-0',
                initBotId && 'lg:min-h-0 lg:overflow-hidden',
              )}
            >
              <CardHeader>
                <CardTitle>{t('bots.eventRouting')}</CardTitle>
                <CardDescription>
                  {t('bots.eventRoutingDescription')}
                </CardDescription>
              </CardHeader>
              <CardContent
                className={cn(
                  'min-w-0',
                  initBotId && 'lg:min-h-0 lg:flex-1 lg:overflow-y-auto',
                )}
              >
                <EventBindingsEditor
                  form={form}
                  botId={initBotId}
                  supportedEvents={adapterSupportedEvents[currentAdapter] || []}
                  agentOptions={agentNameList.filter(
                    (agent) => agent.kind !== 'event_processor',
                  )}
                />
                <PluginProcessorBindings
                  supportedEvents={adapterSupportedEvents[currentAdapter] || []}
                  value={form.watch('plugin_processors') ?? []}
                  onChange={(value) =>
                    form.setValue('plugin_processors', value, {
                      shouldDirty: true,
                    })
                  }
                  agents={agentNameList}
                  onCreated={(agent) =>
                    setAgentNameList((items) => [...items, agent])
                  }
                />
              </CardContent>
            </Card>
          )}
        </fieldset>
      </form>
      <GuidedTour
        enabled={Boolean(initBotId) && guideEnabled}
        storageKey="langbot_bot_detail_guide_v1"
        steps={botGuideSteps}
        testId="bot-detail-guide"
      />
    </Form>
  );
});

export default BotForm;
