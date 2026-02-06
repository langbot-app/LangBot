import {
  DynamicFormItemType,
  IDynamicFormItemSchema,
  IFileConfig,
} from '@/app/infra/entities/form/dynamic';
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
import { Switch } from '@/components/ui/switch';
import { ControllerRenderProps } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { useEffect, useState } from 'react';
import { httpClient, systemInfo, userInfo } from '@/app/infra/http';
import {
  LLMModel,
  Bot,
  KnowledgeBase,
  EmbeddingModel,
} from '@/app/infra/entities/api';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Plus, X, Eye, Wrench } from 'lucide-react';

export default function DynamicFormItemComponent({
  config,
  field,
  onFileUploaded,
}: {
  config: IDynamicFormItemSchema;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  field: ControllerRenderProps<any, any>;
  onFileUploaded?: (fileKey: string) => void;
}) {
  const [llmModels, setLlmModels] = useState<LLMModel[]>([]);
  const [embeddingModels, setEmbeddingModels] = useState<EmbeddingModel[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [bots, setBots] = useState<Bot[]>([]);
  const [uploading, setUploading] = useState<boolean>(false);
  const [kbDialogOpen, setKbDialogOpen] = useState(false);
  const [tempSelectedKBIds, setTempSelectedKBIds] = useState<string[]>([]);
  const { t } = useTranslation();

  const handleFileUpload = async (file: File): Promise<IFileConfig | null> => {
    const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

    if (file.size > MAX_FILE_SIZE) {
      toast.error(t('plugins.fileUpload.tooLarge'));
      return null;
    }

    try {
      setUploading(true);
      const response = await httpClient.uploadPluginConfigFile(file);
      toast.success(t('plugins.fileUpload.success'));

      // 通知父组件文件已上传
      onFileUploaded?.(response.file_key);

      return {
        file_key: response.file_key,
        mimetype: file.type,
      };
    } catch (error) {
      toast.error(
        t('plugins.fileUpload.failed') + ': ' + (error as Error).message,
      );
      return null;
    } finally {
      setUploading(false);
    }
  };

  useEffect(() => {
    if (config.type === DynamicFormItemType.LLM_MODEL_SELECTOR) {
      httpClient
        .getProviderLLMModels()
        .then((resp) => {
          let models = resp.models;
          // Filter out space-chat-completions models when not logged in with space account or when models service is disabled
          if (
            systemInfo.disable_models_service ||
            userInfo?.account_type !== 'space'
          ) {
            models = models.filter(
              (m) => m.provider?.requester !== 'space-chat-completions',
            );
          }
          setLlmModels(models);
        })
        .catch((err) => {
          toast.error('Failed to get LLM model list: ' + err.msg);
        });
    }
  }, [config.type]);

  useEffect(() => {
    if (config.type === DynamicFormItemType.EMBEDDING_MODEL_SELECTOR) {
      httpClient
        .getProviderEmbeddingModels()
        .then((resp) => {
          setEmbeddingModels(resp.models);
        })
        .catch((err) => {
          toast.error('Failed to get embedding model list: ' + err.msg);
        });
    }
  }, [config.type]);

  useEffect(() => {
    if (
      config.type === DynamicFormItemType.KNOWLEDGE_BASE_SELECTOR ||
      config.type === DynamicFormItemType.KNOWLEDGE_BASE_MULTI_SELECTOR
    ) {
      httpClient
        .getKnowledgeBases()
        .then((resp) => {
          setKnowledgeBases(resp.bases);
        })
        .catch((err) => {
          toast.error('Failed to get knowledge base list: ' + err.msg);
        });
    }
  }, [config.type]);

  useEffect(() => {
    if (config.type === DynamicFormItemType.BOT_SELECTOR) {
      httpClient
        .getBots()
        .then((resp) => {
          setBots(resp.bots);
        })
        .catch((err) => {
          toast.error('Failed to get bot list: ' + err.msg);
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

    case DynamicFormItemType.TEXT:
      return <Textarea {...field} className="min-h-[120px]" />;

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
          <SelectTrigger className="bg-[#ffffff] dark:bg-[#2a2a2e]">
            <SelectValue placeholder={t('common.select')} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {config.options?.map((option) => (
                <SelectItem key={option.name} value={option.name}>
                  {extractI18nObject(option.label)}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      );

    case DynamicFormItemType.LLM_MODEL_SELECTOR:
      // Group models by provider
      const groupedModels = llmModels.reduce(
        (acc, model) => {
          const providerName =
            model.provider?.name || model.provider?.requester || 'Unknown';
          if (!acc[providerName]) acc[providerName] = [];
          acc[providerName].push(model);
          return acc;
        },
        {} as Record<string, LLMModel[]>,
      );

      return (
        <Select value={field.value} onValueChange={field.onChange}>
          <SelectTrigger className="bg-[#ffffff] dark:bg-[#2a2a2e]">
            <SelectValue placeholder={t('models.selectModel')} />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(groupedModels).map(([providerName, models]) => (
              <SelectGroup key={providerName}>
                <SelectLabel>{providerName}</SelectLabel>
                {models.map((model) => (
                  <SelectItem key={model.uuid} value={model.uuid}>
                    <span className="inline-flex items-center gap-1">
                      {model.name}
                      {model.abilities?.includes('vision') && (
                        <Eye className="h-3 w-3 text-muted-foreground" />
                      )}
                      {model.abilities?.includes('func_call') && (
                        <Wrench className="h-3 w-3 text-muted-foreground" />
                      )}
                    </span>
                  </SelectItem>
                ))}
              </SelectGroup>
            ))}
          </SelectContent>
        </Select>
      );

    case DynamicFormItemType.EMBEDDING_MODEL_SELECTOR:
      // Group embedding models by provider
      const groupedEmbeddingModels = embeddingModels.reduce(
        (acc, model) => {
          const providerName = model.provider?.name || 'Unknown';
          if (!acc[providerName]) acc[providerName] = [];
          acc[providerName].push(model);
          return acc;
        },
        {} as Record<string, EmbeddingModel[]>,
      );

      return (
        <Select value={field.value} onValueChange={field.onChange}>
          <SelectTrigger className="bg-[#ffffff] dark:bg-[#2a2a2e]">
            <SelectValue placeholder={t('knowledge.selectEmbeddingModel')} />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(groupedEmbeddingModels).map(([providerName, models]) => (
              <SelectGroup key={providerName}>
                <SelectLabel>{providerName}</SelectLabel>
                {models.map((model) => (
                  <SelectItem key={model.uuid} value={model.uuid}>
                    {model.name}
                  </SelectItem>
                ))}
              </SelectGroup>
            ))}
          </SelectContent>
        </Select>
      );

    case DynamicFormItemType.KNOWLEDGE_BASE_SELECTOR:
      // Group KBs by RAG engine name
      const kbsByEngine = knowledgeBases.reduce(
        (acc, kb) => {
          const engineName = kb.rag_engine?.name
            ? extractI18nObject(kb.rag_engine.name)
            : t('knowledge.unknownEngine');
          if (!acc[engineName]) {
            acc[engineName] = [];
          }
          acc[engineName].push(kb);
          return acc;
        },
        {} as Record<string, typeof knowledgeBases>,
      );

      return (
        <Select value={field.value} onValueChange={field.onChange}>
          <SelectTrigger className="bg-[#ffffff] dark:bg-[#2a2a2e]">
            <SelectValue placeholder={t('knowledge.selectKnowledgeBase')} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="__none__">{t('knowledge.empty')}</SelectItem>
            </SelectGroup>

            {Object.entries(kbsByEngine).map(([engineName, kbs]) => (
              <SelectGroup key={engineName}>
                <SelectLabel>{engineName}</SelectLabel>
                {kbs.map((base) => (
                  <SelectItem key={base.uuid} value={base.uuid ?? ''}>
                    {base.name}
                  </SelectItem>
                ))}
              </SelectGroup>
            ))}
          </SelectContent>
        </Select>
      );

    case DynamicFormItemType.KNOWLEDGE_BASE_MULTI_SELECTOR:
      // Group KBs by RAG engine name for multi-selector
      const multiKbsByEngine = knowledgeBases.reduce(
        (acc, kb) => {
          const engineName = kb.rag_engine?.name
            ? extractI18nObject(kb.rag_engine.name)
            : t('knowledge.unknownEngine');
          if (!acc[engineName]) {
            acc[engineName] = [];
          }
          acc[engineName].push(kb);
          return acc;
        },
        {} as Record<string, typeof knowledgeBases>,
      );

      return (
        <>
          <div className="space-y-2">
            {field.value && field.value.length > 0 ? (
              <div className="space-y-2">
                {field.value.map((kbId: string) => {
                  const currentKb = knowledgeBases.find(
                    (base) => base.uuid === kbId,
                  );
                  if (!currentKb) return null;

                  return (
                    <div
                      key={kbId}
                      className="flex items-center justify-between rounded-lg border p-3 hover:bg-accent"
                    >
                      <div className="flex items-center gap-2 flex-1">
                        <div className="flex-1 min-w-0">
                          <div className="font-medium flex items-center gap-2">
                            {currentKb.name}
                            {currentKb.rag_engine?.name && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300">
                                {extractI18nObject(currentKb.rag_engine.name)}
                              </span>
                            )}
                          </div>
                          {currentKb.description && (
                            <div className="text-sm text-muted-foreground">
                              {currentKb.description}
                            </div>
                          )}
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          const newValue = field.value.filter(
                            (id: string) => id !== kbId,
                          );
                          field.onChange(newValue);
                        }}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border">
                <p className="text-sm text-muted-foreground">
                  {t('knowledge.noKnowledgeBaseSelected')}
                </p>
              </div>
            )}
          </div>

          <Button
            type="button"
            onClick={() => {
              setTempSelectedKBIds(field.value || []);
              setKbDialogOpen(true);
            }}
            variant="outline"
            className="w-full"
          >
            <Plus className="mr-2 h-4 w-4" />
            {t('knowledge.addKnowledgeBase')}
          </Button>

          {/* Knowledge Base Selection Dialog */}
          <Dialog open={kbDialogOpen} onOpenChange={setKbDialogOpen}>
            <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
              <DialogHeader>
                <DialogTitle>{t('knowledge.selectKnowledgeBases')}</DialogTitle>
              </DialogHeader>
              <div className="flex-1 overflow-y-auto space-y-4 pr-2">
                {Object.entries(multiKbsByEngine).map(([engineName, kbs]) => (
                  <div key={engineName} className="space-y-2">
                    <div className="text-sm font-semibold text-muted-foreground px-2">
                      {engineName}
                    </div>
                    {kbs.map((base) => {
                      const isSelected = tempSelectedKBIds.includes(
                        base.uuid ?? '',
                      );
                      return (
                        <div
                          key={base.uuid}
                          className="flex items-center gap-3 rounded-lg border p-3 hover:bg-accent cursor-pointer"
                          onClick={() => {
                            const kbId = base.uuid ?? '';
                            setTempSelectedKBIds((prev) =>
                              prev.includes(kbId)
                                ? prev.filter((id) => id !== kbId)
                                : [...prev, kbId],
                            );
                          }}
                        >
                          <Checkbox
                            checked={isSelected}
                            aria-label={`Select ${base.name}`}
                          />
                          <div className="flex-1">
                            <div className="font-medium">{base.name}</div>
                            {base.description && (
                              <div className="text-sm text-muted-foreground">
                                {base.description}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setKbDialogOpen(false)}
                >
                  {t('common.cancel')}
                </Button>
                <Button
                  onClick={() => {
                    field.onChange(tempSelectedKBIds);
                    setKbDialogOpen(false);
                  }}
                >
                  {t('common.confirm')}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </>
      );

    case DynamicFormItemType.BOT_SELECTOR:
      return (
        <Select value={field.value} onValueChange={field.onChange}>
          <SelectTrigger className="bg-[#ffffff] dark:bg-[#2a2a2e]">
            <SelectValue placeholder={t('bots.selectBot')} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {bots.map((bot) => (
                <SelectItem key={bot.uuid} value={bot.uuid ?? ''}>
                  {bot.name}
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
                  <div className="w-[120px] px-3 py-2 border rounded bg-gray-50 dark:bg-[#2a292e] text-gray-500 dark:text-white dark:border-gray-600">
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
                    <SelectTrigger className="w-[120px] bg-[#ffffff] dark:bg-[#2a2a2e]">
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
                <Textarea
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

    case DynamicFormItemType.FILE:
      return (
        <div className="space-y-2">
          {field.value && (field.value as IFileConfig).file_key ? (
            <Card className="py-3 max-w-full overflow-hidden bg-gray-900">
              <CardContent className="flex items-center gap-3 p-0 px-4 min-w-0">
                <div className="flex-1 min-w-0 overflow-hidden">
                  <div
                    className="text-sm font-medium truncate"
                    title={(field.value as IFileConfig).file_key}
                  >
                    {(field.value as IFileConfig).file_key}
                  </div>
                  <div className="text-xs text-muted-foreground truncate">
                    {(field.value as IFileConfig).mimetype}
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="flex-shrink-0 h-8 w-8 p-0"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    field.onChange(null);
                  }}
                  title={t('common.delete')}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    className="w-4 h-4 text-destructive"
                  >
                    <path d="M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"></path>
                  </svg>
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="relative">
              <input
                type="file"
                accept={config.accept}
                disabled={uploading}
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    const fileConfig = await handleFileUpload(file);
                    if (fileConfig) {
                      field.onChange(fileConfig);
                    }
                  }
                  e.target.value = '';
                }}
                className="hidden"
                id={`file-input-${config.name}`}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={uploading}
                onClick={() =>
                  document.getElementById(`file-input-${config.name}`)?.click()
                }
              >
                <svg
                  className="w-4 h-4 mr-2"
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M11 11V5H13V11H19V13H13V19H11V13H5V11H11Z"></path>
                </svg>
                {uploading
                  ? t('plugins.fileUpload.uploading')
                  : t('plugins.fileUpload.chooseFile')}
              </Button>
            </div>
          )}
        </div>
      );

    case DynamicFormItemType.FILE_ARRAY:
      return (
        <div className="space-y-2">
          {(field.value as IFileConfig[])?.map(
            (fileConfig: IFileConfig, index: number) => (
              <Card
                key={index}
                className="py-3 max-w-full overflow-hidden bg-gray-900"
              >
                <CardContent className="flex items-center gap-3 p-0 px-4 min-w-0">
                  <div className="flex-1 min-w-0 overflow-hidden">
                    <div
                      className="text-sm font-medium truncate"
                      title={fileConfig.file_key}
                    >
                      {fileConfig.file_key}
                    </div>
                    <div className="text-xs text-muted-foreground truncate">
                      {fileConfig.mimetype}
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="flex-shrink-0 h-8 w-8 p-0"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      const newValue = (field.value as IFileConfig[]).filter(
                        (_: IFileConfig, i: number) => i !== index,
                      );
                      field.onChange(newValue);
                    }}
                    title={t('common.delete')}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                      className="w-4 h-4 text-destructive"
                    >
                      <path d="M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"></path>
                    </svg>
                  </Button>
                </CardContent>
              </Card>
            ),
          )}
          <div className="relative">
            <input
              type="file"
              accept={config.accept}
              disabled={uploading}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (file) {
                  const fileConfig = await handleFileUpload(file);
                  if (fileConfig) {
                    field.onChange([...(field.value || []), fileConfig]);
                  }
                }
                e.target.value = '';
              }}
              className="hidden"
              id={`file-array-input-${config.name}`}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={uploading}
              onClick={() =>
                document
                  .getElementById(`file-array-input-${config.name}`)
                  ?.click()
              }
            >
              <svg
                className="w-4 h-4 mr-2"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M11 11V5H13V11H19V13H13V19H11V13H5V11H11Z"></path>
              </svg>
              {uploading
                ? t('plugins.fileUpload.uploading')
                : t('plugins.fileUpload.addFile')}
            </Button>
          </div>
        </div>
      );

    default:
      return <Input {...field} />;
  }
}
