import { useEffect, useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { UUID } from 'uuidjs';

import {
  DynamicFormItemConfig,
  getDefaultValues,
  parseDynamicFormItemType,
} from '@/app/home/components/dynamic-form/DynamicFormItemConfig';
import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { httpClient } from '@/app/infra/http/HttpClient';
import { ExternalKnowledgeBase } from '@/app/infra/entities/api';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
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
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { I18nObject } from '@/app/infra/entities/common';

// Form schema
const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('knowledge.nameRequired') }),
    description: z.string().optional(),
    plugin_author: z.string().min(1, { message: 'Please select a retriever' }),
    plugin_name: z.string().min(1, { message: 'Please select a retriever' }),
    retriever_name: z.string().min(1, { message: 'Please select a retriever' }),
    retriever_config: z.record(z.string(), z.any()),
  });

// Retriever information interface
interface RetrieverInfo {
  plugin_author: string;
  plugin_name: string;
  retriever_name: string;
  retriever_description: I18nObject;
  manifest: {
    manifest?: {
      metadata?: {
        label?: I18nObject;
        description?: I18nObject;
      };
      spec?: {
        config?: IDynamicFormItemSchema[];
      };
    };
  };
}

interface ExternalKBFormProps {
  initKBId?: string;
  onFormSubmit: (value: z.infer<ReturnType<typeof getFormSchema>>) => void;
  onKBDeleted: () => void;
  onNewKBCreated: (kbId: string) => void;
}

