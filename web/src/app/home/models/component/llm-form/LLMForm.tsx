import { ICreateLLMField } from '@/app/home/models/ICreateLLMField';
import { useEffect, useState } from 'react';
import { IChooseRequesterEntity } from '@/app/home/models/component/llm-form/ChooseRequesterEntity';
import { httpClient } from '@/app/infra/http/HttpClient';
import { LLMModel } from '@/app/infra/entities/api';
import { UUID } from 'uuidjs';

import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

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
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';
const extraArgSchema = z
  .object({
    key: z.string().min(1, { message: '键名不能为空' }),
    type: z.enum(['string', 'number', 'boolean']),
    value: z.string(),
  })
  .superRefine((data, ctx) => {
    if (data.type === 'number' && isNaN(Number(data.value))) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: '必须是有效的数字',
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
        message: '必须是 true 或 false',
        path: ['value'],
      });
    }
  });

const formSchema = z.object({
  name: z.string().min(1, { message: '模型名称不能为空' }),
  model_provider: z.string().min(1, { message: '模型供应商不能为空' }),
  url: z.string().min(1, { message: '请求URL不能为空' }),
  api_key: z.string().min(1, { message: 'API Key不能为空' }),
  abilities: z.array(z.string()),
  extra_args: z.array(extraArgSchema).optional(),
});

