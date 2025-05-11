import {
  DynamicFormItemType,
  IDynamicFormItemSchema,
} from '@/app/infra/entities/form/dynamic';
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
import { ControllerRenderProps } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { useEffect, useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { LLMModel } from '@/app/infra/entities/api';
import { toast } from 'sonner';

export default function DynamicFormItemComponent({
  config,
  field,
}: {
  config: IDynamicFormItemSchema;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  field: ControllerRenderProps<any, any>;
}) {
  const [llmModels, setLlmModels] = useState<LLMModel[]>([]);

  useEffect(() => {
    if (config.type === DynamicFormItemType.LLM_MODEL_SELECTOR) {
      httpClient
        .getProviderLLMModels()
        .then((resp) => {
          setLlmModels(resp.models);
        })
        .catch((err) => {
          toast.error('获取 LLM 模型列表失败：' + err.message);
        });
    }
  }, [config.type]);

  switch (config.type) {
    case DynamicFormItemType.INT:
    case DynamicFormItemType.FLOAT:
      return (
        <Input
          type="number"
          {...field}
          onChange={(e) => field.onChange(Number(e.target.value))}
        />
      );

    case DynamicFormItemType.STRING:
      return <Input {...field} />;

    case DynamicFormItemType.BOOLEAN:
      return <Switch checked={field.value} onCheckedChange={field.onChange} />;

    case DynamicFormItemType.STRING_ARRAY:
      return (
        <div className="space-y-2">
          {field.value.map((item: string, index: number) => (
            <div key={index} className="flex gap-2 items-center">
              <Input
                className="w-[200px]"
                value={item}
                onChange={(e) => {
                  const newValue = [...field.value];
                  newValue[index] = e.target.value;
                  field.onChange(newValue);
                }}
              />
              <button
                type="button"
                className="p-2 hover:bg-gray-100 rounded"
                onClick={() => {
                  const newValue = field.value.filter(
                    (_: string, i: number) => i !== index,
                  );
                  field.onChange(newValue);
                }}
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
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              field.onChange([...field.value, '']);
            }}
          >
            添加
          </Button>
        </div>
      );

    case DynamicFormItemType.SELECT:
      return (
        <Select value={field.value} onValueChange={field.onChange}>
          <SelectTrigger>
            <SelectValue placeholder="请选择" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {config.options?.map((option) => (
                <SelectItem key={option.name} value={option.name}>
                  {option.label.zh_CN}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      );

    case DynamicFormItemType.LLM_MODEL_SELECTOR:
      return (
        <Select value={field.value} onValueChange={field.onChange}>
          <SelectTrigger>
            <SelectValue placeholder="请选择模型" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {llmModels.map((model) => (
                <SelectItem key={model.uuid} value={model.uuid}>
                  {model.name}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      );

    case DynamicFormItemType.PROMPT_EDITOR:
      return (
        <div className="space-y-2">
          {field.value.map(
            (item: { role: string; content: string }, index: number) => (
              <div key={index} className="flex gap-2 items-center">
                {/* 角色选择 */}
                {index === 0 ? (
                  <div className="w-[120px] px-3 py-2 border rounded bg-gray-50 text-gray-500">
                    system
                  </div>
                ) : (
                  <Select
                    value={item.role}
                    onValueChange={(value) => {
                      const newValue = [...field.value];
                      newValue[index] = { ...newValue[index], role: value };
                      field.onChange(newValue);
                    }}
                  >
                    <SelectTrigger className="w-[120px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="user">user</SelectItem>
                        <SelectItem value="assistant">assistant</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                )}
                {/* 内容输入 */}
                <Input
                  className="w-[300px]"
                  value={item.content}
                  onChange={(e) => {
                    const newValue = [...field.value];
                    newValue[index] = {
                      ...newValue[index],
                      content: e.target.value,
                    };
                    field.onChange(newValue);
                  }}
                />
                {/* 删除按钮，第一轮不显示 */}
                {index !== 0 && (
                  <button
                    type="button"
                    className="p-2 hover:bg-gray-100 rounded"
                    onClick={() => {
                      const newValue = field.value.filter(
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        (_: any, i: number) => i !== index,
                      );
                      field.onChange(newValue);
                    }}
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
                )}
              </div>
            ),
          )}
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              field.onChange([...field.value, { role: 'user', content: '' }]);
            }}
          >
            添加回合
          </Button>
        </div>
      );

    default:
      return <Input {...field} />;
  }
}
