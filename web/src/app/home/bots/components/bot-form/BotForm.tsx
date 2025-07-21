import { useEffect, useState } from 'react';
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
import { i18nObj } from '@/i18n/I18nProvider';

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

  useEffect(() => {
    setBotFormValues();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
          })
          .catch((err) => {
            toast.error(t('bots.getBotConfigError') + err.message);
          });
      } else {
        form.reset();
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
          label: i18nObj(item.label),
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
          acc[item.name] = i18nObj(item.description);
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
  ): Promise<z.infer<typeof formSchema>> {
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
                          <SelectTrigger>
                            <SelectValue
                              placeholder={t('bots.selectPipeline')}
                            />
                          </SelectTrigger>
                          <SelectContent className="fixed z-[1000]">
                            <SelectGroup>
                              {pipelineNameList.map((item) => (
                                <SelectItem key={item.value} value={item.value}>
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
                        <SelectTrigger className="w-[180px]">
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
                  className="w-12 h-12"
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

            {showDynamicForm && dynamicFormConfigList.length > 0 && (
              <div className="space-y-4">
                <div className="text-lg font-medium">
                  {t('bots.adapterConfig')}
                </div>
                <DynamicFormComponent
                  itemConfigList={dynamicFormConfigList}
                  initialValues={form.watch('adapter_config')}
                  onSubmit={(values) => {
                    form.setValue('adapter_config', values);
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