export default function LLMForm({
  editMode,
  initLLMId,
  onFormSubmit,
  onFormCancel,
  onLLMDeleted,
}: {
  editMode: boolean;
  initLLMId?: string;
  onFormSubmit: () => void;
  onFormCancel: () => void;
  onLLMDeleted: () => void;
}) {
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      model_provider: '',
      url: '',
      api_key: '',
      abilities: [],
      extra_args: [],
    },
  });

  const [extraArgs, setExtraArgs] = useState<
    { key: string; type: 'string' | 'number' | 'boolean'; value: string }[]
  >([]);

  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState(false);
  const abilityOptions: { label: string; value: string }[] = [
    {
      label: '视觉能力',
      value: 'vision',
    },
    {
      label: '函数调用',
      value: 'func_call',
    },
  ];
  const [requesterNameList, setRequesterNameList] = useState<
    IChooseRequesterEntity[]
  >([]);
  const [requesterDefaultURLList, setRequesterDefaultURLList] = useState<
    string[]
  >([]);

  useEffect(() => {
    initLLMModelFormComponent();
    if (editMode && initLLMId) {
      getLLMConfig(initLLMId).then((val) => {
        form.setValue('name', val.name);
        form.setValue('model_provider', val.model_provider);
        form.setValue('url', val.url);
        form.setValue('api_key', val.api_key);
        form.setValue('abilities', val.abilities as ('vision' | 'func_call')[]);
        // 转换extra_args为新格式
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  async function initLLMModelFormComponent() {
    const requesterNameList = await httpClient.getProviderRequesters();
    setRequesterNameList(
      requesterNameList.requesters.map((item) => {
        return {
          label: item.label.zh_CN,
          value: item.name,
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

  async function getLLMConfig(id: string): Promise<ICreateLLMField> {
    const llmModel = await httpClient.getProviderLLMModel(id);

    const fakeExtraArgs = [];
    const extraArgs = llmModel.model.extra_args as Record<string, string>;
    for (const key in extraArgs) {
      fakeExtraArgs.push(`${key}:${extraArgs[key]}`);
    }
    return {
      name: llmModel.model.name,
      model_provider: llmModel.model.requester,
      url: llmModel.model.requester_config?.base_url,
      api_key: llmModel.model.api_keys[0],
      abilities: llmModel.model.abilities || [],
      extra_args: fakeExtraArgs,
    };
  }

  function handleFormSubmit(value: z.infer<typeof formSchema>) {
    const extraArgsObj: Record<string, string | number | boolean> = {};
    value.extra_args?.forEach((arg) => {
      if (arg.type === 'number') {
        extraArgsObj[arg.key] = Number(arg.value);
      } else if (arg.type === 'boolean') {
        extraArgsObj[arg.key] = arg.value === 'true';
      } else {
        extraArgsObj[arg.key] = arg.value;
      }
    });

    const llmModel: LLMModel = {
      uuid: editMode ? initLLMId || '' : UUID.generate(),
      name: value.name,
      description: '',
      requester: value.model_provider,
      requester_config: {
        base_url: value.url,
        timeout: 120,
      },
      extra_args: extraArgsObj,
      api_keys: [value.api_key],
      abilities: value.abilities,
    };

    if (editMode) {
      onSaveEdit(llmModel).then(() => {
        form.reset();
      });
    } else {
      onCreateLLM(llmModel).then(() => {
        form.reset();
      });
    }
  }

  async function onCreateLLM(llmModel: LLMModel) {
    try {
      await httpClient.createProviderLLMModel(llmModel);
      onFormSubmit();
      toast.success('创建成功');
    } catch (err) {
      toast.error('创建失败：' + (err as Error).message);
    }
  }

  async function onSaveEdit(llmModel: LLMModel) {
    try {
      await httpClient.updateProviderLLMModel(initLLMId || '', llmModel);
      onFormSubmit();
      toast.success('保存成功');
    } catch (err) {
      toast.error('保存失败：' + (err as Error).message);
    }
  }

  function deleteModel() {
    if (initLLMId) {
      httpClient
        .deleteProviderLLMModel(initLLMId)
        .then(() => {
          onLLMDeleted();
          toast.success('删除成功');
        })
        .catch((err) => {
          toast.error('删除失败：' + err.message);
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
            <DialogTitle>删除确认</DialogTitle>
          </DialogHeader>
          <DialogDescription>你确定要删除这个模型吗？</DialogDescription>
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
                deleteModel();
                setShowDeleteConfirmModal(false);
              }}
            >
              确认删除
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
                    模型名称<span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                  <FormDescription>
                    请填写供应商向您提供的模型名称
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
                    模型供应商<span className="text-red-500">*</span>
                  </FormLabel>
                  <FormControl>
                    <Select
                      onValueChange={(value) => {
                        field.onChange(value);
                        const index = requesterNameList.findIndex(
                          (item) => item.value === value,
                        );
                        if (index !== -1) {
                          form.setValue('url', requesterDefaultURLList[index]);
                        }
                      }}
                      value={field.value}
                    >
                      <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="选择模型供应商" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          {requesterNameList.map((item) => (
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
                    请求URL<span className="text-red-500">*</span>
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
              name="api_key"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    API Key<span className="text-red-500">*</span>
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
              name="abilities"
              render={() => (
                <FormItem>
                  <FormLabel>能力</FormLabel>
                  <div className="mb-0">
                    <FormDescription>选择模型能力</FormDescription>
                  </div>
                  {abilityOptions.map((item) => (
                    <FormField
                      key={item.value}
                      control={form.control}
                      name="abilities"
                      render={({ field }) => {
                        return (
                          <FormItem
                            key={item.value}
                            className="flex flex-row items-start space-x-1 space-y-0"
                          >
                            <FormControl>
                              <Checkbox
                                checked={
                                  Array.isArray(field.value) &&
                                  field.value?.includes(item.value)
                                }
                                onCheckedChange={(checked) => {
                                  return checked
                                    ? field.onChange([
                                        ...(field.value || []),
                                        item.value,
                                      ])
                                    : field.onChange(
                                        field.value?.filter(
                                          (value) => value !== item.value,
                                        ),
                                      );
                                }}
                              />
                            </FormControl>
                            <FormLabel className="font-normal">
                              {item.label}
                            </FormLabel>
                          </FormItem>
                        );
                      }}
                    />
                  ))}
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormItem>
              <FormLabel>额外参数</FormLabel>
              <div className="space-y-2">
                {extraArgs.map((arg, index) => (
                  <div key={index} className="flex gap-2">
                    <Input
                      placeholder="键名"
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
                      <SelectTrigger className="w-[120px]">
                        <SelectValue placeholder="类型" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="string">字符串</SelectItem>
                        <SelectItem value="number">数字</SelectItem>
                        <SelectItem value="boolean">布尔值</SelectItem>
                      </SelectContent>
                    </Select>
                    <Input
                      placeholder="值"
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
                  添加参数
                </Button>
              </div>
              <FormDescription>
                将在请求时附加到请求体中，如 max_tokens, temperature, top_p 等
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
                删除
              </Button>
            )}

            <Button type="submit">{editMode ? '保存' : '提交'}</Button>

            <Button
              type="button"
              variant="outline"
              onClick={() => onFormCancel()}
            >
              取消
            </Button>
          </DialogFooter>
        </form>
      </Form>
    </div>
  );
}
