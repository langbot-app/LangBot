import React, { useEffect, useState } from 'react';
import {
  IChooseAdapterEntity,
  IPipelineEntity,
} from '@/app/home/bots/components/bot-form/ChooseEntity';
import {
  DynamicFormItemConfig,
  getDefaultValues,
  parseDynamicFormItemType,
} from '@/app/home/components/dynamic-form/DynamicFormItemConfig';
import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import { UUID } from 'uuidjs';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Bot } from '@/app/infra/entities/api';

import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

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
import { Switch } from '@/components/ui/switch';
import { extractI18nObject } from '@/i18n/I18nProvider';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('bots.botNameRequired') }),
    description: z
      .string()
      .min(1, { message: t('bots.botDescriptionRequired') }),
    adapter: z.string().min(1, { message: t('bots.adapterRequired') }),
    adapter_config: z.record(z.string(), z.any()),
    enable: z.boolean().optional(),
    use_pipeline_uuid: z.string().optional(),
  });

export default function BotForm({
  initBotId,
  onFormSubmit,
  onBotDeleted,
  onNewBotCreated,
}: {
  initBotId?: string;
  onFormSubmit: (value: z.infer<ReturnType<typeof getFormSchema>>) => void;
  onBotDeleted: () => void;
  onNewBotCreated: (botId: string) => void;
}) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: t('bots.defaultDescription'),
      adapter: '',
      adapter_config: {},
      enable: true,
      use_pipeline_uuid: '',
    },
  });

  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState(false);

  const [adapterNameToDynamicConfigMap, setAdapterNameToDynamicConfigMap] =
    useState(new Map<string, IDynamicFormItemSchema[]>());
  // const [form] = Form.useForm<IBotFormEntity>();
  const [showDynamicForm, setShowDynamicForm] = useState<boolean>(false);
  // const [dynamicForm] = Form.useForm();
  const [adapterNameList, setAdapterNameList] = useState<
    IChooseAdapterEntity[]
  >([]);
  const [adapterIconList, setAdapterIconList] = useState<
    Record<string, string>
  >({});
  const [adapterDescriptionList, setAdapterDescriptionList] = useState<
    Record<string, string>
  >({});

  const [pipelineNameList, setPipelineNameList] = useState<IPipelineEntity[]>(
    [],
  );

  const [dynamicFormConfigList, setDynamicFormConfigList] = useState<
    IDynamicFormItemSchema[]
  >([]);
  const [, setIsLoading] = useState<boolean>(false);
  const [webhookUrl, setWebhookUrl] = useState<string>('');
  const webhookInputRef = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    setBotFormValues();
  }, []);

  // 复制到剪贴板的辅助函数 - 使用页面上的真实input元素
  const copyToClipboard = () => {
    console.log('[Copy] Attempting to copy from input element');

    const inputElement = webhookInputRef.current;
    if (!inputElement) {
      console.error('[Copy] Input element not found');
      toast.error(t('common.copyFailed'));
      return;
    }

    try {
      // 确保input元素可见且未被禁用
      inputElement.disabled = false;
      inputElement.readOnly = false;

      // 聚焦并选中所有文本
      inputElement.focus();
      inputElement.select();

      // 尝试使用现代API
      if (navigator.clipboard && navigator.clipboard.writeText) {
        console.log(
          '[Copy] Using Clipboard API with input value:',
          inputElement.value,
        );
        navigator.clipboard
          .writeText(inputElement.value)
          .then(() => {
            console.log('[Copy] Clipboard API success');
            inputElement.blur(); // 取消选中
            inputElement.readOnly = true;
            toast.success(t('bots.webhookUrlCopied'));
          })
          .catch((err) => {
            console.error(
              '[Copy] Clipboard API failed, trying execCommand:',
              err,
            );
            // 降级到execCommand
            const successful = document.execCommand('copy');
            console.log('[Copy] execCommand result:', successful);
            inputElement.blur();
            inputElement.readOnly = true;
            if (successful) {
              toast.success(t('bots.webhookUrlCopied'));
            } else {
              toast.error(t('common.copyFailed'));
            }
          });
      } else {
        // 直接使用execCommand
        console.log(
          '[Copy] Using execCommand with input value:',
          inputElement.value,
        );
        const successful = document.execCommand('copy');
        console.log('[Copy] execCommand result:', successful);
        inputElement.blur();
        inputElement.readOnly = true;
        if (successful) {
          toast.success(t('bots.webhookUrlCopied'));
        } else {
          toast.error(t('common.copyFailed'));
        }
      }
    } catch (err) {
      console.error('[Copy] Copy failed:', err);
      inputElement.readOnly = true;
      toast.error(t('common.copyFailed'));
    }
  };

  function setBotFormValues() {
    initBotFormComponent().then(() => {
      // 拉取初始化表单信息
      if (initBotId) {
        getBotConfig(initBotId)
          .then((val) => {
            form.setValue('name', val.name);
            form.setValue('description', val.description);
            form.setValue('adapter', val.adapter);
            form.setValue('adapter_config', val.adapter_config);
            form.setValue('enable', val.enable);
            form.setValue('use_pipeline_uuid', val.use_pipeline_uuid || '');
            console.log('form', form.getValues());
            handleAdapterSelect(val.adapter);
            // dynamicForm.setFieldsValue(val.adapter_config);

            // 设置 webhook 地址（如果有）
            if (val.webhook_full_url) {
              setWebhookUrl(val.webhook_full_url);
            } else {
              setWebhookUrl('');
            }
          })
          .catch((err) => {
            toast.error(t('bots.getBotConfigError') + err.message);
          });
      } else {
        form.reset();
        setWebhookUrl('');
      }
    });
  }

  async function initBotFormComponent() {
    // 初始化流水线列表
    const pipelinesRes = await httpClient.getPipelines();
    console.log('rawPipelineList', pipelinesRes);
    setPipelineNameList(
      pipelinesRes.pipelines.map((item) => {
        return {
          label: item.name,
          value: item.uuid ?? '',
        };
      }),
    );

    // 拉取adapter
    const adaptersRes = await httpClient.getAdapters();
    console.log('rawAdapterList', adaptersRes);
    setAdapterNameList(
      adaptersRes.adapters.map((item) => {
        return {
          label: extractI18nObject(item.label),
          value: item.name,
        };
      }),
    );

    // 初始化适配器图标列表
    setAdapterIconList(
      adaptersRes.adapters.reduce(
        (acc, item) => {
          acc[item.name] = httpClient.getAdapterIconURL(item.name);
          return acc;
        },
        {} as Record<string, string>,
      ),
    );

    // 初始化适配器描述列表
    setAdapterDescriptionList(
      adaptersRes.adapters.reduce(
        (acc, item) => {
          acc[item.name] = extractI18nObject(item.description);
          return acc;
        },
        {} as Record<string, string>,
      ),
    );

    // 初始化适配器表单map
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
            }),
        ),
      );
    });
    setAdapterNameToDynamicConfigMap(adapterNameToDynamicConfigMap);
  }

  async function getBotConfig(
    botId: string,
  ): Promise<z.infer<typeof formSchema> & { webhook_full_url?: string }> {
    return new Promise((resolve, reject) => {
      httpClient
        .getBot(botId)
        .then((res) => {
          const bot = res.bot;
          resolve({
            adapter: bot.adapter,
            description: bot.description,
            name: bot.name,
            adapter_config: bot.adapter_config,
            enable: bot.enable ?? true,
            use_pipeline_uuid: bot.use_pipeline_uuid ?? '',
            webhook_full_url: bot.adapter_runtime_values
              ? ((bot.adapter_runtime_values as Record<string, unknown>)
                  .webhook_full_url as string)
              : undefined,
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

  // 只有通过外层固定表单验证才会走到这里，真正的提交逻辑在这里
  function onDynamicFormSubmit(value: object) {
    setIsLoading(true);
    console.log('set loading', true);
    if (initBotId) {
      // 编辑提交
      // console.log('submit edit', form.getFieldsValue(), value);
      const updateBot: Bot = {
        uuid: initBotId,
        name: form.getValues().name,
        description: form.getValues().description,
        adapter: form.getValues().adapter,
        adapter_config: form.getValues().adapter_config,
        enable: form.getValues().enable,
        use_pipeline_uuid: form.getValues().use_pipeline_uuid,
      };
      httpClient
        .updateBot(initBotId, updateBot)
        .then((res) => {
          console.log('update bot success', res);
          onFormSubmit(form.getValues());
          toast.success(t('bots.saveSuccess'));

          // 保存成功后重新拉取机器人配置，更新 webhook 地址（依赖后端 runtime 计算）
          httpClient
            .getBot(initBotId)
            .then((getRes) => {
              const runtimeValues = getRes.bot.adapter_runtime_values as Record<string, unknown> | undefined;
              const newWebhookUrl = runtimeValues
                ? ((runtimeValues.webhook_full_url as string) || '')
                : '';
              setWebhookUrl(newWebhookUrl);
            })
            .catch((err) => {
              console.warn('refresh webhook url failed', err);
            });
        })
        .catch((err) => {
          toast.error(t('bots.saveError') + err.message);
        })
        .finally(() => {
          setIsLoading(false);
          // form.reset();
          // dynamicForm.resetFields();
        });
    } else {
      // 创建提交
      console.log('submit create', form.getValues(), value);
      const newBot: Bot = {
        name: form.getValues().name,
        description: form.getValues().description,
        adapter: form.getValues().adapter,
        adapter_config: form.getValues().adapter_config,
      };
      httpClient
        .createBot(newBot)
        .then((res) => {
          console.log('create bot success', res);
          toast.success(t('bots.createSuccess'));
          initBotId = res.uuid;

          setBotFormValues();

          onNewBotCreated(res.uuid);
        })
        .catch((err) => {
          toast.error(t('bots.createError') + err.message);
        })
        .finally(() => {
          setIsLoading(false);
          form.reset();
          // dynamicForm.resetFields();
        });
    }
  }

  function deleteBot() {
    if (initBotId) {
      httpClient
        .deleteBot(initBotId)
        .then(() => {
          onBotDeleted();
          toast.success(t('bots.deleteSuccess'));
        })
        .catch((err) => {
          toast.error(t('bots.deleteError') + err.message);
        });
    }
  }

  // 计算动态表单渲染列表：启用 Lark 的 Webhook 时隐藏 app_id 与 app_secret
  const dynamicFormConfigListToRender = (() => {
    const isLark = form.watch('adapter') === 'lark';
    const enableWebhook = !!form.watch('adapter_config')?.['enable-webhook'];
    if (isLark && enableWebhook) {
      return dynamicFormConfigList.filter(
        (item) => item.name !== 'app_id' && item.name !== 'app_secret',
      );
    }
    return dynamicFormConfigList;
  })();

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
          <DialogDescription>{t('bots.deleteConfirmation')}</DialogDescription>
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
                deleteBot();
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
          id="bot-form"
          onSubmit={form.handleSubmit(onDynamicFormSubmit)}
          className="space-y-8"
        >
          <div className="space-y-4">
            {/* 是否启用 & 绑定流水线  仅在编辑模式 */}
            {initBotId && (
              <>
                <div className="flex items-center gap-6">
                  <FormField
                    control={form.control}
                    name="enable"
                    render={({ field }) => (
                      <FormItem className="flex flex-col justify-start gap-[0.8rem] h-[3.8rem]">
                        <FormLabel>{t('common.enable')}</FormLabel>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="use_pipeline_uuid"
                    render={({ field }) => (
                      <FormItem className="flex flex-col justify-start gap-[0.8rem] h-[3.8rem]">
                        <FormLabel>{t('bots.bindPipeline')}</FormLabel>
                        <FormControl>
                          <Select onValueChange={field.onChange} {...field}>
                            <SelectTrigger className="bg-[#ffffff] dark:bg-[#2a2a2e]">
                              <SelectValue
                                placeholder={t('bots.selectPipeline')}
                              />
                            </SelectTrigger>
                            <SelectContent className="fixed z-[1000]">
                              <SelectGroup>
                                {pipelineNameList.map((item) => (
                                  <SelectItem
                                    key={item.value}
                                    value={item.value}
                                  >
                                    {item.label}
                                  </SelectItem>
                                ))}
                              </SelectGroup>
                            </SelectContent>
                          </Select>
                        </FormControl>
                      </FormItem>
                    )}
                  />
                </div>

                {/* Webhook 地址显示（统一 Webhook 模式） */}
                {form.watch('adapter') === 'lark' &&
                  !!form.watch('adapter_config')?.['enable-webhook'] &&
                  webhookUrl && (
                  <FormItem>
                    <FormLabel>{t('bots.webhookUrl')}</FormLabel>
                    <div className="flex items-center gap-2">
                      <Input
                        ref={webhookInputRef}
                        value={webhookUrl}
                        readOnly
                        className="flex-1 bg-gray-50 dark:bg-gray-900"
                        onClick={(e) => {
                          // 点击输入框时自动全选
                          (e.target as HTMLInputElement).select();
                        }}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={copyToClipboard}
                      >
                        {t('common.copy')}
                      </Button>
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      {t('bots.webhookUrlHint')}
                    </p>
                  </FormItem>
                )}
              </>
            )}

            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('bots.botName')}
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
                  <FormLabel>
                    {t('bots.botDescription')}
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
              name="adapter"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('bots.platformAdapter')}
                    <span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <div className="relative">
                      <Select
                        onValueChange={(value) => {
                          field.onChange(value);
                          handleAdapterSelect(value);
                        }}
                        value={field.value}
                      >
                        <SelectTrigger className="w-[180px] bg-[#ffffff] dark:bg-[#2a2a2e]">
                          <SelectValue placeholder={t('bots.selectAdapter')} />
                        </SelectTrigger>
                        <SelectContent className="fixed z-[1000]">
                          <SelectGroup>
                            {adapterNameList.map((item) => (
                              <SelectItem key={item.value} value={item.value}>
                                {item.label}
                              </SelectItem>
                            ))}
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </div>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {form.watch('adapter') && (
              <div className="flex items-start gap-3 p-4 rounded-lg border">
                <img
                  src={adapterIconList[form.watch('adapter')]}
                  alt="adapter icon"
                  className="w-12 h-12 rounded-[8%]"
                />
                <div className="flex flex-col gap-1">
                  <div className="font-medium">
                    {
                      adapterNameList.find(
                        (item) => item.value === form.watch('adapter'),
                      )?.label
                    }
                  </div>
                  <div className="text-sm text-gray-500">
                    {adapterDescriptionList[form.watch('adapter')]}
                  </div>
                </div>
              </div>
            )}

            {showDynamicForm && dynamicFormConfigListToRender.length > 0 && (
              <div className="space-y-4">
                <div className="text-lg font-medium">
                  {t('bots.adapterConfig')}
                </div>
                <DynamicFormComponent
                  itemConfigList={dynamicFormConfigListToRender}
                  initialValues={form.watch('adapter_config')}
                  onSubmit={(values) => {
                    const prev = form.getValues('adapter_config') || {};
                    form.setValue('adapter_config', { ...prev, ...values });
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
