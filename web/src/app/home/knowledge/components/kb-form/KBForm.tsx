import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from '@/components/ui/form';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { KnowledgeBase, RAGEngine } from '@/app/infra/entities/api';
import { toast } from 'sonner';
import { extractI18nObject } from '@/i18n/I18nProvider';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import {
  jsonSchemaToFormItems,
  getDefaultValuesFromSchema,
} from '@/app/infra/utils/jsonSchemaConverter';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('knowledge.kbNameRequired') }),
    description: z
      .string()
      .min(1, { message: t('knowledge.kbDescriptionRequired') }),
    ragEngineId: z
      .string()
      .min(1, { message: t('knowledge.ragEngineRequired') }),
  });

export default function KBForm({
  initKbId,
  onNewKbCreated,
  onKbUpdated,
}: {
  initKbId?: string;
  onNewKbCreated: (kbId: string) => void;
  onKbUpdated: (kbId: string) => void;
}) {
  const { t } = useTranslation();
  const [ragEngines, setRagEngines] = useState<RAGEngine[]>([]);
  const [selectedEngineId, setSelectedEngineId] = useState<string>('');
  const [configSettings, setConfigSettings] = useState<
    Record<string, unknown>
  >({});
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);

  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: t('knowledge.defaultDescription'),
      ragEngineId: '',
    },
  });

  // Get selected engine details
  const selectedEngine = ragEngines.find(
    (e) => e.plugin_id === selectedEngineId,
  );

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
      // Initialize config settings with defaults
      if (firstEngine.creation_schema) {
        setConfigSettings(
          getDefaultValuesFromSchema(firstEngine.creation_schema),
        );
      }
    }
  }, [ragEngines, selectedEngineId, isEditing]);

  const loadRagEngines = async () => {
    setLoading(true);
    try {
      const resp = await httpClient.getRagEngines();
      setRagEngines(resp.engines);
    } catch (err) {
      console.error('Failed to load RAG engines:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadKbConfig = async (kbId: string) => {
    try {
      setIsEditing(true);

      const res = await httpClient.getKnowledgeBase(kbId);
      const kb = res.base;

      const engineId = kb.rag_engine_plugin_id || '';
      setSelectedEngineId(engineId);

      form.setValue('name', kb.name);
      form.setValue('description', kb.description);
      form.setValue('ragEngineId', engineId);

      setConfigSettings(kb.creation_settings || {});
    } catch (err) {
      console.error('Failed to load KB config:', err);
    }
  };

  const handleEngineChange = (engineId: string) => {
    setSelectedEngineId(engineId);
    form.setValue('ragEngineId', engineId);

    // Find engine and initialize config settings with defaults from schema
    const engine = ragEngines.find((e) => e.plugin_id === engineId);
    if (engine) {
      if (engine.creation_schema) {
        setConfigSettings(getDefaultValuesFromSchema(engine.creation_schema));
      } else {
        setConfigSettings({});
      }
    }
  };

  const onSubmit = (data: z.infer<typeof formSchema>) => {
    const kbData: KnowledgeBase = {
      name: data.name,
      description: data.description,
      rag_engine_plugin_id: selectedEngineId,
      creation_settings: configSettings,
      embedding_model_uuid: '',
      top_k: 5,
    };

    if (initKbId) {
      // Update knowledge base
      httpClient
        .updateKnowledgeBase(initKbId, kbData)
        .then((res) => {
          onKbUpdated(res.uuid);
          toast.success(t('knowledge.updateKnowledgeBaseSuccess'));
        })
        .catch((err) => {
          console.error('update knowledge base failed', err);
          toast.error(t('knowledge.updateKnowledgeBaseFailed'));
        });
    } else {
      // Create knowledge base
      httpClient
        .createKnowledgeBase(kbData)
        .then((res) => {
          onNewKbCreated(res.uuid);
        })
        .catch((err) => {
          console.error('create knowledge base failed', err);
          toast.error(t('knowledge.createKnowledgeBaseFailed'));
        });
    }
  };

  // Convert creation schema to dynamic form items
  const configFormItems = (() => {
    if (!selectedEngine?.creation_schema) return [];
    return jsonSchemaToFormItems(selectedEngine.creation_schema);
  })();

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
        <p className="text-muted-foreground">{t('knowledge.noEnginesAvailable')}</p>
        <p className="text-sm text-muted-foreground">
          {t('knowledge.installEngineHint')}
        </p>
      </div>
    );
  }

  return (
    <>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          id="kb-form"
          className="space-y-8"
        >
          <div className="space-y-4">
            {/* RAG Engine Selector */}
            <FormField
              control={form.control}
              name="ragEngineId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('knowledge.ragEngine')}
                    <span className="text-red-500">*</span>
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
                        <SelectValue
                          placeholder={t('knowledge.selectRagEngine')}
                        />
                      </SelectTrigger>
                      <SelectContent className="fixed z-[1000]">
                        {ragEngines.map((engine) => (
                          <SelectItem
                            key={engine.plugin_id}
                            value={engine.plugin_id}
                          >
                            {engine.name}
                          </SelectItem>
                        ))}
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
                      {t('knowledge.cannotChangeRagEngine')}
                    </FormDescription>
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Name */}
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('knowledge.kbName')}
                    <span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Description */}
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('knowledge.kbDescription')}
                    <span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Engine specific fields (dynamic form) */}
            {configFormItems.length > 0 && (
              <div className="space-y-4 pt-2 border-t">
                <div className="text-sm font-medium text-muted-foreground">
                  {t('knowledge.engineSettings')}
                </div>
                <DynamicFormComponent
                  itemConfigList={configFormItems}
                  initialValues={configSettings as Record<string, object>}
                  onSubmit={(val) =>
                    setConfigSettings(val as Record<string, unknown>)
                  }
                />
              </div>
            )}
          </div>
        </form>
      </Form>
    </>
  );
}
