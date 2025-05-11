import { useEffect, useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Pipeline } from '@/app/infra/entities/api';
import {
  PipelineFormEntity,
  PipelineConfigTab,
  PipelineConfigStage,
} from '@/app/infra/entities/pipeline';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
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
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';

export default function PipelineFormComponent({
  initValues,
  isDefaultPipeline,
  onFinish,
  onNewPipelineCreated,
  isEditMode,
  pipelineId,
}: {
  pipelineId?: string;
  isDefaultPipeline: boolean;
  isEditMode: boolean;
  disableForm: boolean;
  // 这里的写法很不安全不规范，未来流水线需要重新整理
  initValues?: PipelineFormEntity;
  onFinish: () => void;
  onNewPipelineCreated: (pipelineId: string) => void;
}) {
  const formSchema = isEditMode
    ? z.object({
        basic: z.object({
          name: z.string().min(1, { message: '名称不能为空' }),
          description: z.string().min(1, { message: '描述不能为空' }),
        }),
        ai: z.record(z.string(), z.any()),
        trigger: z.record(z.string(), z.any()),
        safety: z.record(z.string(), z.any()),
        output: z.record(z.string(), z.any()),
      })
    : z.object({
        basic: z.object({
          name: z.string().min(1, { message: '名称不能为空' }),
          description: z.string().min(1, { message: '描述不能为空' }),
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
        { label: '基础信息', name: 'basic' },
        { label: 'AI能力', name: 'ai' },
        { label: '触发条件', name: 'trigger' },
        { label: '安全能力', name: 'safety' },
        { label: '输出处理', name: 'output' },
      ]
    : [{ label: '基础信息', name: 'basic' }];
  // const [basicForm] = Form.useForm();
  // const [aiForm] = Form.useForm();
  // const [triggerForm] = Form.useForm();
  // const [safetyForm] = Form.useForm();
  // const [outputForm] = Form.useForm();
  const [aiConfigTabSchema, setAIConfigTabSchema] =
    useState<PipelineConfigTab>();
  const [triggerConfigTabSchema, setTriggerConfigTabSchema] =
    useState<PipelineConfigTab>();
  const [safetyConfigTabSchema, setSafetyConfigTabSchema] =
    useState<PipelineConfigTab>();
  const [outputConfigTabSchema, setOutputConfigTabSchema] =
    useState<PipelineConfigTab>();
  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState(false);

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
  }, []);

  useEffect(() => {
    if (initValues) {
      form.reset(initValues);
    }

    if (!isEditMode) {
      form.reset({
        basic: {
          name: '',
          description: '',
        },
      });
    }
  }, [initValues, form, isEditMode]);

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
        toast.success('创建成功 请编辑流水线详细参数');
      })
      .catch((err) => {
        toast.error('创建失败：' + err.message);
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
        toast.success('保存成功');
      })
      .catch((err) => {
        toast.error('保存失败：' + err.message);
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
            <div className="text-lg font-medium">{stage.label.zh_CN}</div>
            {stage.description && (
              <div className="text-sm text-gray-500">
                {stage.description.zh_CN}
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
    }

    return (
      <div key={stage.name} className="space-y-4 mb-6">
        <div className="text-lg font-medium">{stage.label.zh_CN}</div>
        {stage.description && (
          <div className="text-sm text-gray-500">{stage.description.zh_CN}</div>
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

  function deletePipeline() {
    httpClient
      .deletePipeline(pipelineId || '')
      .then(() => {
        onFinish();
        toast.success('删除成功');
      })
      .catch((err) => {
        toast.error('删除失败：' + err.message);
      });
  }

  return (
    <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
      <Dialog
        open={showDeleteConfirmModal}
        onOpenChange={setShowDeleteConfirmModal}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除确认</DialogTitle>
          </DialogHeader>
          <DialogDescription>
            你确定要删除这个流水线吗？已绑定此流水线的机器人将无法使用。
          </DialogDescription>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteConfirmModal(false)}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                deletePipeline();
                setShowDeleteConfirmModal(false);
              }}
            >
              确认删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(handleFormSubmit)}>
          <Tabs defaultValue={formLabelList[0].name}>
            <TabsList>
              {formLabelList.map((formLabel) => (
                <TabsTrigger key={formLabel.name} value={formLabel.name}>
                  {formLabel.label}
                </TabsTrigger>
              ))}
            </TabsList>

            {formLabelList.map((formLabel) => (
              <TabsContent
                key={formLabel.name}
                value={formLabel.name}
                className="pr-6"
              >
                <h1 className="text-xl font-bold mb-4">{formLabel.label}</h1>

                {formLabel.name === 'basic' && (
                  <div className="space-y-6">
                    <FormField
                      control={form.control}
                      name="basic.name"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>
                            名称<span className="text-red-500">*</span>
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
                            描述<span className="text-red-500">*</span>
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

                    {formLabel.name === 'trigger' && triggerConfigTabSchema && (
                      <div className="space-y-6">
                        {triggerConfigTabSchema.stages.map((stage) =>
                          renderDynamicForms(stage, 'trigger'),
                        )}
                      </div>
                    )}

                    {formLabel.name === 'safety' && safetyConfigTabSchema && (
                      <div className="space-y-6">
                        {safetyConfigTabSchema.stages.map((stage) =>
                          renderDynamicForms(stage, 'safety'),
                        )}
                      </div>
                    )}

                    {formLabel.name === 'output' && outputConfigTabSchema && (
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
          </Tabs>

          <div className="sticky bottom-0 left-0 right-0 bg-background border-t p-4 mt-4">
            <div className="flex justify-end items-center gap-2">
              {isEditMode && isDefaultPipeline && (
                <span className="text-gray-500 text-[0.7rem]">
                  默认流水线不可删除
                </span>
              )}

              {isEditMode && !isDefaultPipeline && (
                <Button
                  type="button"
                  variant="destructive"
                  onClick={() => {
                    setShowDeleteConfirmModal(true);
                  }}
                  className="cursor-pointer"
                >
                  删除
                </Button>
              )}

              <Button type="submit" className="cursor-pointer">
                {isEditMode ? '保存' : '提交'}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={onFinish}
                className="cursor-pointer"
              >
                取消
              </Button>
            </div>
          </div>
        </form>
      </Form>
    </div>
  );
}

interface FormLabel {
  label: string;
  name: string;
}