export default function ExternalKBForm({
  initKBId,
  onFormSubmit,
  onKBDeleted,
  onNewKBCreated,
}: ExternalKBFormProps) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

  // Form setup
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: '',
      plugin_author: '',
      plugin_name: '',
      retriever_name: '',
      retriever_config: {},
    },
  });

  // State management
  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState(false);
  const [availableRetrievers, setAvailableRetrievers] = useState<
    RetrieverInfo[]
  >([]);
  const [retrieverNameToConfigMap, setRetrieverNameToConfigMap] = useState(
    new Map<string, IDynamicFormItemSchema[]>(),
  );
  const [showDynamicForm, setShowDynamicForm] = useState<boolean>(false);
  const [dynamicFormConfigList, setDynamicFormConfigList] = useState<
    IDynamicFormItemSchema[]
  >([]);

  // Initialize form when initKBId changes
  useEffect(() => {
    loadFormData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initKBId]);

  /**
   * Load form data: initialize retrievers list and load KB config if editing
   */
  async function loadFormData() {
    const configMap = await loadAvailableRetrievers();

    if (initKBId) {
      // Edit mode: load existing KB configuration
      try {
        const kbConfig = await loadKBConfig(initKBId);
        // Set form values
        form.setValue('name', kbConfig.name);
        form.setValue('description', kbConfig.description || '');
        form.setValue('plugin_author', kbConfig.plugin_author);
        form.setValue('plugin_name', kbConfig.plugin_name);
        form.setValue('retriever_name', kbConfig.retriever_name);
        form.setValue('retriever_config', kbConfig.retriever_config);

        // Load dynamic form for the selected retriever
        const fullName = `${kbConfig.plugin_author}/${kbConfig.plugin_name}/${kbConfig.retriever_name}`;
        loadDynamicFormConfig(fullName, configMap);
      } catch (err) {
        toast.error('Failed to load KB config: ' + (err as Error).message);
      }
    } else {
      // Create mode: reset form
      form.reset();
    }
  }

  /**
   * Load available retrievers from API and build config map
   */
  async function loadAvailableRetrievers(): Promise<
    Map<string, IDynamicFormItemSchema[]>
  > {
    const retrieversRes = await httpClient.listKnowledgeRetrievers();
    setAvailableRetrievers((retrieversRes.retrievers || []) as RetrieverInfo[]);

    // Build retriever name to config map
    const configMap = new Map<string, IDynamicFormItemSchema[]>();
    ((retrieversRes.retrievers || []) as RetrieverInfo[]).forEach(
      (retriever) => {
        const fullName = `${retriever.plugin_author}/${retriever.plugin_name}/${retriever.retriever_name}`;
        const configSchema = retriever.manifest?.manifest?.spec?.config || [];

        configMap.set(
          fullName,
          configSchema.map(
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
              }),
          ),
        );
      },
    );

    setRetrieverNameToConfigMap(configMap);
    return configMap;
  }

  /**
   * Load KB configuration from API
   */
  async function loadKBConfig(
    kbId: string,
  ): Promise<z.infer<typeof formSchema>> {
    const res = await httpClient.getExternalKnowledgeBase(kbId);
    const kb = res.base;
    return {
      name: kb.name,
      description: kb.description,
      plugin_author: kb.plugin_author,
      plugin_name: kb.plugin_name,
      retriever_name: kb.retriever_name,
      retriever_config: kb.retriever_config || {},
    };
  }

  /**
   * Load dynamic form configuration for selected retriever
   * @param fullRetrieverName - Full retriever name in format: plugin_author/plugin_name/retriever_name
   * @param configMapOverride - Optional config map to use (for initial load)
   */
  function loadDynamicFormConfig(
    fullRetrieverName: string,
    configMapOverride?: Map<string, IDynamicFormItemSchema[]>,
  ) {
    if (!fullRetrieverName) {
      setShowDynamicForm(false);
      return;
    }

    // Use provided config map or fall back to state
    const configMap = configMapOverride || retrieverNameToConfigMap;
    const configList = configMap.get(fullRetrieverName);

    if (configList && configList.length > 0) {
      setDynamicFormConfigList(configList);
      setShowDynamicForm(true);

      // Only reset to default values when manually selecting (not initial load)
      if (!configMapOverride) {
        form.setValue('retriever_config', getDefaultValues(configList));
      }
    } else {
      setShowDynamicForm(false);
      if (!configMapOverride) {
        form.setValue('retriever_config', {});
      }
    }
  }

  /**
   * Handle retriever selection change
   */
  function handleRetrieverSelect(fullRetrieverName: string) {
    if (!fullRetrieverName) {
      setShowDynamicForm(false);
      return;
    }

    // Parse and update form fields
    const parts = fullRetrieverName.split('/');
    if (parts.length === 3) {
      form.setValue('plugin_author', parts[0]);
      form.setValue('plugin_name', parts[1]);
      form.setValue('retriever_name', parts[2]);
    }

    // Load dynamic form configuration
    loadDynamicFormConfig(fullRetrieverName);
  }

  /**
   * Handle form submission (create or update)
   */
  function handleFormSubmit() {
    const formData: ExternalKnowledgeBase = {
      name: form.getValues().name,
      description: form.getValues().description || '',
      plugin_author: form.getValues().plugin_author,
      plugin_name: form.getValues().plugin_name,
      retriever_name: form.getValues().retriever_name,
      retriever_config: form.getValues().retriever_config,
    };

    if (initKBId) {
      // Update existing KB
      httpClient
        .updateExternalKnowledgeBase(initKBId, { ...formData, uuid: initKBId })
        .then(() => {
          onFormSubmit(form.getValues());
          toast.success(t('knowledge.updateExternalSuccess'));
        })
        .catch((err) => {
          toast.error('Failed to update KB: ' + err.message);
        });
    } else {
      // Create new KB
      httpClient
        .createExternalKnowledgeBase(formData)
        .then((res) => {
          toast.success(t('knowledge.createExternalSuccess'));
          onNewKBCreated(res.uuid);
          form.reset();
        })
        .catch((err) => {
          toast.error('Failed to create KB: ' + err.message);
        });
    }
  }

  /**
   * Handle KB deletion
   */
  function handleDelete() {
    if (!initKBId) return;

    httpClient
      .deleteExternalKnowledgeBase(initKBId)
      .then(() => {
        onKBDeleted();
        toast.success(t('knowledge.deleteExternalSuccess'));
      })
      .catch((err) => {
        toast.error('Failed to delete KB: ' + err.message);
      });
  }

  /**
   * Get retriever label with i18n support
   */
  function getRetrieverLabel(fullName: string): string {
    const retriever = availableRetrievers.find(
      (r) =>
        `${r.plugin_author}/${r.plugin_name}/${r.retriever_name}` === fullName,
    );
    return retriever?.manifest?.manifest?.metadata?.label
      ? extractI18nObject(retriever.manifest.manifest.metadata.label)
      : fullName;
  }

  // Compute full retriever name for display
  const currentRetrieverFullName =
    form.watch('plugin_author') &&
    form.watch('plugin_name') &&
    form.watch('retriever_name')
      ? `${form.watch('plugin_author')}/${form.watch(
          'plugin_name',
        )}/${form.watch('retriever_name')}`
      : '';

  return (
    <div>
      {/* Delete Confirmation Dialog */}
      <Dialog
        open={showDeleteConfirmModal}
        onOpenChange={setShowDeleteConfirmModal}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
          </DialogHeader>
          <DialogDescription>
            {t('knowledge.deleteConfirmation')}
          </DialogDescription>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteConfirmModal(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                handleDelete();
                setShowDeleteConfirmModal(false);
              }}
            >
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Main Form */}
      <Form {...form}>
        <form
          id="external-kb-form"
          onSubmit={form.handleSubmit(handleFormSubmit)}
          className="space-y-8"
        >
          <div className="space-y-4">
            {/* KB Name */}
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

            {/* KB Description */}
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

            {/* Retriever Selector */}
            <FormField
              control={form.control}
              name="retriever_name"
              render={() => (
                <FormItem>
                  <FormLabel>
                    {t('knowledge.retriever')}
                    <span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <Select
                      onValueChange={handleRetrieverSelect}
                      value={currentRetrieverFullName}
                    >
                      <SelectTrigger className="w-full bg-[#ffffff] dark:bg-[#2a2a2e]">
                        <SelectValue
                          placeholder={t('knowledge.selectRetriever')}
                        />
                      </SelectTrigger>
                      <SelectContent className="fixed z-[1000]">
                        <SelectGroup>
                          {availableRetrievers.map((retriever) => {
                            const fullName = `${retriever.plugin_author}/${retriever.plugin_name}/${retriever.retriever_name}`;
                            const label = retriever.manifest?.manifest?.metadata
                              ?.label
                              ? extractI18nObject(
                                  retriever.manifest.manifest.metadata.label,
                                )
                              : retriever.retriever_name;
                            const description = extractI18nObject(
                              retriever.retriever_description,
                            );

                            return (
                              <HoverCard
                                key={fullName}
                                openDelay={0}
                                closeDelay={0}
                              >
                                <HoverCardTrigger asChild>
                                  <SelectItem value={fullName}>
                                    {label}
                                  </SelectItem>
                                </HoverCardTrigger>
                                <HoverCardContent
                                  className="w-80 data-[state=open]:animate-none"
                                  align="end"
                                  side="right"
                                  sideOffset={10}
                                >
                                  <div className="space-y-2">
                                    <div className="flex items-start gap-3">
                                      <div className="w-10 h-10 rounded-[8%] bg-gray-200 dark:bg-gray-700 flex items-center justify-center flex-shrink-0">
                                        <svg
                                          className="w-5 h-5 text-gray-400"
                                          fill="none"
                                          stroke="currentColor"
                                          viewBox="0 0 24 24"
                                        >
                                          <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                                          />
                                        </svg>
                                      </div>
                                      <div className="flex flex-col gap-1 flex-1 min-w-0">
                                        <h4 className="font-medium text-sm">
                                          {label}
                                        </h4>
                                        <p className="text-xs text-muted-foreground">
                                          {retriever.plugin_author} /{' '}
                                          {retriever.plugin_name}
                                        </p>
                                      </div>
                                    </div>
                                    {description && (
                                      <p className="text-sm text-muted-foreground">
                                        {description}
                                      </p>
                                    )}
                                  </div>
                                </HoverCardContent>
                              </HoverCard>
                            );
                          })}
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Selected Retriever Card */}
            {currentRetrieverFullName && (
              <div className="flex items-start gap-3 p-4 rounded-lg border">
                <div className="w-12 h-12 rounded-[8%] bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
                  <svg
                    className="w-6 h-6 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                    />
                  </svg>
                </div>
                <div className="flex flex-col gap-1">
                  <div className="font-medium">
                    {getRetrieverLabel(currentRetrieverFullName)}
                  </div>
                  <div className="text-sm text-gray-500">
                    {form.watch('plugin_author')} / {form.watch('plugin_name')}
                  </div>
                </div>
              </div>
            )}

            {/* Dynamic Retriever Configuration Form */}
            {showDynamicForm && dynamicFormConfigList.length > 0 && (
              <div className="space-y-4">
                <div className="text-lg font-medium">
                  {t('knowledge.retrieverConfiguration')}
                </div>
                <DynamicFormComponent
                  itemConfigList={dynamicFormConfigList}
                  initialValues={form.watch('retriever_config')}
                  onSubmit={(values) => {
                    form.setValue('retriever_config', values);
                  }}
                />
              </div>
            )}
          </div>
        </form>
      </Form>
    </div>
  );
}
