import { useEffect, useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { GetPipelineResponseData, Pipeline } from '@/app/infra/entities/api';
import {
  PipelineConfigTab,
  PipelineConfigStage,
} from '@/app/infra/entities/pipeline';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import N8nAuthFormComponent from '@/app/home/components/dynamic-form/N8nAuthFormComponent';
import { Button } from '@/components/ui/button';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Input } from '@/components/ui/input';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { i18nObj } from '@/i18n/I18nProvider';

export default function PipelineFormComponent({
  isDefaultPipeline,
  onFinish,
  onNewPipelineCreated,
  isEditMode,
  pipelineId,
  showButtons = true,
  onDeletePipeline,
  onCancel,
}: {
  pipelineId?: string;
  isDefaultPipeline: boolean;
  isEditMode: boolean;
  disableForm: boolean;
  showButtons?: boolean;
  onFinish: () => void;
  onNewPipelineCreated: (pipelineId: string) => void;
  onDeletePipeline: () => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const formSchema = isEditMode
    ? z.object({
        basic: z.object({
          name: z.string().min(1, { message: t('pipelines.nameRequired') }),
          description: z
            .string()
            .min(1, { message: t('pipelines.descriptionRequired') }),
        }),
        ai: z.record(z.string(), z.any()),
        trigger: z.record(z.string(), z.any()),
        safety: z.record(z.string(), z.any()),
        output: z.record(z.string(), z.any()),
      })
    : z.object({
        basic: z.object({
          name: z.string().min(1, { message: t('pipelines.nameRequired') }),
          description: z
            .string()
            .min(1, { message: t('pipelines.descriptionRequired') }),
        }),
        ai: z.record(z.string(), z.any()).optional(),
        trigger: z.record(z.string(), z.any()).optional(),
        safety: z.record(z.string(), z.any()).optional(),
        output: z.record(z.string(), z.any()).optional(),
      });

  type FormValues = z.infer<typeof formSchema>;
  // 这里不好，可以改成enum等
  const formLabelList: FormLabel[] = isEditMode
    ? [
        { label: t('pipelines.basicInfo'), name: 'basic' },
        { label: t('pipelines.aiCapabilities'), name: 'ai' },
        { label: t('pipelines.triggerConditions'), name: 'trigger' },
        { label: t('pipelines.safetyControls'), name: 'safety' },
        { label: t('pipelines.outputProcessing'), name: 'output' },
      ]
    : [{ label: t('pipelines.basicInfo'), name: 'basic' }];

  const [aiConfigTabSchema, setAIConfigTabSchema] =
    useState<PipelineConfigTab>();
  const [triggerConfigTabSchema, setTriggerConfigTabSchema] =
    useState<PipelineConfigTab>();
  const [safetyConfigTabSchema, setSafetyConfigTabSchema] =
    useState<PipelineConfigTab>();
  const [outputConfigTabSchema, setOutputConfigTabSchema] =
    useState<PipelineConfigTab>();

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      basic: {},
      ai: {},
      trigger: {},
      safety: {},
      output: {},
    },
  });

  useEffect(() => {
    // get config schema from metadata
    httpClient.getGeneralPipelineMetadata().then((resp) => {
      for (const config of resp.configs) {
        if (config.name === 'ai') {
          setAIConfigTabSchema(config);
        } else if (config.name === 'trigger') {
          setTriggerConfigTabSchema(config);
        } else if (config.name === 'safety') {
          setSafetyConfigTabSchema(config);
        } else if (config.name === 'output') {
          setOutputConfigTabSchema(config);
        }
      }
    });

    if (isEditMode) {
      httpClient
        .getPipeline(pipelineId || '')
        .then((resp: GetPipelineResponseData) => {
          form.reset({
            basic: {
              name: resp.pipeline.name,
              description: resp.pipeline.description,
            },
            ai: resp.pipeline.config.ai,
            trigger: resp.pipeline.config.trigger,
            safety: resp.pipeline.config.safety,
            output: resp.pipeline.config.output,
          });
        });
    }
  }, []);

  useEffect(() => {
    if (!isEditMode) {
      form.reset({
        basic: {
          name: '',
          description: '',
        },
      });
    }
  }, [form, isEditMode]);

  function handleFormSubmit(values: FormValues) {
    console.log('handleFormSubmit', values);
    if (isEditMode) {
      handleModify(values);
    } else {
      handleCreate(values);
    }
  }

  function handleCreate(values: FormValues) {
    console.log('handleCreate', values);
    const pipeline: Pipeline = {
      config: {},
      description: values.basic.description,
      name: values.basic.name,
    };
    httpClient
      .createPipeline(pipeline)
      .then((resp) => {
        onFinish();
        onNewPipelineCreated(resp.uuid);
        toast.success(t('pipelines.createSuccess'));
      })
      .catch((err) => {
        toast.error(t('pipelines.createError') + err.message);
      });
  }

  function handleModify(values: FormValues) {
    const realConfig = {
      ai: values.ai,
      trigger: values.trigger,
      safety: values.safety,
      output: values.output,
    };

    const pipeline: Pipeline = {
      config: realConfig,
      // created_at: '',
      description: values.basic.description,
      // for_version: '',
      name: values.basic.name,
      // stages: [],
      // updated_at: '',
      // uuid: pipelineId || '',
      // is_default: false,
    };
    httpClient
      .updatePipeline(pipelineId || '', pipeline)
      .then(() => {
        onFinish();
        toast.success(t('pipelines.saveSuccess'));
      })
      .catch((err) => {
        toast.error(t('pipelines.saveError') + err.message);
      });
  }

  function renderDynamicForms(
    stage: PipelineConfigStage,
    formName: keyof FormValues,
  ) {
    // 如果是 AI 配置，需要特殊处理
    if (formName === 'ai') {
      // 获取当前选择的 runner
      const currentRunner = form.watch('ai.runner.runner');

      // 如果是 runner 配置项，直接渲染
      if (stage.name === 'runner') {
        return (
          <div key={stage.name} className="space-y-4 mb-6">
            <div className="text-lg font-medium">{i18nObj(stage.label)}</div>
            {stage.description && (
              <div className="text-sm text-gray-500">
                {i18nObj(stage.description)}
              </div>
            )}
            <DynamicFormComponent
              itemConfigList={stage.config}
              initialValues={
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                (form.watch(formName) as Record<string, any>)?.[stage.name] ||
                {}
              }
              onSubmit={(values) => {
                const currentValues =
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  (form.getValues(formName) as Record<string, any>) || {};
                form.setValue(formName, {
                  ...currentValues,
                  [stage.name]: values,
                });
              }}
            />
          </div>
        );
      }

      // 如果不是当前选择的 runner 对应的配置项，则不渲染
      if (stage.name !== currentRunner) {
        return null;
      }

      // 对于n8n-service-api配置，使用N8nAuthFormComponent处理表单联动
      if (stage.name === 'n8n-service-api') {
        return (
          <div key={stage.name} className="space-y-4 mb-6">
            <div className="text-lg font-medium">{i18nObj(stage.label)}</div>
            {stage.description && (
              <div className="text-sm text-gray-500">
                {i18nObj(stage.description)}
              </div>
            )}
            <N8nAuthFormComponent
              itemConfigList={stage.config}
              initialValues={
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                (form.watch(formName) as Record<string, any>)?.[stage.name] ||
                {}
              }
              onSubmit={(values) => {
                const currentValues =
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  (form.getValues(formName) as Record<string, any>) || {};
                form.setValue(formName, {
                  ...currentValues,
                  [stage.name]: values,
                });
              }}
            />
          </div>
        );
      }
    }

    return (
      <div key={stage.name} className="space-y-4 mb-6">
        <div className="text-lg font-medium">{i18nObj(stage.label)}</div>
        {stage.description && (
          <div className="text-sm text-gray-500">
            {i18nObj(stage.description)}
          </div>
        )}
        <DynamicFormComponent
          itemConfigList={stage.config}
          initialValues={
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            (form.watch(formName) as Record<string, any>)?.[stage.name] || {}
          }
          onSubmit={(values) => {
            const currentValues =
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              (form.getValues(formName) as Record<string, any>) || {};
            form.setValue(formName, {
              ...currentValues,
              [stage.name]: values,
            });
          }}
        />
      </div>
    );
  }

  const handleDelete = () => {
    setShowDeleteConfirm(true);
  };

  const confirmDelete = () => {
    if (pipelineId) {
      httpClient
        .deletePipeline(pipelineId)
        .then(() => {
          onDeletePipeline();
          setShowDeleteConfirm(false);
          toast.success(t('pipelines.deleteSuccess'));
        })
        .catch((err) => {
          toast.error(t('pipelines.deleteError') + err.message);
        });
    }
  };

  return (
    <>
      <div className="!max-w-[70vw] max-w-6xl h-full p-0 flex flex-col bg-white">
        <Form {...form}>
          <form
            id="pipeline-form"
            onSubmit={form.handleSubmit(handleFormSubmit)}
            className="h-full flex flex-col flex-1 min-h-0 mb-2"
          >
            <div className="flex-1 flex flex-col min-h-0">
              <Tabs
                defaultValue={formLabelList[0].name}
                className="h-full flex flex-col flex-1 min-h-0"
              >
                <TabsList>
                  {formLabelList.map((formLabel) => (
                    <TabsTrigger key={formLabel.name} value={formLabel.name}>
                      {formLabel.label}
                    </TabsTrigger>
                  ))}
                </TabsList>

                <div
                  id="pipeline-form-content"
                  className="flex-1 overflow-y-auto min-h-0"
                >
                  {formLabelList.map((formLabel) => (
                    <TabsContent
                      key={formLabel.name}
                      value={formLabel.name}
                      className="overflow-y-auto max-h-full"
                    >
                      {formLabel.name === 'basic' && (
                        <div className="space-y-6">
                          <FormField
                            control={form.control}
                            name="basic.name"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>
                                  {t('common.name')}
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
                            name="basic.description"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>
                                  {t('common.description')}
                                  <span className="text-red-500">*</span>
                                </FormLabel>
                                <FormControl>
                                  <Input {...field} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>
                      )}

                      {isEditMode && (
                        <>
                          {formLabel.name === 'ai' && aiConfigTabSchema && (
                            <div className="space-y-6">
                              {aiConfigTabSchema.stages.map((stage) =>
                                renderDynamicForms(stage, 'ai'),
                              )}
                            </div>
                          )}

                          {formLabel.name === 'trigger' &&
                            triggerConfigTabSchema && (
                              <div className="space-y-6">
                                {triggerConfigTabSchema.stages.map((stage) =>
                                  renderDynamicForms(stage, 'trigger'),
                                )}
                              </div>
                            )}

                          {formLabel.name === 'safety' &&
                            safetyConfigTabSchema && (
                              <div className="space-y-6">
                                {safetyConfigTabSchema.stages.map((stage) =>
                                  renderDynamicForms(stage, 'safety'),
                                )}
                              </div>
                            )}

                          {formLabel.name === 'output' &&
                            outputConfigTabSchema && (
                              <div className="space-y-6">
                                {outputConfigTabSchema.stages.map((stage) =>
                                  renderDynamicForms(stage, 'output'),
                                )}
                              </div>
                            )}
                        </>
                      )}
                    </TabsContent>
                  ))}
                </div>
              </Tabs>
            </div>
          </form>
          {/* 按钮栏移到 Tabs 外部，始终固定底部 */}
          {showButtons && (
            <div className="flex justify-end gap-2 pt-4 border-t mb-0 bg-white sticky bottom-0 z-10">
              {isEditMode && !isDefaultPipeline && (
                <Button
                  type="button"
                  variant="destructive"
                  onClick={handleDelete}
                >
                  {t('common.delete')}
                </Button>
              )}

              {isEditMode && isDefaultPipeline && (
                <div className="text-gray-500 text-sm h-full flex items-center mr-2">
                  {t('pipelines.defaultPipelineCannotDelete')}
                </div>
              )}
              <Button type="submit" form="pipeline-form">
                {isEditMode ? t('common.save') : t('common.submit')}
              </Button>
              <Button type="button" variant="outline" onClick={onCancel}>
                {t('common.cancel')}
              </Button>
            </div>
          )}
        </Form>
      </div>

      {/* 删除确认对话框 */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
          </DialogHeader>
          <div className="py-4">{t('pipelines.deleteConfirmation')}</div>
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
interface FormLabel {
  label: string;
  name: string;
}
