import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import EmojiPicker from '@/components/ui/emoji-picker';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from '@/components/ui/form';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { KnowledgeBase, KnowledgeEngine } from '@/app/infra/entities/api';
import { CustomApiError } from '@/app/infra/entities/common';
import { toast } from 'sonner';
import { extractI18nObject } from '@/i18n/I18nProvider';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import {
  DynamicFormItemConfig,
  getDefaultValues,
  parseDynamicFormItemType,
} from '@/app/home/components/dynamic-form/DynamicFormItemConfig';
import { UUID } from 'uuidjs';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('knowledge.kbNameRequired') }),
    description: z.string().optional(),
    emoji: z.string().optional(),
    ragEngineId: z
      .string()
      .min(1, { message: t('knowledge.knowledgeEngineRequired') }),
  });

/**
 * Parse creation schema from Knowledge Engine to IDynamicFormItemSchema[]
 */
function parseCreationSchema(
  schemaItems: any | any[] | undefined,
): IDynamicFormItemSchema[] {
  if (!schemaItems) return [];
  const items = Array.isArray(schemaItems) ? schemaItems : schemaItems.schema;
  if (!items || !Array.isArray(items)) return [];

  return items.map(
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
      }),
  );
}

export default function KBForm({
  initKbId,
  onNewKbCreated,
  onKbUpdated,
  onDirtyChange,
}: {
  initKbId?: string;
  onNewKbCreated: (kbId: string) => void;
  onKbUpdated: (kbId: string) => void;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const { t } = useTranslation();
  const [ragEngines, setRagEngines] = useState<KnowledgeEngine[]>([]);
  const [selectedEngineId, setSelectedEngineId] = useState<string>('');
  const [configSettings, setConfigSettings] = useState<Record<string, unknown>>(
    {},
  );
  const [retrievalSettings, setRetrievalSettings] = useState<
    Record<string, unknown>
  >({});
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);

  // Dirty tracking: snapshot of saved state for comparison
  const savedSnapshotRef = useRef<string>('');
  const isInitializing = useRef(true);

  // Refs to store validation functions from dynamic forms
  const configValidateRef = useRef<(() => Promise<boolean>) | null>(null);
  const retrievalValidateRef = useRef<(() => Promise<boolean>) | null>(null);

  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: '',
      emoji: '📚',
      ragEngineId: '',
    },
  });

  // Get selected engine details
  const selectedEngine = ragEngines.find(
    (e) => e.plugin_id === selectedEngineId,
  );

  // Dirty tracking: compare current form + dynamic settings against saved snapshot
  const watchedFormValues = form.watch();
  useEffect(() => {
    if (!savedSnapshotRef.current || isInitializing.current) return;
    const currentSnapshot = JSON.stringify({
      form: watchedFormValues,
      config: configSettings,
      retrieval: retrievalSettings,
    });
    const dirty = currentSnapshot !== savedSnapshotRef.current;
    onDirtyChange?.(dirty);
  }, [watchedFormValues, configSettings, retrievalSettings, onDirtyChange]);

  const captureSnapshot = () => {
    savedSnapshotRef.current = JSON.stringify({
      form: form.getValues(),
      config: configSettings,
      retrieval: retrievalSettings,
    });
  };

  useEffect(() => {
    loadRagEngines().then(() => {
      if (initKbId) {
        loadKbConfig(initKbId);
      }
    });
  }, []);

  // Auto-select first engine when engines are loaded and no selection
  useEffect(() => {
    if (ragEngines.length > 0 && !selectedEngineId && !isEditing) {
      const firstEngine = ragEngines[0];
      setSelectedEngineId(firstEngine.plugin_id);
      form.setValue('ragEngineId', firstEngine.plugin_id);
      const formItems = parseCreationSchema(firstEngine.creation_schema);
      if (formItems.length > 0) {
        setConfigSettings(getDefaultValues(formItems));
      }
      const retrievalItems = parseCreationSchema(firstEngine.retrieval_schema);
      if (retrievalItems.length > 0) {
        setRetrievalSettings(getDefaultValues(retrievalItems));
      }
    }
  }, [ragEngines, selectedEngineId, isEditing]);

  const loadRagEngines = async () => {
    setLoading(true);
    try {
      const resp = await httpClient.getKnowledgeEngines();
      setRagEngines(resp.engines);
    } catch (err) {
      console.error('Failed to load Knowledge Engines:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadKbConfig = async (kbId: string) => {
    try {
      isInitializing.current = true;
      setIsEditing(true);

      const res = await httpClient.getKnowledgeBase(kbId);
      const kb = res.base;

      const engineId = kb.knowledge_engine_plugin_id || '';
      setSelectedEngineId(engineId);

      form.reset({
        name: kb.name,
        description: kb.description,
        emoji: kb.emoji || '📚',
        ragEngineId: engineId,
      });

      setConfigSettings(kb.creation_settings || {});
      setRetrievalSettings(kb.retrieval_settings || {});

      // Capture snapshot after a tick so dynamic forms have emitted initial values
      setTimeout(() => {
        captureSnapshot();
        isInitializing.current = false;
      }, 500);
    } catch (err) {
      console.error('Failed to load KB config:', err);
      isInitializing.current = false;
    }
  };

  const handleEngineChange = (engineId: string) => {
    setSelectedEngineId(engineId);
    form.setValue('ragEngineId', engineId);

    const engine = ragEngines.find((e) => e.plugin_id === engineId);
    if (engine) {
      const formItems = parseCreationSchema(engine.creation_schema);
      if (formItems.length > 0) {
        setConfigSettings(getDefaultValues(formItems));
      } else {
        setConfigSettings({});
      }
      const retrievalItems = parseCreationSchema(engine.retrieval_schema);
      if (retrievalItems.length > 0) {
        setRetrievalSettings(getDefaultValues(retrievalItems));
      } else {
        setRetrievalSettings({});
      }
    }
  };

  const onSubmit = async (data: z.infer<typeof formSchema>) => {
    // Validate dynamic forms before submission
    if (configValidateRef.current) {
      const configValid = await configValidateRef.current();
      if (!configValid) {
        toast.error(t('knowledge.engineSettingsInvalid'));
        return;
      }
    }

    if (retrievalValidateRef.current) {
      const retrievalValid = await retrievalValidateRef.current();
      if (!retrievalValid) {
        toast.error(t('knowledge.retrievalSettingsInvalid'));
        return;
      }
    }

    const kbData: KnowledgeBase = {
      name: data.name,
      description: data.description ?? '',
      emoji: data.emoji,
      knowledge_engine_plugin_id: selectedEngineId,
      creation_settings: configSettings,
      retrieval_settings: retrievalSettings,
    };

    if (initKbId) {
      httpClient
        .updateKnowledgeBase(initKbId, kbData)
        .then((res) => {
          captureSnapshot();
          onDirtyChange?.(false);
          onKbUpdated(res.uuid);
          toast.success(t('knowledge.updateKnowledgeBaseSuccess'));
        })
        .catch((err) => {
          console.error('update knowledge base failed', err);
          toast.error(
            t('knowledge.updateKnowledgeBaseFailed') +
              (err as CustomApiError).msg,
          );
        });
    } else {
      httpClient
        .createKnowledgeBase(kbData)
        .then((res) => {
          onNewKbCreated(res.uuid);
        })
        .catch((err) => {
          console.error('create knowledge base failed', err);
          toast.error(
            t('knowledge.createKnowledgeBaseFailed') +
              (err as CustomApiError).msg,
          );
        });
    }
  };

  const configFormItems = useMemo(
    () => parseCreationSchema(selectedEngine?.creation_schema),
    [selectedEngine?.creation_schema],
  );

  const retrievalFormItems = useMemo(
    () => parseCreationSchema(selectedEngine?.retrieval_schema),
    [selectedEngine?.retrieval_schema],
  );

  // Show loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-muted-foreground">{t('common.loading')}</p>
      </div>
    );
  }

  // Show message if no engines available
  if (ragEngines.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 space-y-4">
        <p className="text-muted-foreground">
          {t('knowledge.noEnginesAvailable')}
        </p>
        <Link
          to="/home/market?category=KnowledgeEngine"
          className="text-sm text-primary hover:underline"
        >
          {t('knowledge.installEngineHint')}
        </Link>
      </div>
    );
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        id="kb-form"
        className="space-y-6"
      >
        {/* Card 1: Basic Information */}
        <Card>
          <CardHeader>
            <CardTitle>{t('knowledge.basicInfo')}</CardTitle>
            <CardDescription>
              {t('knowledge.basicInfoDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Name and Emoji in same row */}
            <div className="flex gap-4 items-start">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormLabel>
                      {t('knowledge.kbName')}
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

            {/* Description */}
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('knowledge.kbDescription')}</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Knowledge Engine Selector */}
            <FormField
              control={form.control}
              name="ragEngineId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('knowledge.knowledgeEngine')}
                    <span className="text-destructive">*</span>
                  </FormLabel>
                  <FormControl>
                    <Select
                      disabled={isEditing}
                      onValueChange={(value) => {
                        field.onChange(value);
                        handleEngineChange(value);
                      }}
                      value={field.value}
                    >
                      <SelectTrigger className="w-full bg-[#ffffff] dark:bg-[#2a2a2e]">
                        {field.value ? (
                          (() => {
                            const [author, name] = field.value.split('/');
                            const engine = ragEngines.find(
                              (e) => e.plugin_id === field.value,
                            );
                            return (
                              <div className="flex items-center gap-2">
                                <img
                                  src={httpClient.getPluginIconURL(
                                    author,
                                    name,
                                  )}
                                  alt=""
                                  className="h-5 w-5 rounded"
                                />
                                <span>
                                  {engine
                                    ? extractI18nObject(engine.name)
                                    : field.value}
                                </span>
                              </div>
                            );
                          })()
                        ) : (
                          <SelectValue
                            placeholder={t('knowledge.selectKnowledgeEngine')}
                          />
                        )}
                      </SelectTrigger>
                      <SelectContent className="fixed z-[1000]">
                        {ragEngines.map((engine) => {
                          const [author, name] = engine.plugin_id.split('/');
                          return (
                            <SelectItem
                              key={engine.plugin_id}
                              value={engine.plugin_id}
                            >
                              <div className="flex items-center gap-2">
                                <img
                                  src={httpClient.getPluginIconURL(
                                    author,
                                    name,
                                  )}
                                  alt=""
                                  className="h-5 w-5 rounded"
                                />
                                <span>{extractI18nObject(engine.name)}</span>
                              </div>
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  </FormControl>
                  {selectedEngine?.description && (
                    <FormDescription>
                      {extractI18nObject(selectedEngine.description)}
                    </FormDescription>
                  )}
                  {isEditing && (
                    <FormDescription>
                      {t('knowledge.cannotChangeKnowledgeEngine')}
                    </FormDescription>
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        {/* Card 2: Engine Settings (dynamic form from creation_schema) */}
        {configFormItems.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>{t('knowledge.engineSettings')}</CardTitle>
              <CardDescription>
                {t('knowledge.engineSettingsDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <DynamicFormComponent
                itemConfigList={configFormItems}
                initialValues={configSettings as Record<string, object>}
                onSubmit={(val) =>
                  setConfigSettings(val as Record<string, unknown>)
                }
                isEditing={isEditing}
                externalDependentValues={retrievalSettings}
                onValidate={(validateFn) =>
                  (configValidateRef.current = validateFn)
                }
              />
            </CardContent>
          </Card>
        )}

        {/* Card 3: Retrieval Settings (dynamic form from retrieval_schema) */}
        {retrievalFormItems.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>{t('knowledge.retrievalSettings')}</CardTitle>
              <CardDescription>
                {t('knowledge.retrievalSettingsDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <DynamicFormComponent
                itemConfigList={retrievalFormItems}
                initialValues={retrievalSettings as Record<string, object>}
                onSubmit={(val) =>
                  setRetrievalSettings(val as Record<string, unknown>)
                }
                externalDependentValues={configSettings}
                onValidate={(validateFn) =>
                  (retrievalValidateRef.current = validateFn)
                }
              />
            </CardContent>
          </Card>
        )}
      </form>
    </Form>
  );
}
