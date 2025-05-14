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
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { useTranslation } from 'react-i18next';
import { i18nObj } from '@/i18n/I18nProvider';

export default function DynamicFormItemComponent({
  config,
  field,
}: {
  config: IDynamicFormItemSchema;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  field: ControllerRenderProps<any, any>;
}) {
  const [llmModels, setLlmModels] = useState<LLMModel[]>([]);
  const { t } = useTranslation();

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
            {t('common.add')}
          </Button>
        </div>
      );

    case DynamicFormItemType.SELECT:
      return (
        <Select value={field.value} onValueChange={field.onChange}>
          <SelectTrigger>
            <SelectValue placeholder={t('common.select')} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {config.options?.map((option) => (
                <SelectItem key={option.name} value={option.name}>
                  {i18nObj(option.label)}
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
            <SelectValue placeholder={t('models.selectModel')} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {llmModels.map((model) => (
                <HoverCard key={model.uuid} openDelay={0} closeDelay={0}>
                  <HoverCardTrigger asChild>
                    <SelectItem value={model.uuid}>{model.name}</SelectItem>
                  </HoverCardTrigger>
                  <HoverCardContent
                    className="w-80 data-[state=open]:animate-none data-[state=closed]:animate-none"
                    align="end"
                    side="right"
                    sideOffset={10}
                  >
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <img
                          src={httpClient.getProviderRequesterIconURL(
                            model.requester,
                          )}
                          alt="icon"
                          className="w-8 h-8 rounded-full"
                        />
                        <h4 className="font-medium">{model.name}</h4>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {model.description}
                      </p>
                      {model.requester_config && (
                        <div className="flex items-center gap-1 text-xs">
                          <svg
                            className="w-4 h-4 text-gray-500"
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 24 24"
                            fill="currentColor"
                          >
                            <path d="M13.0607 8.11097L14.4749 9.52518C17.2086 12.2589 17.2086 16.691 14.4749 19.4247L14.1214 19.7782C11.3877 22.5119 6.95555 22.5119 4.22188 19.7782C1.48821 17.0446 1.48821 12.6124 4.22188 9.87874L5.6361 11.293C3.68348 13.2456 3.68348 16.4114 5.6361 18.364C7.58872 20.3166 10.7545 20.3166 12.7072 18.364L13.0607 18.0105C15.0133 16.0578 15.0133 12.892 13.0607 10.9394L11.6465 9.52518L13.0607 8.11097ZM19.7782 14.1214L18.364 12.7072C20.3166 10.7545 20.3166 7.58872 18.364 5.6361C16.4114 3.68348 13.2456 3.68348 11.293 5.6361L10.9394 5.98965C8.98678 7.94227 8.98678 11.1081 10.9394 13.0607L12.3536 14.4749L10.9394 15.8891L9.52518 14.4749C6.79151 11.7413 6.79151 7.30911 9.52518 4.57544L9.87874 4.22188C12.6124 1.48821 17.0446 1.48821 19.7782 4.22188C22.5119 6.95555 22.5119 11.3877 19.7782 14.1214Z"></path>
                          </svg>
                          <span className="font-semibold">Base URL：</span>
                          {model.requester_config.base_url}
                        </div>
                      )}
                      {model.abilities && model.abilities.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {model.abilities.map((ability) => (
                            <div
                              key={ability}
                              className="flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-600"
                            >
                              {ability === 'vision' && (
                                <svg
                                  className="w-3 h-3"
                                  xmlns="http://www.w3.org/2000/svg"
                                  viewBox="0 0 24 24"
                                  fill="currentColor"
                                >
                                  <path d="M12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2ZM12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4ZM12 7C14.7614 7 17 9.23858 17 12C17 14.7614 14.7614 17 12 17C9.23858 17 7 14.7614 7 12C7 11.4872 7.07719 10.9925 7.22057 10.5268C7.61175 11.3954 8.48527 12 9.5 12C10.8807 12 12 10.8807 12 9.5C12 8.48527 11.3954 7.61175 10.5269 7.21995C10.9925 7.07719 11.4872 7 12 7Z"></path>
                                </svg>
                              )}
                              {ability === 'func_call' && (
                                <svg
                                  className="w-3 h-3"
                                  xmlns="http://www.w3.org/2000/svg"
                                  viewBox="0 0 24 24"
                                  fill="currentColor"
                                >
                                  <path d="M5.32943 3.27158C6.56252 2.8332 7.9923 3.10749 8.97927 4.09446C10.1002 5.21537 10.3019 6.90741 9.5843 8.23385L20.293 18.9437L18.8788 20.3579L8.16982 9.64875C6.84325 10.3669 5.15069 10.1654 4.02952 9.04421C3.04227 8.05696 2.7681 6.62665 3.20701 5.39332L5.44373 7.63C6.02952 8.21578 6.97927 8.21578 7.56505 7.63C8.15084 7.04421 8.15084 6.09446 7.56505 5.50868L5.32943 3.27158ZM15.6968 5.15512L18.8788 3.38736L20.293 4.80157L18.5252 7.98355L16.7574 8.3371L14.6361 10.4584L13.2219 9.04421L15.3432 6.92289L15.6968 5.15512ZM8.97927 13.2868L10.3935 14.7011L5.09018 20.0044C4.69966 20.3949 4.06649 20.3949 3.67597 20.0044C3.31334 19.6417 3.28744 19.0699 3.59826 18.6774L3.67597 18.5902L8.97927 13.2868Z"></path>
                                </svg>
                              )}
                              <span>
                                {ability === 'vision'
                                  ? t('models.visionAbility')
                                  : ability === 'func_call'
                                    ? t('models.functionCallAbility')
                                    : ability}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      {model.extra_args &&
                        Object.keys(model.extra_args).length > 0 && (
                          <div className="text-xs">
                            <div className="font-semibold mb-1">
                              {t('models.extraParameters')}
                            </div>
                            <div className="space-y-1">
                              {Object.entries(
                                model.extra_args as Record<string, unknown>,
                              ).map(([key, value]) => (
                                <div
                                  key={key}
                                  className="flex items-center gap-1"
                                >
                                  <span className="text-gray-500">{key}：</span>
                                  <span className="break-all">
                                    {JSON.stringify(value)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                    </div>
                  </HoverCardContent>
                </HoverCard>
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
            {t('common.addRound')}
          </Button>
        </div>
      );

    default:
      return <Input {...field} />;
  }
}
