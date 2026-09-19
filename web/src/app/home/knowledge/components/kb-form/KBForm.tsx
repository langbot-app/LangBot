import EntityLoadState from '@/components/EntityLoadState';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { Separator } from '@/components/ui/separator';
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
import KnowledgeEngineSelect from './KnowledgeEngineSelect';
import GuidedTour, {
  GuidedTourStep,
} from '@/app/home/components/guided-tour/GuidedTour';

const KNOWLEDGE_ENGINE_MARKETPLACE_URL =
  'https://space.langbot.app/market?type=plugin&component=KnowledgeEngine';

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
  guideEnabled = true,
}: {
  initKbId?: string;
  onNewKbCreated: (kbId: string) => void;
  onKbUpdated: (kbId: string) => void;
  onDirtyChange?: (dirty: boolean) => void;
  guideEnabled?: boolean;
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
  const [isEditing, setIsEditing] = useState(Boolean(initKbId));
  const [engineInitialized, setEngineInitialized] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [initialDataLoaded, setInitialDataLoaded] = useState(false);
  const [loading, setLoading] = useState(true);

  // Dirty tracking: snapshot of saved state for comparison
  const savedSnapshotRef = useRef<string>('');
  const isInitializing = useRef(true);
  const suppressNextAutoSelectRef = useRef(false);

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
    setInitialDataLoaded(false);
    setLoadFailed(false);
    loadRagEngines()
      .then(() => {
        if (initKbId) return loadKbConfig(initKbId);
      })
      .catch(() => setLoadFailed(true))
      .finally(() => setInitialDataLoaded(true));
  }, [initKbId, loadAttempt]);

  // Auto-select first engine when engines are loaded and no selection
  useEffect(() => {
    if (ragEngines.length > 0 && !selectedEngineId && !isEditing) {
      if (suppressNextAutoSelectRef.current) {
        suppressNextAutoSelectRef.current = false;
        return;
      }
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
      throw err;
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
      setEngineInitialized(kb.initialized !== false);

      // Capture snapshot after a tick so dynamic forms have emitted initial values
      setTimeout(() => {
        captureSnapshot();
        isInitializing.current = false;
        onDirtyChange?.(kb.initialized === false);
      }, 500);
    } catch (err) {
      isInitializing.current = false;
      throw err;
    }
  };

  const handleEngineChange = useCallback(
    (engineId: string, installedEngine?: KnowledgeEngine) => {
      setSelectedEngineId(engineId);
      form.setValue('ragEngineId', engineId, {
        shouldDirty: true,
        shouldTouch: true,
        shouldValidate: true,
      });
      form.clearErrors('ragEngineId');
      void form.trigger('ragEngineId');

      const engine =
        installedEngine ??
        ragEngines.find((candidate) => candidate.plugin_id === engineId);
      if (!engine) return;

      const formItems = parseCreationSchema(engine.creation_schema);
      setConfigSettings(
        formItems.length > 0 ? getDefaultValues(formItems) : {},
      );
      const retrievalItems = parseCreationSchema(engine.retrieval_schema);
      setRetrievalSettings(
        retrievalItems.length > 0 ? getDefaultValues(retrievalItems) : {},
      );
    },
    [form, ragEngines],
  );

  const handleEngineInstalled = useCallback((engine: KnowledgeEngine) => {
    suppressNextAutoSelectRef.current = true;
    setRagEngines((current) => [
      ...current.filter((item) => item.plugin_id !== engine.plugin_id),
      engine,
    ]);
  }, []);

  const onSubmit = async (data: z.infer<typeof formSchema>) => {
    // Engine parameters are configured only after the draft has been created.
    if (initKbId && configValidateRef.current) {
      const configValid = await configValidateRef.current();
      if (!configValid) {
        toast.error(t('knowledge.engineSettingsInvalid'));
        return;
      }
    }

    if (initKbId && retrievalValidateRef.current) {
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
      ...(initKbId
        ? { initialize_engine: !engineInitialized }
        : { defer_initialization: true }),
    };

    if (initKbId) {
      httpClient
        .updateKnowledgeBase(initKbId, kbData)
        .then((res) => {
          setEngineInitialized(true);
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

  const guideSteps = useMemo<GuidedTourStep[]>(() => {
    const steps: GuidedTourStep[] = [
      {
        id: 'engine',
        target: '[data-guide="knowledge-engine"] [role="combobox"]',
        title: t('guidedTour.knowledge.engine.title'),
        description: t('guidedTour.knowledge.engine.description'),
        action: {
          href: KNOWLEDGE_ENGINE_MARKETPLACE_URL,
          label: t('guidedTour.knowledge.engine.action'),
        },
      },
    ];

    if (configFormItems.length > 0) {
      steps.push({
        id: 'engine-parameters',
        target: '[data-guide="knowledge-engine-parameters"]',
        title: t('guidedTour.knowledge.parameters.title'),
        description: t('guidedTour.knowledge.parameters.description'),
      });
    }

    if (retrievalFormItems.length > 0) {
      steps.push({
        id: 'retrieval',
        target: '[data-guide="knowledge-retrieval"]',
        title: t('guidedTour.knowledge.retrieval.title'),
        description: t('guidedTour.knowledge.retrieval.description'),
      });
    }

    steps.push({
      id: 'save',
      target: '[data-guide="knowledge-config-save"]',
      title: t('guidedTour.knowledge.save.title'),
      description: t('guidedTour.knowledge.save.description'),
    });
    return steps;
  }, [configFormItems, retrievalFormItems, t]);

  if (loadFailed)
    return (
      <EntityLoadState error onRetry={() => setLoadAttempt((n) => n + 1)} />
    );
  if (!initialDataLoaded) return <EntityLoadState />;

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        id="kb-form"
        className="space-y-6"
      >
        {/* Basic information is entered here only during creation. */}
        {!isEditing && (
          <Card data-guide="knowledge-basic">
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
            </CardContent>
          </Card>
        )}

        {/* Knowledge engine selection and settings stay together. */}
        <Card data-guide="knowledge-engine">
          <CardHeader>
            <CardTitle>{t('knowledge.engineSettings')}</CardTitle>
            <CardDescription>
              {t('knowledge.engineSettingsDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
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
                    <KnowledgeEngineSelect
                      engines={ragEngines}
                      value={field.value}
                      disabled={isEditing}
                      loading={loading}
                      installScope="knowledge-base-create"
                      onValueChange={handleEngineChange}
                      onInstalled={handleEngineInstalled}
                    />
                  </FormControl>
                  {selectedEngine?.description && (
                    <FormDescription className="max-w-[28rem] leading-5">
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

            {isEditing && configFormItems.length > 0 && (
              <div
                data-guide="knowledge-engine-parameters"
                className="space-y-6"
              >
                <Separator />
                <DynamicFormComponent
                  itemConfigList={configFormItems}
                  initialValues={configSettings as Record<string, object>}
                  onSubmit={(val) =>
                    setConfigSettings(val as Record<string, unknown>)
                  }
                  isEditing={engineInitialized}
                  externalDependentValues={retrievalSettings}
                  onValidate={(validateFn) =>
                    (configValidateRef.current = validateFn)
                  }
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Retrieval Settings (dynamic form from retrieval_schema) */}
        {isEditing && retrievalFormItems.length > 0 && (
          <Card data-guide="knowledge-retrieval">
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
      <GuidedTour
        enabled={isEditing && guideEnabled}
        storageKey="langbot_knowledge_detail_guide_v1"
        steps={guideSteps}
        testId="knowledge-detail-guide"
      />
    </Form>
  );
}
