import { ICreateEmbeddingField } from '@/app/home/models/component/ICreateEmbeddingField';
import { useEffect, useState } from 'react';
import { IChooseRequesterEntity } from '@/app/home/models/component/ChooseRequesterEntity';
import { httpClient } from '@/app/infra/http/HttpClient';
import { EmbeddingModel } from '@/app/infra/entities/api';
import { UUID } from 'uuidjs';

import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
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
  FormDescription,
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
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import { extractI18nObject } from '@/i18n/I18nProvider';

const getExtraArgSchema = (t: (key: string) => string) =>
  z
    .object({
      key: z.string().min(1, { message: t('models.keyNameRequired') }),
      type: z.enum(['string', 'number', 'boolean']),
      value: z.string(),
    })
    .superRefine((data, ctx) => {
      if (data.type === 'number' && isNaN(Number(data.value))) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: t('models.mustBeValidNumber'),
          path: ['value'],
        });
      }
      if (
        data.type === 'boolean' &&
        data.value !== 'true' &&
        data.value !== 'false'
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: t('models.mustBeTrueOrFalse'),
          path: ['value'],
        });
      }
    });

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('models.modelNameRequired') }),
    model_provider: z
      .string()
      .min(1, { message: t('models.modelProviderRequired') }),
    url: z.string().min(1, { message: t('models.requestURLRequired') }),
    api_key: z.string().optional(),
    extra_args: z.array(getExtraArgSchema(t)).optional(),
  });

