import React, { useEffect, useMemo, useRef, useState } from 'react';
import i18n from 'i18next';
import { IChooseAdapterEntity } from '@/app/home/bots/components/bot-form/ChooseEntity';
import {
  DynamicFormItemConfig,
  getDefaultValues,
  parseDynamicFormItemType,
} from '@/app/home/components/dynamic-form/DynamicFormItemConfig';
import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import { UUID } from 'uuidjs';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { httpClient } from '@/app/infra/http/HttpClient';
import { systemInfo } from '@/app/infra/http';
import { Agent, Bot } from '@/app/infra/entities/api';
import { getAdapterDocUrl } from '@/app/infra/entities/adapter-docs';
import { ExternalLink, ChevronDown, ChevronRight } from 'lucide-react';
import EventBindingsEditor from './EventBindingsEditor';

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

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('bots.botNameRequired') }),
    description: z.string().optional(),
    adapter: z.string().min(1, { message: t('bots.adapterRequired') }),
    adapter_config: z.record(z.string(), z.any()),
    enable: z.boolean().optional(),
    event_bindings: z
      .array(
        z.object({
          id: z.string().optional(),
          event_pattern: z.string(),
          target_type: z.enum(['agent', 'pipeline', 'discard']),
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

export default function BotForm({
  initBotId,
  onFormSubmit,
  onNewBotCreated,
  onDirtyChange,
}: {
  initBotId?: string;
  onFormSubmit: (value: z.infer<ReturnType<typeof getFormSchema>>) => void;
  onNewBotCreated: (botId: string) => void;
  onDirtyChange?: (dirty: boolean) => void;
}) {
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
    },
  });

  // Track whether initial data loading is complete.
  // setValue calls during init should NOT mark the form as dirty.
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
  const [, setIsLoading] = useState<boolean>(false);
  const [webhookUrl, setWebhookUrl] = useState<string>('');
  const [extraWebhookUrl, setExtraWebhookUrl] = useState<string>('');

  // Watch adapter and adapter_config for filtering
  const currentAdapter = form.watch('adapter');
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

  useEffect(() => {
    setBotFormValues();
  }, []);

  function setBotFormValues() {
    isInitializing.current = true;
    initBotFormComponent().then(() => {
      if (initBotId) {
        getBotConfig(initBotId)
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
            });
            handleAdapterSelect(val.adapter);

            if (val.webhook_full_url) {
              setWebhookUrl(val.webhook_full_url);
            } else {
              setWebhookUrl('');
            }
            setExtraWebhookUrl(val.extra_webhook_full_url || '');
          })
          .catch((err) => {
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
    });
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

  function handleAdapterSelect(adapterName: string) {
    if (adapterName) {
      const dynamicFormConfigList =
        adapterNameToDynamicConfigMap.get(adapterName);
      if (dynamicFormConfigList) {
        setDynamicFormConfigList(dynamicFormConfigList);
        if (!initBotId) {
          form.setValue(
            'adapter_config',
            getDefaultValues(dynamicFormConfigList),
          );
        }
      }
      setShowDynamicForm(true);
    } else {
      setShowDynamicForm(false);
    }
  }

  function onDynamicFormSubmit() {
    setIsLoading(true);
    if (initBotId) {
      const updateBot: Bot = {
        uuid: initBotId,
        name: form.getValues().name,
        description: form.getValues().description ?? '',
        adapter: form.getValues().adapter,
        adapter_config: form.getValues().adapter_config,
        enable: form.getValues().enable,
        event_bindings: form.getValues().event_bindings ?? [],
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
          toast.error(t('bots.saveError') + err.msg);
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      const newBot: Bot = {
        name: form.getValues().name,
        description: form.getValues().description ?? '',
        adapter: form.getValues().adapter,
        adapter_config: form.getValues().adapter_config,
      };
      httpClient
        .createBot(newBot)
        .then((res) => {
          toast.success(t('bots.createSuccess'));
          initBotId = res.uuid;

          setBotFormValues();

          onNewBotCreated(res.uuid);
        })
        .catch((err) => {
          toast.error(t('bots.createError') + err.msg);
        })
        .finally(() => {
          setIsLoading(false);
          form.reset();
        });
    }
  }

  return (
    <Form {...form}>
      <form
        id="bot-form"
        onSubmit={form.handleSubmit(onDynamicFormSubmit)}
        className="space-y-6"
      >
        {/* Card 1: Basic Information */}
        <Card>
          <CardHeader>
            <CardTitle>{t('bots.basicInfo')}</CardTitle>
            <CardDescription>{t('bots.basicInfoDescription')}</CardDescription>
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

        {/* Card 2: Event Routing (edit mode only) */}
        {initBotId && (
          <Card>
            <CardHeader>
              <CardTitle>{t('bots.eventRouting')}</CardTitle>
              <CardDescription>
                {t('bots.eventRoutingDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <EventBindingsEditor
                form={form}
                botId={initBotId}
                supportedEvents={adapterSupportedEvents[currentAdapter] || []}
                agentOptions={agentNameList}
              />
            </CardContent>
          </Card>
        )}

        {/* Card 4: Adapter Configuration */}
        <Card>
          <CardHeader>
            <CardTitle>{t('bots.adapterConfig')}</CardTitle>
            <CardDescription>
              {t('bots.adapterConfigDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
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
                    <div className="flex items-center gap-2">
                      <Select
                        onValueChange={(value) => {
                          field.onChange(value);
                          handleAdapterSelect(value);
                        }}
                        value={field.value}
                      >
                        <SelectTrigger className="w-[240px] overflow-hidden">
                          {field.value ? (
                            <div className="flex min-w-0 items-center gap-2">
                              <img
                                src={httpClient.getAdapterIconURL(field.value)}
                                alt=""
                                className="h-5 w-5 shrink-0 rounded"
                              />
                              {(() => {
                                const selectedAdapter = adapterNameList.find(
                                  (a) => a.value === field.value,
                                );

                                return (
                                  <>
                                    <span className="min-w-0 truncate">
                                      {selectedAdapter?.label ?? field.value}
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
                        <SelectContent>
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
                                  if (e.key === 'Enter' || e.key === ' ') {
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
                                  <p className="px-2 pb-1 text-[11px] leading-snug text-muted-foreground">
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
                  {currentAdapter && adapterDescriptionList[currentAdapter] && (
                    <FormDescription>
                      {adapterDescriptionList[currentAdapter]}
                    </FormDescription>
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />

            {showDynamicForm && dynamicFormConfigList.length > 0 && (
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
            )}
          </CardContent>
        </Card>
      </form>
    </Form>
  );
}
