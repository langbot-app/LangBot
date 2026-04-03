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
import {
  Plus,
  X,
  Eye,
  Wrench,
  Trash2,
  Sparkles,
  Info,
  Settings,
  ChevronDown,
} from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import ModelsDialog from '@/app/home/components/models-dialog/ModelsDialog';

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
  const [modelsDialogOpen, setModelsDialogOpen] = useState(false);

  const fetchLlmModels = () => {
    httpClient
      .getProviderLLMModels()
      .then((resp) => {
        setLlmModels(resp.models);
      })
      .catch((err) => {
        toast.error(t('models.getModelListError') + err.msg);
      });
  };

  const handleModelsDialogChange = (open: boolean) => {
    setModelsDialogOpen(open);
    if (!open) {
      fetchLlmModels();
    }
  };

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

  // Whether to show Space login CTA in model selectors
  const showSpaceLoginCTA =
    !systemInfo.disable_models_service && userInfo?.account_type !== 'space';

  const handleSpaceLogin = () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        toast.error(t('common.error'));
        return;
      }
      const currentOrigin = window.location.origin;
      const redirectUri = `${currentOrigin}/auth/space/callback?mode=bind`;
      httpClient
        .getSpaceAuthorizeUrl(redirectUri, token)
        .then((response) => {
          window.location.href = response.authorize_url;
        })
        .catch(() => {
          toast.error(t('common.spaceLoginFailed'));
        });
    } catch {
      toast.error(t('common.spaceLoginFailed'));
    }
  };

  useEffect(() => {
    if (config.type === DynamicFormItemType.LLM_MODEL_SELECTOR) {
      fetchLlmModels();
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
          toast.error(t('embedding.getModelListError') + err.msg);
        });
    }
  }, [config.type]);

  useEffect(() => {
    if (config.type === DynamicFormItemType.MODEL_FALLBACK_SELECTOR) {
      fetchLlmModels();
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
          toast.error(t('knowledge.getKnowledgeBaseListError') + err.msg);
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
          toast.error(t('bots.getBotListError') + err.msg);
        });
    }
  }, [config.type]);

  switch (config.type) {
    case DynamicFormItemType.INT:
    case DynamicFormItemType.FLOAT:
      return (
        <Input
          type="number"
          className="max-w-xs"
          {...field}
          onChange={(e) => field.onChange(Number(e.target.value))}
        />
      );

    case DynamicFormItemType.STRING:
      if (config.options && config.options.length > 0) {
        return (
          <div className="flex items-center gap-1.5 max-w-md">
            <Input className="flex-1" {...field} />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  type="button"
                  className="h-9 w-9 shrink-0 text-muted-foreground"
                >
                  <ChevronDown className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {config.options.map((option) => (
                  <DropdownMenuItem
                    key={option.name}
                    onClick={() => field.onChange(option.name)}
                  >
                    <div className="flex flex-col gap-0.5">
                      <span>{extractI18nObject(option.label)}</span>
                      <span className="text-xs text-muted-foreground">
                        {option.name}
                      </span>
                    </div>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        );
      }
      return <Input className="max-w-md" {...field} />;

    case DynamicFormItemType.TEXT:
      return <Textarea {...field} className="min-h-[120px] max-w-2xl" />;

    case DynamicFormItemType.BOOLEAN:
      return <Switch checked={field.value} onCheckedChange={field.onChange} />;

    case DynamicFormItemType.STRING_ARRAY:
      return (
        <div className="space-y-2 max-w-md">
          {field.value.map((item: string, index: number) => (
            <div key={index} className="flex gap-1.5 items-center">
              <Input
                className="flex-1"
                value={item}
                onChange={(e) => {
                  const newValue = [...field.value];
                  newValue[index] = e.target.value;
                  field.onChange(newValue);
                }}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="shrink-0 text-muted-foreground hover:text-destructive"
                onClick={() => {
                  const newValue = field.value.filter(
                    (_: string, i: number) => i !== index,
                  );
                  field.onChange(newValue);
                }}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            className="w-full border-dashed text-muted-foreground hover:text-foreground"
            onClick={() => {
              field.onChange([...field.value, '']);
            }}
          >
            <Plus className="size-4 mr-1.5" />
            {t('common.add')}
          </Button>
        </div>
      );

    case DynamicFormItemType.SELECT:
      return (
        <Select value={field.value} onValueChange={field.onChange}>
          <SelectTrigger className="max-w-md bg-[#ffffff] dark:bg-[#2a2a2e]">
            <SelectValue placeholder={t('common.select')} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {config.options?.map((option) => (
                <SelectItem
                  key={option.name}
                  value={option.name}
                  description={option.name}
                >
                  {extractI18nObject(option.label)}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      );

    case DynamicFormItemType.LLM_MODEL_SELECTOR:
      // Separate space models from regular models
      const spaceModels = llmModels.filter(
        (m) => m.provider?.requester === 'space-chat-completions',
      );
      const regularModels = llmModels.filter(
        (m) => m.provider?.requester !== 'space-chat-completions',
      );

      // Group regular models by provider
      const groupedModels = regularModels.reduce(
        (acc, model) => {
          const providerName =
            model.provider?.name || model.provider?.requester || 'Unknown';
          if (!acc[providerName]) acc[providerName] = [];
          acc[providerName].push(model);
          return acc;
        },
        {} as Record<string, LLMModel[]>,
      );

      // Group space models by provider (for logged-in users)
      const groupedSpaceModels = spaceModels.reduce(
        (acc, model) => {
          const providerName =
            model.provider?.name || model.provider?.requester || 'Unknown';
          if (!acc[providerName]) acc[providerName] = [];
          acc[providerName].push(model);
          return acc;
        },
        {} as Record<string, LLMModel[]>,
      );

      // Hardcoded preview model names for CTA when no space models are synced
      const previewModelNames = [
        'gpt-4o',
        'claude-sonnet-4-20250514',
        'deepseek-chat',
        'gemini-2.5-flash',
        'qwen-plus',
      ];

      return (
        <div className="max-w-md flex items-center gap-1.5">
          <div className="flex-1">
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
                {/* Space models section */}
                {showSpaceLoginCTA ? (
                  <SelectGroup>
                    <SelectLabel>
                      <span className="inline-flex items-center gap-1.5">
                        <Sparkles className="h-3.5 w-3.5 text-purple-500" />
                        {t('models.langbotModels')}
                        <Tooltip>
                          <TooltipTrigger
                            asChild
                            onMouseDown={(e) => e.preventDefault()}
                          >
                            <Info className="h-3 w-3 text-muted-foreground cursor-help" />
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-[240px]">
                            {t('models.spaceTrialTooltip')}
                          </TooltipContent>
                        </Tooltip>
                      </span>
                    </SelectLabel>
                    <div
                      className="relative"
                      onMouseDown={(e) => e.preventDefault()}
                    >
                      {/* Preview models (first 3 visible, rest blurred) */}
                      {(spaceModels.length > 0
                        ? spaceModels.map((m) => m.name)
                        : previewModelNames
                      )
                        .slice(0, 3)
                        .map((name) => (
                          <div
                            key={name}
                            className="relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm text-muted-foreground/60"
                          >
                            {name}
                          </div>
                        ))}
                      {/* Blurred remaining models with login overlay */}
                      <div className="relative">
                        <div
                          className="select-none overflow-hidden"
                          style={{ maxHeight: '3rem' }}
                        >
                          {(spaceModels.length > 0
                            ? spaceModels.map((m) => m.name)
                            : previewModelNames
                          )
                            .slice(3)
                            .map((name) => (
                              <div
                                key={name}
                                className="flex w-full items-center py-1.5 pl-8 pr-2 text-sm text-muted-foreground/40 blur-[2px]"
                              >
                                {name}
                              </div>
                            ))}
                        </div>
                        {/* Login overlay */}
                        <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-b from-transparent to-background/80">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="h-7 text-xs px-3 gap-1.5 shadow-sm"
                            onMouseDown={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              handleSpaceLogin();
                            }}
                          >
                            <Sparkles className="h-3 w-3" />
                            {t('models.unlockModels')}
                          </Button>
                        </div>
                      </div>
                    </div>
                  </SelectGroup>
                ) : !systemInfo.disable_models_service ? (
                  // User is logged into Space — show space models normally
                  Object.entries(groupedSpaceModels).map(
                    ([providerName, models]) => (
                      <SelectGroup key={providerName}>
                        <SelectLabel>
                          <span className="inline-flex items-center gap-1.5">
                            <Sparkles className="h-3.5 w-3.5 text-purple-500" />
                            {providerName}
                          </span>
                        </SelectLabel>
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
                    ),
                  )
                ) : null}
              </SelectContent>
            </Select>
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-9 w-9 shrink-0"
                onClick={() => setModelsDialogOpen(true)}
              >
                <Settings className="h-4 w-4 text-muted-foreground" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">{t('models.title')}</TooltipContent>
          </Tooltip>
          <ModelsDialog
            open={modelsDialogOpen}
            onOpenChange={handleModelsDialogChange}
          />
        </div>
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
        <div className="max-w-md">
          <Select value={field.value} onValueChange={field.onChange}>
            <SelectTrigger className="bg-[#ffffff] dark:bg-[#2a2a2e]">
              <SelectValue placeholder={t('knowledge.selectEmbeddingModel')} />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(groupedEmbeddingModels).map(
                ([providerName, models]) => (
                  <SelectGroup key={providerName}>
                    <SelectLabel>{providerName}</SelectLabel>
                    {models.map((model) => (
                      <SelectItem key={model.uuid} value={model.uuid}>
                        {model.name}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ),
              )}
            </SelectContent>
          </Select>
        </div>
      );

    case DynamicFormItemType.MODEL_FALLBACK_SELECTOR: {
      // Separate space models from regular models
      const fbSpaceModels = llmModels.filter(
        (m) => m.provider?.requester === 'space-chat-completions',
      );
      const fbRegularModels = llmModels.filter(
        (m) => m.provider?.requester !== 'space-chat-completions',
      );

      // Group regular models by provider
      const groupedModelsForFallback = fbRegularModels.reduce(
        (acc, model) => {
          const providerName =
            model.provider?.name || model.provider?.requester || 'Unknown';
          if (!acc[providerName]) acc[providerName] = [];
          acc[providerName].push(model);
          return acc;
        },
        {} as Record<string, LLMModel[]>,
      );

      // Group space models by provider (for logged-in users)
      const fbGroupedSpaceModels = fbSpaceModels.reduce(
        (acc, model) => {
          const providerName =
            model.provider?.name || model.provider?.requester || 'Unknown';
          if (!acc[providerName]) acc[providerName] = [];
          acc[providerName].push(model);
          return acc;
        },
        {} as Record<string, LLMModel[]>,
      );

      // Hardcoded preview model names for CTA
      const fbPreviewModelNames = [
        'gpt-4o',
        'claude-sonnet-4-20250514',
        'deepseek-chat',
        'gemini-2.5-flash',
        'qwen-plus',
      ];

      const rawModelValue = field.value;
      const modelValue: { primary: string; fallbacks: string[] } =
        rawModelValue != null &&
        typeof rawModelValue === 'object' &&
        !Array.isArray(rawModelValue)
          ? {
              primary:
                typeof (rawModelValue as Record<string, unknown>).primary ===
                'string'
                  ? ((rawModelValue as Record<string, unknown>)
                      .primary as string)
                  : '',
              fallbacks: Array.isArray(
                (rawModelValue as Record<string, unknown>).fallbacks,
              )
                ? (
                    (rawModelValue as Record<string, unknown>)
                      .fallbacks as unknown[]
                  ).filter((v): v is string => typeof v === 'string')
                : [],
            }
          : {
              primary: typeof rawModelValue === 'string' ? rawModelValue : '',
              fallbacks: [],
            };

      const renderModelSelect = (
        value: string,
        onChange: (val: string) => void,
        placeholder: string,
      ) => (
        <Select value={value} onValueChange={onChange}>
          <SelectTrigger className="bg-[#ffffff] dark:bg-[#2a2a2e]">
            <SelectValue placeholder={placeholder} />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(groupedModelsForFallback).map(
              ([providerName, models]) => (
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
              ),
            )}
            {/* Space models section */}
            {showSpaceLoginCTA ? (
              <SelectGroup>
                <SelectLabel>
                  <span className="inline-flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5 text-purple-500" />
                    {t('models.langbotModels')}
                    <Tooltip>
                      <TooltipTrigger
                        asChild
                        onMouseDown={(e) => e.preventDefault()}
                      >
                        <Info className="h-3 w-3 text-muted-foreground cursor-help" />
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-[240px]">
                        {t('models.spaceTrialTooltip')}
                      </TooltipContent>
                    </Tooltip>
                  </span>
                </SelectLabel>
                <div
                  className="relative"
                  onMouseDown={(e) => e.preventDefault()}
                >
                  {/* Preview models (first 3 visible, rest blurred) */}
                  {(fbSpaceModels.length > 0
                    ? fbSpaceModels.map((m) => m.name)
                    : fbPreviewModelNames
                  )
                    .slice(0, 3)
                    .map((name) => (
                      <div
                        key={name}
                        className="relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm text-muted-foreground/60"
                      >
                        {name}
                      </div>
                    ))}
                  {/* Blurred remaining models with login overlay */}
                  <div className="relative">
                    <div
                      className="select-none overflow-hidden"
                      style={{ maxHeight: '3rem' }}
                    >
                      {(fbSpaceModels.length > 0
                        ? fbSpaceModels.map((m) => m.name)
                        : fbPreviewModelNames
                      )
                        .slice(3)
                        .map((name) => (
                          <div
                            key={name}
                            className="flex w-full items-center py-1.5 pl-8 pr-2 text-sm text-muted-foreground/40 blur-[2px]"
                          >
                            {name}
                          </div>
                        ))}
                    </div>
                    {/* Login overlay */}
                    <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-b from-transparent to-background/80">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs px-3 gap-1.5 shadow-sm"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleSpaceLogin();
                        }}
                      >
                        <Sparkles className="h-3 w-3" />
                        {t('models.unlockModels')}
                      </Button>
                    </div>
                  </div>
                </div>
              </SelectGroup>
            ) : !systemInfo.disable_models_service ? (
              // User is logged into Space — show space models normally
              Object.entries(fbGroupedSpaceModels).map(
                ([providerName, models]) => (
                  <SelectGroup key={providerName}>
                    <SelectLabel>
                      <span className="inline-flex items-center gap-1.5">
                        <Sparkles className="h-3.5 w-3.5 text-purple-500" />
                        {providerName}
                      </span>
                    </SelectLabel>
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
                ),
              )
            ) : null}
          </SelectContent>
        </Select>
      );

      const updateValue = (patch: Partial<typeof modelValue>) => {
        field.onChange({ ...modelValue, ...patch });
      };

      const addFallbackModel = () => {
        updateValue({ fallbacks: [...modelValue.fallbacks, ''] });
      };

      const updateFallbackModel = (index: number, value: string) => {
        const updated = [...modelValue.fallbacks];
        updated[index] = value;
        updateValue({ fallbacks: updated });
      };

      const removeFallbackModel = (index: number) => {
        const updated = [...modelValue.fallbacks];
        updated.splice(index, 1);
        updateValue({ fallbacks: updated });
      };

      const moveFallbackModel = (index: number, direction: 'up' | 'down') => {
        const updated = [...modelValue.fallbacks];
        const newIndex = direction === 'up' ? index - 1 : index + 1;
        if (newIndex < 0 || newIndex >= updated.length) return;
        [updated[index], updated[newIndex]] = [
          updated[newIndex],
          updated[index],
        ];
        updateValue({ fallbacks: updated });
      };

      return (
        <div className="space-y-3">
          {/* Primary model selector */}
          <div>
            <p className="text-xs text-muted-foreground mb-1">
              {t('models.fallback.primary')}
            </p>
            <div className="flex items-center gap-1.5">
              <div className="flex-1">
                {renderModelSelect(
                  modelValue.primary,
                  (val) => updateValue({ primary: val }),
                  t('models.selectModel'),
                )}
              </div>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 shrink-0"
                    onClick={() => setModelsDialogOpen(true)}
                  >
                    <Settings className="h-4 w-4 text-muted-foreground" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  {t('models.title')}
                </TooltipContent>
              </Tooltip>
              <ModelsDialog
                open={modelsDialogOpen}
                onOpenChange={handleModelsDialogChange}
              />
            </div>
          </div>

          {/* Fallback models */}
          {modelValue.fallbacks.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                {t('models.fallback.fallbackList')}
              </p>
              {modelValue.fallbacks.map((fbUuid: string, index: number) => (
                <div key={index} className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground w-4 shrink-0">
                    {index + 1}.
                  </span>
                  <div className="flex-1">
                    {renderModelSelect(
                      fbUuid,
                      (val) => updateFallbackModel(index, val),
                      t('models.selectModel'),
                    )}
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0"
                      onClick={() => moveFallbackModel(index, 'up')}
                      disabled={index === 0}
                    >
                      ↑
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0"
                      onClick={() => moveFallbackModel(index, 'down')}
                      disabled={index === modelValue.fallbacks.length - 1}
                    >
                      ↓
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      onClick={() => removeFallbackModel(index)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Add fallback button */}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-full border-dashed text-muted-foreground hover:text-foreground"
            onClick={addFallbackModel}
          >
            <Plus className="size-4 mr-1.5" />
            {t('models.fallback.addFallback')}
          </Button>
        </div>
      );
    }

    case DynamicFormItemType.KNOWLEDGE_BASE_SELECTOR:
      // Group KBs by Knowledge Engine name
      const kbsByEngine = knowledgeBases.reduce(
        (acc, kb) => {
          const engineName = kb.knowledge_engine?.name
            ? extractI18nObject(kb.knowledge_engine.name)
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
            {field.value && field.value !== '__none__' ? (
              (() => {
                const selectedKb = knowledgeBases.find(
                  (kb) => kb.uuid === field.value,
                );
                return (
                  <div className="flex items-center gap-2">
                    {selectedKb?.emoji && (
                      <span className="text-sm shrink-0">
                        {selectedKb.emoji}
                      </span>
                    )}
                    <span>{selectedKb?.name ?? field.value}</span>
                  </div>
                );
              })()
            ) : (
              <SelectValue placeholder={t('knowledge.selectKnowledgeBase')} />
            )}
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
                    <div className="flex items-center gap-2">
                      {base.emoji && (
                        <span className="text-sm shrink-0">{base.emoji}</span>
                      )}
                      <span>{base.name}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectGroup>
            ))}
          </SelectContent>
        </Select>
      );

    case DynamicFormItemType.KNOWLEDGE_BASE_MULTI_SELECTOR:
      // Group KBs by Knowledge Engine name for multi-selector
      const multiKbsByEngine = knowledgeBases.reduce(
        (acc, kb) => {
          const engineName = kb.knowledge_engine?.name
            ? extractI18nObject(kb.knowledge_engine.name)
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
                            {currentKb.emoji && (
                              <span className="text-sm shrink-0">
                                {currentKb.emoji}
                              </span>
                            )}
                            {currentKb.name}
                            {currentKb.knowledge_engine?.name && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300">
                                {extractI18nObject(
                                  currentKb.knowledge_engine.name,
                                )}
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
                            <div className="font-medium flex items-center gap-2">
                              {base.emoji && (
                                <span className="text-sm shrink-0">
                                  {base.emoji}
                                </span>
                              )}
                              {base.name}
                            </div>
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

    case DynamicFormItemType.PROMPT_EDITOR: {
      // Guard: field.value may be undefined when the form resets or
      // initialValues haven't propagated yet. Fall back to a default
      // single system-prompt entry to prevent the .map() crash.
      const promptItems: { role: string; content: string }[] = Array.isArray(
        field.value,
      )
        ? field.value
        : [{ role: 'system', content: '' }];
      return (
        <div className="space-y-2">
          {promptItems.map(
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
                      const newValue = [...(field.value ?? promptItems)];
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
                    const newValue = [...(field.value ?? promptItems)];
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
                      const newValue = (field.value ?? promptItems).filter(
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
              field.onChange([
                ...(field.value ?? promptItems),
                { role: 'user', content: '' },
              ]);
            }}
          >
            {t('common.addRound')}
          </Button>
        </div>
      );
    }

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
