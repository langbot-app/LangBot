import { useEffect, useRef, useState, useMemo } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { GetPipelineResponseData, Pipeline } from '@/app/infra/entities/api';
import {
  PipelineConfigTab,
  PipelineConfigStage,
} from '@/app/infra/entities/pipeline';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import N8nAuthFormComponent from '@/app/home/components/dynamic-form/N8nAuthFormComponent';
import { Button } from '@/components/ui/button';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Input } from '@/components/ui/input';
import EmojiPicker from '@/components/ui/emoji-picker';
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
import { extractI18nObject } from '@/i18n/I18nProvider';
import { cn } from '@/lib/utils';
import { Info, Brain, Zap, Shield, FileOutput } from 'lucide-react';

export default function PipelineFormComponent({
  onFinish,
  onNewPipelineCreated,
  isEditMode,
  pipelineId,
  showButtons = true,
  onDeletePipeline,
  onCancel,
}: {
  pipelineId?: string;
  isEditMode: boolean;
  disableForm: boolean;
  showButtons?: boolean;
  onFinish: () => void;
  onNewPipelineCreated: (pipelineId: string) => void;
  onDeletePipeline: () => void;
  onCancel?: () => void;
}) {
  const { t } = useTranslation();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showCopyConfirm, setShowCopyConfirm] = useState(false);
  const [isDefaultPipeline, setIsDefaultPipeline] = useState<boolean>(false);

  const formSchema = isEditMode
    ? z.object({
        basic: z.object({
          name: z.string().min(1, { message: t('pipelines.nameRequired') }),
          description: z
            .string()
            .min(1, { message: t('pipelines.descriptionRequired') }),
          emoji: z.string().optional(),
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
          emoji: z.string().optional(),
        }),
        ai: z.record(z.string(), z.any()).optional(),
        trigger: z.record(z.string(), z.any()).optional(),
        safety: z.record(z.string(), z.any()).optional(),
        output: z.record(z.string(), z.any()).optional(),
      });

  type FormValues = z.infer<typeof formSchema>;
  // Section navigation items with icons
  const SECTION_ICONS: Record<string, React.ElementType> = {
    basic: Info,
    ai: Brain,
    trigger: Zap,
    safety: Shield,
    output: FileOutput,
  };

  const formLabelList: SectionItem[] = isEditMode
    ? [
        {
          label: t('pipelines.basicInfo'),
          name: 'basic',
          icon: SECTION_ICONS.basic,
        },
        {
          label: t('pipelines.aiCapabilities'),
          name: 'ai',
          icon: SECTION_ICONS.ai,
        },
        {
          label: t('pipelines.triggerConditions'),
          name: 'trigger',
          icon: SECTION_ICONS.trigger,
        },
        {
          label: t('pipelines.safetyControls'),
          name: 'safety',
          icon: SECTION_ICONS.safety,
        },
        {
          label: t('pipelines.outputProcessing'),
          name: 'output',
          icon: SECTION_ICONS.output,
        },
      ]
    : [
        {
          label: t('pipelines.basicInfo'),
          name: 'basic',
          icon: SECTION_ICONS.basic,
        },
      ];

  const [activeSection, setActiveSection] = useState(formLabelList[0].name);

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
      basic: {
        emoji: '⚙️',
      },
      ai: {},
      trigger: {},
      safety: {},
      output: {},
    },
  });

  // Track unsaved changes by comparing current form values against a saved snapshot
  const savedSnapshotRef = useRef<string>('');
  // Track which dynamic form stages have completed their initial mount emission.
  const initializedStagesRef = useRef<Set<string>>(new Set());
  const watchedValues = form.watch();
  const hasUnsavedChanges = useMemo(() => {
    if (!isEditMode || !savedSnapshotRef.current) return false;
    return JSON.stringify(watchedValues) !== savedSnapshotRef.current;
  }, [isEditMode, watchedValues]);

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
          setIsDefaultPipeline(resp.pipeline.is_default ?? false);
          const loadedValues = {
            basic: {
              name: resp.pipeline.name,
              description: resp.pipeline.description,
              emoji: resp.pipeline.emoji || '⚙️',
            },
            ai: resp.pipeline.config.ai,
            trigger: resp.pipeline.config.trigger,
            safety: resp.pipeline.config.safety,
            output: resp.pipeline.config.output,
          };
          form.reset(loadedValues);
          savedSnapshotRef.current = JSON.stringify(loadedValues);
          initializedStagesRef.current.clear();
        });
    }
  }, []);

  useEffect(() => {
    if (!isEditMode) {
      form.reset({
        basic: {
          name: '',
          description: '',
          emoji: '⚙️',
        },
      });
    }
  }, [form, isEditMode]);

  function handleFormSubmit(values: FormValues) {
    if (isEditMode) {
      handleModify(values);
    } else {
      handleCreate(values);
    }
  }

  function handleCreate(values: FormValues) {
    const pipeline: Pipeline = {
      config: {},
      description: values.basic.description,
      name: values.basic.name,
      emoji: values.basic.emoji,
    };
    httpClient
      .createPipeline(pipeline)
      .then((resp) => {
        onFinish();
        onNewPipelineCreated(resp.uuid);
        toast.success(t('pipelines.createSuccess'));
      })
      .catch((err) => {
        toast.error(t('pipelines.createError') + err.msg);
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
      emoji: values.basic.emoji,
      // stages: [],
      // updated_at: '',
      // uuid: pipelineId || '',
      // is_default: false,
    };
    httpClient
      .updatePipeline(pipelineId || '', pipeline)
      .then(() => {
        savedSnapshotRef.current = JSON.stringify(form.getValues());
        onFinish();
        toast.success(t('pipelines.saveSuccess'));
      })
      .catch((err) => {
        toast.error(t('pipelines.saveError') + err.msg);
      });
  }

  // Called from DynamicFormComponent/N8nAuthFormComponent onSubmit callbacks.
  // On the first emission for a stage (mount-time default filling), the
  // snapshot is synchronously re-captured so that hasUnsavedChanges stays false.
  function handleDynamicFormEmit(
    formName: keyof FormValues,
    stageName: string,
    values: object,
  ) {
    const stageKey = `${String(formName)}.${stageName}`;
    const isFirstEmission = !initializedStagesRef.current.has(stageKey);

    const currentValues =
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (form.getValues(formName) as Record<string, any>) || {};
    form.setValue(formName, {
      ...currentValues,
      [stageName]: values,
    });

    if (isFirstEmission) {
      initializedStagesRef.current.add(stageKey);
      // Synchronously re-capture snapshot so that the useMemo comparison
      // in the same render cycle still returns false.
      savedSnapshotRef.current = JSON.stringify(form.getValues());
    }
  }

  function renderDynamicForms(
    stage: PipelineConfigStage,
    formName: keyof FormValues,
  ) {
    // Special handling for AI config section
    if (formName === 'ai') {
      // Get the currently selected runner
      const currentRunner = form.watch('ai.runner.runner');

      // If this is the runner selector stage, render it directly
      if (stage.name === 'runner') {
        return (
          <div key={stage.name} className="space-y-4 mb-6">
            <div className="text-lg font-medium">
              {extractI18nObject(stage.label)}
            </div>
            {stage.description && (
              <div className="text-sm text-muted-foreground">
                {extractI18nObject(stage.description)}
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
                handleDynamicFormEmit(formName, stage.name, values);
              }}
            />
          </div>
        );
      }

      // Do not render if not the currently selected runner
      if (stage.name !== currentRunner) {
        return null;
      }

      // For n8n-service-api config, use N8nAuthFormComponent for form linkage
      if (stage.name === 'n8n-service-api') {
        return (
          <div key={stage.name} className="space-y-4 mb-6">
            <div className="text-lg font-medium">
              {extractI18nObject(stage.label)}
            </div>
            {stage.description && (
              <div className="text-sm text-muted-foreground">
                {extractI18nObject(stage.description)}
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
                handleDynamicFormEmit(formName, stage.name, values);
              }}
            />
          </div>
        );
      }
    }

    return (
      <div key={stage.name} className="space-y-4 mb-6">
        <div className="text-lg font-medium">
          {extractI18nObject(stage.label)}
        </div>
        {stage.description && (
          <div className="text-sm text-muted-foreground">
            {extractI18nObject(stage.description)}
          </div>
        )}
        <DynamicFormComponent
          itemConfigList={stage.config}
          initialValues={
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            (form.watch(formName) as Record<string, any>)?.[stage.name] || {}
          }
          onSubmit={(values) => {
            handleDynamicFormEmit(formName, stage.name, values);
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
          toast.error(t('pipelines.deleteError') + err.msg);
        });
    }
  };

  const handleCopy = () => {
    setShowCopyConfirm(true);
  };

  const confirmCopy = () => {
    if (pipelineId) {
      httpClient
        .copyPipeline(pipelineId)
        .then(() => {
          onFinish();
          toast.success(t('common.copySuccess'));
          setShowCopyConfirm(false);
          onCancel?.();
        })
        .catch((err) => {
          toast.error(t('pipelines.createError') + err.msg);
        });
    }
  };

  return (
    <>
      <div className="h-full p-0 flex flex-col">
        <Form {...form}>
          <form
            id="pipeline-form"
            onSubmit={form.handleSubmit(handleFormSubmit)}
            className="h-full flex flex-col flex-1 min-h-0 mb-2"
          >
            <div className="flex-1 flex min-h-0">
              {/* Vertical section navigation (only show when multiple sections) */}
              {formLabelList.length > 1 && (
                <nav className="w-44 shrink-0 pr-4 mr-4 border-r overflow-y-auto">
                  <ul className="space-y-1">
                    {formLabelList.map((section) => {
                      const Icon = section.icon;
                      return (
                        <li key={section.name}>
                          <button
                            type="button"
                            onClick={() => setActiveSection(section.name)}
                            className={cn(
                              'w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors text-left',
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
              )}

              {/* Content panel */}
              <div className="flex-1 overflow-y-auto min-h-0">
                {/* Basic info section */}
                {activeSection === 'basic' && (
                  <div className="space-y-6">
                    {/* Name and Emoji in same row */}
                    <div className="flex gap-4 items-start">
                      <FormField
                        control={form.control}
                        name="basic.name"
                        render={({ field }) => (
                          <FormItem className="flex-1">
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

                {/* Dynamic config sections (edit mode only) */}
                {isEditMode && (
                  <>
                    {activeSection === 'ai' && aiConfigTabSchema && (
                      <div className="space-y-6">
                        {aiConfigTabSchema.stages.map((stage) =>
                          renderDynamicForms(stage, 'ai'),
                        )}
                      </div>
                    )}

                    {activeSection === 'trigger' && triggerConfigTabSchema && (
                      <div className="space-y-6">
                        {triggerConfigTabSchema.stages.map((stage) =>
                          renderDynamicForms(stage, 'trigger'),
                        )}
                      </div>
                    )}

                    {activeSection === 'safety' && safetyConfigTabSchema && (
                      <div className="space-y-6">
                        {safetyConfigTabSchema.stages.map((stage) =>
                          renderDynamicForms(stage, 'safety'),
                        )}
                      </div>
                    )}

                    {activeSection === 'output' && outputConfigTabSchema && (
                      <div className="space-y-6">
                        {outputConfigTabSchema.stages.map((stage) =>
                          renderDynamicForms(stage, 'output'),
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </form>
          {/* Button bar pinned to bottom */}
          {showButtons && (
            <div className="flex justify-end items-center gap-2 pt-4 border-t mb-0 sticky bottom-0 z-10">
              {isEditMode && hasUnsavedChanges && (
                <div className="text-amber-600 dark:text-amber-400 text-sm flex items-center gap-1.5 mr-auto">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500" />
                  {t('pipelines.unsavedChanges')}
                </div>
              )}

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
                <div className="text-muted-foreground text-sm h-full flex items-center mr-2">
                  {t('pipelines.defaultPipelineCannotDelete')}
                </div>
              )}

              {isEditMode && (
                <Button
                  type="button"
                  variant="default"
                  onClick={handleCopy}
                  className="bg-green-600 hover:bg-green-700 text-white"
                >
                  {t('common.copy')}
                </Button>
              )}

              <Button type="submit" form="pipeline-form">
                {isEditMode ? t('common.save') : t('common.submit')}
              </Button>
            </div>
          )}
        </Form>
      </div>

      {/* Delete confirmation dialog */}
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

      {/* Copy confirmation dialog */}
      <Dialog open={showCopyConfirm} onOpenChange={setShowCopyConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('pipelines.copyConfirmTitle')}</DialogTitle>
          </DialogHeader>
          <div className="py-4">{t('pipelines.copyConfirmation')}</div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCopyConfirm(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={confirmCopy}>{t('common.confirm')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
interface SectionItem {
  label: string;
  name: string;
  icon: React.ElementType;
}