export default function EmbeddingForm({
  editMode,
  initEmbeddingId,
  onFormSubmit,
  onFormCancel,
  onEmbeddingDeleted,
}: {
  editMode: boolean;
  initEmbeddingId?: string;
  onFormSubmit: () => void;
  onFormCancel: () => void;
  onEmbeddingDeleted: () => void;
}) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      model_provider: '',
      url: '',
      api_key: '',
      extra_args: [],
    },
  });

  const [extraArgs, setExtraArgs] = useState<
    { key: string; type: 'string' | 'number' | 'boolean'; value: string }[]
  >([]);

  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState(false);
  const [requesterNameList, setRequesterNameList] = useState<
    IChooseRequesterEntity[]
  >([]);
  const [requesterDefaultURLList, setRequesterDefaultURLList] = useState<
    string[]
  >([]);
  const [modelTesting, setModelTesting] = useState(false);
  const [currentModelProvider, setCurrentModelProvider] = useState('');

  useEffect(() => {
    initEmbeddingModelFormComponent().then(() => {
      if (editMode && initEmbeddingId) {
        getEmbeddingConfig(initEmbeddingId).then((val) => {
          form.setValue('name', val.name);
          form.setValue('model_provider', val.model_provider);
          setCurrentModelProvider(val.model_provider);
          form.setValue('url', val.url);
          form.setValue('api_key', val.api_key);
          if (val.extra_args) {
            const args = val.extra_args.map((arg) => {
              const [key, value] = arg.split(':');
              let type: 'string' | 'number' | 'boolean' = 'string';
              if (!isNaN(Number(value))) {
                type = 'number';
              } else if (value === 'true' || value === 'false') {
                type = 'boolean';
              }
              return {
                key,
                type,
                value,
              };
            });
            setExtraArgs(args);
            form.setValue('extra_args', args);
          }
        });
      } else {
        form.reset();
      }
    });
  }, []);

  const addExtraArg = () => {
    setExtraArgs([...extraArgs, { key: '', type: 'string', value: '' }]);
  };

  const updateExtraArg = (
    index: number,
    field: 'key' | 'type' | 'value',
    value: string,
  ) => {
    const newArgs = [...extraArgs];
    newArgs[index] = {
      ...newArgs[index],
      [field]: value,
    };
    setExtraArgs(newArgs);
    form.setValue('extra_args', newArgs);
  };

  const removeExtraArg = (index: number) => {
    const newArgs = extraArgs.filter((_, i) => i !== index);
    setExtraArgs(newArgs);
    form.setValue('extra_args', newArgs);
  };

  async function initEmbeddingModelFormComponent() {
    const requesterNameList =
      await httpClient.getProviderRequesters('text-embedding');
    setRequesterNameList(
      requesterNameList.requesters.map((item) => {
        return {
          label: extractI18nObject(item.label),
          value: item.name,
          provider_category: item.spec.provider_category || 'manufacturer',
        };
      }),
    );
    setRequesterDefaultURLList(
      requesterNameList.requesters.map((item) => {
        const config = item.spec.config;
        for (let i = 0; i < config.length; i++) {
          if (config[i].name == 'base_url') {
            return config[i].default?.toString() || '';
          }
        }
        return '';
      }),
    );
  }

  async function getEmbeddingConfig(
    id: string,
  ): Promise<ICreateEmbeddingField> {
    const embeddingModel = await httpClient.getProviderEmbeddingModel(id);

    const fakeExtraArgs = [];
    const extraArgs = embeddingModel.model.extra_args as Record<string, string>;
    for (const key in extraArgs) {
      fakeExtraArgs.push(`${key}:${extraArgs[key]}`);
    }
    return {
      name: embeddingModel.model.name,
      model_provider: embeddingModel.model.requester,
      url: embeddingModel.model.requester_config?.base_url,
      api_key: embeddingModel.model.api_keys[0],
      extra_args: fakeExtraArgs,
    };
  }

  function handleFormSubmit(value: z.infer<typeof formSchema>) {
    const extraArgsObj: Record<string, string | number | boolean> = {};
    value.extra_args?.forEach(
      (arg: { key: string; type: string; value: string }) => {
        if (arg.type === 'number') {
          extraArgsObj[arg.key] = Number(arg.value);
        } else if (arg.type === 'boolean') {
          extraArgsObj[arg.key] = arg.value === 'true';
        } else {
          extraArgsObj[arg.key] = arg.value;
        }
      },
    );

    const embeddingModel: EmbeddingModel = {
      uuid: editMode ? initEmbeddingId || '' : UUID.generate(),
      name: value.name,
      description: '',
      requester: value.model_provider,
      requester_config: {
        base_url: value.url,
        timeout: 120,
      },
      extra_args: extraArgsObj,
      api_keys: value.api_key ? [value.api_key] : [],
    };

    if (editMode) {
      onSaveEdit(embeddingModel).then(() => {
        form.reset();
      });
    } else {
      onCreateEmbedding(embeddingModel).then(() => {
        form.reset();
      });
    }
  }

  async function onCreateEmbedding(embeddingModel: EmbeddingModel) {
    try {
      await httpClient.createProviderEmbeddingModel(embeddingModel);
      onFormSubmit();
      toast.success(t('models.createSuccess'));
    } catch (err) {
      toast.error(t('models.createError') + (err as Error).message);
    }
  }

  async function onSaveEdit(embeddingModel: EmbeddingModel) {
    try {
      await httpClient.updateProviderEmbeddingModel(
        initEmbeddingId || '',
        embeddingModel,
      );
      onFormSubmit();
      toast.success(t('models.saveSuccess'));
    } catch (err) {
      toast.error(t('models.saveError') + (err as Error).message);
    }
  }

  function deleteModel() {
    if (initEmbeddingId) {
      httpClient
        .deleteProviderEmbeddingModel(initEmbeddingId)
        .then(() => {
          onEmbeddingDeleted();
          toast.success(t('models.deleteSuccess'));
        })
        .catch((err) => {
          toast.error(t('models.deleteError') + err.message);
        });
    }
  }

  function testEmbeddingModelInForm() {
    setModelTesting(true);
    const extraArgsObj: Record<string, string | number | boolean> = {};
    form
      .getValues('extra_args')
      ?.forEach((arg: { key: string; type: string; value: string }) => {
        if (arg.type === 'number') {
          extraArgsObj[arg.key] = Number(arg.value);
        } else if (arg.type === 'boolean') {
          extraArgsObj[arg.key] = arg.value === 'true';
        } else {
          extraArgsObj[arg.key] = arg.value;
        }
      });
    const apiKey = form.getValues('api_key');
    httpClient
      .testEmbeddingModel('_', {
        uuid: '',
        name: form.getValues('name'),
        description: '',
        requester: form.getValues('model_provider'),
        requester_config: {
          base_url: form.getValues('url'),
          timeout: 120,
        },
        api_keys: apiKey ? [apiKey] : [],
        extra_args: extraArgsObj,
      })
      .then((res) => {
        console.log(res);
        toast.success(t('models.testSuccess'));
      })
      .catch(() => {
        toast.error(t('models.testError'));
      })
      .finally(() => {
        setModelTesting(false);
      });
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
          <DialogDescription>
            {t('models.deleteConfirmation')}
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
                deleteModel();
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
          onSubmit={form.handleSubmit(handleFormSubmit)}
          className="space-y-8"
        >
          <div className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('models.modelName')}
                    <span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                  <FormDescription>
                    {t('models.modelProviderDescription')}
                  </FormDescription>
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="model_provider"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('models.modelProvider')}
                    <span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <Select
                      onValueChange={(value) => {
                        field.onChange(value);
                        setCurrentModelProvider(value);
                        const index = requesterNameList.findIndex(
                          (item) => item.value === value,
                        );
                        if (index !== -1) {
                          form.setValue('url', requesterDefaultURLList[index]);
                        }
                      }}
                      value={field.value}
                    >
                      <SelectTrigger className="w-[180px] bg-[#ffffff] dark:bg-[#2a2a2e]">
                        <SelectValue
                          placeholder={t('models.selectModelProvider')}
                        />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          <SelectLabel>
                            {t('models.modelManufacturer')}
                          </SelectLabel>
                          {requesterNameList
                            .filter(
                              (item) =>
                                item.provider_category === 'manufacturer',
                            )
                            .map((item) => (
                              <SelectItem key={item.value} value={item.value}>
                                {item.label}
                              </SelectItem>
                            ))}
                        </SelectGroup>
                        <SelectGroup>
                          <SelectLabel>
                            {t('models.aggregationPlatform')}
                          </SelectLabel>
                          {requesterNameList
                            .filter((item) => item.provider_category === 'maas')
                            .map((item) => (
                              <SelectItem key={item.value} value={item.value}>
                                {item.label}
                              </SelectItem>
                            ))}
                        </SelectGroup>
                        <SelectGroup>
                          <SelectLabel>{t('models.selfDeployed')}</SelectLabel>
                          {requesterNameList
                            .filter(
                              (item) =>
                                item.provider_category === 'self-hosted',
                            )
                            .map((item) => (
                              <SelectItem key={item.value} value={item.value}>
                                {item.label}
                              </SelectItem>
                            ))}
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="url"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('models.requestURL')}
                    <span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {!['ollama-chat'].includes(currentModelProvider) && (
              <FormField
                control={form.control}
                name="api_key"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('models.apiKey')}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            <FormItem>
              <FormLabel>{t('models.extraParameters')}</FormLabel>
              <div className="space-y-2">
                {extraArgs.map((arg, index) => (
                  <div key={index} className="flex gap-2">
                    <Input
                      placeholder={t('models.keyName')}
                      value={arg.key}
                      onChange={(e) =>
                        updateExtraArg(index, 'key', e.target.value)
                      }
                    />
                    <Select
                      value={arg.type}
                      onValueChange={(value) =>
                        updateExtraArg(index, 'type', value)
                      }
                    >
                      <SelectTrigger className="w-[120px] bg-[#ffffff] dark:bg-[#2a2a2e]">
                        <SelectValue placeholder={t('models.type')} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="string">
                          {t('models.string')}
                        </SelectItem>
                        <SelectItem value="number">
                          {t('models.number')}
                        </SelectItem>
                        <SelectItem value="boolean">
                          {t('models.boolean')}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <Input
                      placeholder={t('models.value')}
                      value={arg.value}
                      onChange={(e) =>
                        updateExtraArg(index, 'value', e.target.value)
                      }
                    />
                    <button
                      type="button"
                      className="p-2 hover:bg-gray-100 rounded"
                      onClick={() => removeExtraArg(index)}
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                        className="w-5 h-5 text-red-500"
                      >
                        <path d="M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"></path>
                      </svg>
                    </button>
                  </div>
                ))}
                <Button type="button" variant="outline" onClick={addExtraArg}>
                  {t('models.addParameter')}
                </Button>
              </div>
              <FormDescription>
                {t('embedding.extraParametersDescription')}
              </FormDescription>
              <FormMessage />
            </FormItem>
          </div>
          <DialogFooter>
            {editMode && (
              <Button
                type="button"
                variant="destructive"
                onClick={() => setShowDeleteConfirmModal(true)}
              >
                {t('common.delete')}
              </Button>
            )}

            <Button type="submit">
              {editMode ? t('common.save') : t('common.submit')}
            </Button>

            <Button
              type="button"
              variant="outline"
              onClick={() => testEmbeddingModelInForm()}
              disabled={modelTesting}
            >
              {t('common.test')}
            </Button>

            <Button
              type="button"
              variant="outline"
              onClick={() => onFormCancel()}
            >
              {t('common.cancel')}
            </Button>
          </DialogFooter>
        </form>
      </Form>
    </div>
  );
}
