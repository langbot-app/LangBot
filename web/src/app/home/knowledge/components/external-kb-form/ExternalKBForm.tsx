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
import { Textarea } from '@/components/ui/textarea';
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

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('knowledge.nameRequired') }),
    description: z.string().optional(),
    plugin_author: z.string().min(1, { message: 'Please select a retriever' }),
    plugin_name: z.string().min(1, { message: 'Please select a retriever' }),
    retriever_name: z.string().min(1, { message: 'Please select a retriever' }),
    retriever_config: z.record(z.string(), z.any()),
  });

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

export default function ExternalKBForm({
  initKBId,
  onFormSubmit,
  onKBDeleted,
  onNewKBCreated,
}: {
  initKBId?: string;
  onFormSubmit: (value: z.infer<ReturnType<typeof getFormSchema>>) => void;
  onKBDeleted: () => void;
  onNewKBCreated: (kbId: string) => void;
}) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

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
  const [, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    setKBFormValues();
  }, []);

  function setKBFormValues() {
    initKBFormComponent().then(() => {
      if (initKBId) {
        getKBConfig(initKBId)
          .then((val) => {
            form.setValue('name', val.name);
            form.setValue('description', val.description || '');
            form.setValue('plugin_author', val.plugin_author);
            form.setValue('plugin_name', val.plugin_name);
            form.setValue('retriever_name', val.retriever_name);
            form.setValue('retriever_config', val.retriever_config);
            const fullName = `${val.plugin_author}/${val.plugin_name}/${val.retriever_name}`;
            handleRetrieverSelect(fullName);
          })
          .catch((err) => {
            toast.error('Failed to load KB config: ' + err.message);
          });
      } else {
        form.reset();
      }
    });
  }

  async function initKBFormComponent() {
    // Load available retrievers
    const retrieversRes = await httpClient.listKnowledgeRetrievers();
    console.log('Available retrievers', retrieversRes);
    setAvailableRetrievers(retrieversRes.retrievers || []);

    // Build retriever name to config map
    const configMap = new Map<string, IDynamicFormItemSchema[]>();
    retrieversRes.retrievers?.forEach((retriever: RetrieverInfo) => {
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
            }),
        ),
      );
    });
    setRetrieverNameToConfigMap(configMap);
  }

  async function getKBConfig(
    kbId: string,
  ): Promise<z.infer<typeof formSchema>> {
    return new Promise((resolve, reject) => {
      httpClient
        .getExternalKnowledgeBase(kbId)
        .then((res) => {
          const kb = res.base;
          resolve({
            name: kb.name,
            description: kb.description,
            plugin_author: kb.plugin_author,
            plugin_name: kb.plugin_name,
            retriever_name: kb.retriever_name,
            retriever_config: kb.retriever_config || {},
          });
        })
        .catch((err) => {
          reject(err);
        });
    });
  }

  function handleRetrieverSelect(fullRetrieverName: string) {
    if (fullRetrieverName) {
      // Parse fullRetrieverName: plugin_author/plugin_name/retriever_name
      const parts = fullRetrieverName.split('/');
      if (parts.length === 3) {
        // Only update form fields if not loading from existing KB
        if (!initKBId) {
          form.setValue('plugin_author', parts[0]);
          form.setValue('plugin_name', parts[1]);
          form.setValue('retriever_name', parts[2]);
        }
      }

      const dynamicFormConfigList =
        retrieverNameToConfigMap.get(fullRetrieverName);
      if (dynamicFormConfigList && dynamicFormConfigList.length > 0) {
        setDynamicFormConfigList(dynamicFormConfigList);
        if (!initKBId) {
          form.setValue(
            'retriever_config',
            getDefaultValues(dynamicFormConfigList),
          );
        }
        setShowDynamicForm(true);
      } else {
        setShowDynamicForm(false);
        if (!initKBId) {
          form.setValue('retriever_config', {});
        }
      }
    } else {
      setShowDynamicForm(false);
    }
  }

  function onDynamicFormSubmit(value: object) {
    setIsLoading(true);
    if (initKBId) {
      // Update
      const updateKB: ExternalKnowledgeBase = {
        uuid: initKBId,
        name: form.getValues().name,
        description: form.getValues().description || '',
        plugin_author: form.getValues().plugin_author,
        plugin_name: form.getValues().plugin_name,
        retriever_name: form.getValues().retriever_name,
        retriever_config: form.getValues().retriever_config,
      };
      httpClient
        .updateExternalKnowledgeBase(initKBId, updateKB)
        .then((res) => {
          console.log('Update KB success', res);
          onFormSubmit(form.getValues());
          toast.success(t('knowledge.updateExternalSuccess'));
        })
        .catch((err) => {
          toast.error('Failed to update KB: ' + err.message);
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      // Create
      const newKB: ExternalKnowledgeBase = {
        name: form.getValues().name,
        description: form.getValues().description || '',
        plugin_author: form.getValues().plugin_author,
        plugin_name: form.getValues().plugin_name,
        retriever_name: form.getValues().retriever_name,
        retriever_config: form.getValues().retriever_config,
      };
      httpClient
        .createExternalKnowledgeBase(newKB)
        .then((res) => {
          console.log('Create KB success', res);
          toast.success(t('knowledge.createExternalSuccess'));
          initKBId = res.uuid;
          setKBFormValues();
          onNewKBCreated(res.uuid);
        })
        .catch((err) => {
          toast.error('Failed to create KB: ' + err.message);
        })
        .finally(() => {
          setIsLoading(false);
          form.reset();
        });
    }
  }

  function deleteKB() {
    if (initKBId) {
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
  }

  const getRetrieverLabel = (fullName: string) => {
    const retriever = availableRetrievers.find(
      (r) =>
        `${r.plugin_author}/${r.plugin_name}/${r.retriever_name}` === fullName,
    );
    return retriever?.manifest?.manifest?.metadata?.label
      ? extractI18nObject(retriever.manifest.manifest.metadata.label)
      : fullName;
  };

  const getRetrieverDisplayName = (fullName: string) => {
    const retriever = availableRetrievers.find(
      (r) =>
        `${r.plugin_author}/${r.plugin_name}/${r.retriever_name}` === fullName,
    );
    return retriever
      ? `${retriever.plugin_name}/${retriever.retriever_name}`
      : fullName;
  };

  const getRetrieverDescription = (fullName: string) => {
    const retriever = availableRetrievers.find(
      (r) =>
        `${r.plugin_author}/${r.plugin_name}/${r.retriever_name}` === fullName,
    );
    return retriever ? extractI18nObject(retriever.retriever_description) : '';
  };

  return (
    <div>
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
                deleteKB();
                setShowDeleteConfirmModal(false);
              }}
            >
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Form {...form}>
        <form
          id="external-kb-form"
          onSubmit={form.handleSubmit(onDynamicFormSubmit)}
          className="space-y-8"
        >
          <div className="space-y-4">
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

            <FormField
              control={form.control}
              name="retriever_name"
              render={({ field }) => {
                // Compute the full retriever name for display
                const fullRetrieverName =
                  form.watch('plugin_author') &&
                  form.watch('plugin_name') &&
                  form.watch('retriever_name')
                    ? `${form.watch('plugin_author')}/${form.watch(
                        'plugin_name',
                      )}/${form.watch('retriever_name')}`
                    : '';

                return (
                  <FormItem>
                    <FormLabel>
                      {t('knowledge.retriever')}
                      <span className="text-red-500">*</span>
                    </FormLabel>
                    <FormControl>
                      <div className="relative">
                        <Select
                          onValueChange={(value) => {
                            handleRetrieverSelect(value);
                          }}
                          value={fullRetrieverName}
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
                                const label = retriever.manifest?.manifest
                                  ?.metadata?.label
                                  ? extractI18nObject(
                                      retriever.manifest.manifest.metadata
                                        .label,
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
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                );
              }}
            />

            {/* Retriever Card */}
            {form.watch('retriever_name') &&
              form.watch('plugin_author') &&
              form.watch('plugin_name') && (
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
                      {getRetrieverLabel(
                        `${form.watch('plugin_author')}/${form.watch(
                          'plugin_name',
                        )}/${form.watch('retriever_name')}`,
                      )}
                    </div>
                    <div className="text-sm text-gray-500">
                      {form.watch('plugin_author')} /{' '}
                      {form.watch('plugin_name')}
                    </div>
                  </div>
                </div>
              )}

            {/* Dynamic Form for Retriever Config */}
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
