import { useState } from 'react';
import {
  Plus,
  ChevronDown,
  ChevronRight,
  Trash2,
  Settings,
  LogIn,
} from 'lucide-react';
import { httpClient, systemInfo } from '@/app/infra/http/HttpClient';
import { ModelProvider } from '@/app/infra/entities/api';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useTranslation } from 'react-i18next';
import langbotIcon from '@/app/assets/langbot-logo.webp';
import {
  ExtraArg,
  ModelType,
  ScanModelsResult,
  SelectedScannedModel,
  TestResult,
  ProviderModels,
} from '../types';
import ModelItem from './ModelItem';
import AddModelPopover from './AddModelPopover';

interface ProviderCardProps {
  provider: ModelProvider;
  isLangBotModels?: boolean;
  isExpanded: boolean;
  isLoading: boolean;
  models?: ProviderModels;
  accountType: 'local' | 'space';
  spaceCredits: number | null;
  // Popover states
  addModelPopoverOpen: string | null;
  editModelPopoverOpen: string | null;
  deleteConfirmOpen: string | null;
  // Handlers
  onToggle: () => void;
  onEditProvider: () => void;
  onDeleteProvider: () => void;
  onSpaceLogin: () => void;
  onOpenAddModel: () => void;
  onCloseAddModel: () => void;
  onAddModel: (
    modelType: ModelType,
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) => Promise<void>;
  onScanModels: (modelType: ModelType) => Promise<ScanModelsResult>;
  onAddScannedModels: (
    modelType: ModelType,
    models: SelectedScannedModel[],
  ) => Promise<void>;
  onOpenEditModel: (modelId: string) => void;
  onCloseEditModel: () => void;
  onUpdateModel: (
    modelId: string,
    modelType: ModelType,
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) => Promise<void>;
  onOpenDeleteConfirm: (modelId: string) => void;
  onCloseDeleteConfirm: () => void;
  onDeleteModel: (modelId: string, modelType: ModelType) => Promise<void>;
  onTestModel: (
    name: string,
    modelType: ModelType,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) => Promise<void>;
  isSubmitting: boolean;
  isTesting: boolean;
  testResult: TestResult | null;
  onResetTestResult: () => void;
}

function maskApiKey(key: string): string {
  if (!key) return '';
  if (key.length <= 8) return '****';
  return `${key.slice(0, 4)}...${key.slice(-4)}`;
}

export default function ProviderCard({
  provider,
  isLangBotModels = false,
  isExpanded,
  isLoading,
  models,
  accountType,
  spaceCredits,
  addModelPopoverOpen,
  editModelPopoverOpen,
  deleteConfirmOpen,
  onToggle,
  onEditProvider,
  onDeleteProvider,
  onSpaceLogin,
  onOpenAddModel,
  onCloseAddModel,
  onAddModel,
  onScanModels,
  onAddScannedModels,
  onOpenEditModel,
  onCloseEditModel,
  onUpdateModel,
  onOpenDeleteConfirm,
  onCloseDeleteConfirm,
  onDeleteModel,
  onTestModel,
  isSubmitting,
  isTesting,
  testResult,
  onResetTestResult,
}: ProviderCardProps) {
  const { t } = useTranslation();
  const [deleteProviderConfirmOpen, setDeleteProviderConfirmOpen] =
    useState(false);

  const canDelete =
    !isLangBotModels &&
    (provider.llm_count || 0) === 0 &&
    (provider.embedding_count || 0) === 0 &&
    (provider.rerank_count || 0) === 0;
  const totalModels =
    (provider.llm_count || 0) + (provider.embedding_count || 0) + (provider.rerank_count || 0);

  return (
    <Card className="mb-2">
      <Collapsible open={isExpanded} onOpenChange={onToggle}>
        <CardHeader className="py-0 px-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-1">
              {isLangBotModels ? (
                <div className="w-9 h-9 rounded-lg overflow-hidden flex-shrink-0">
                  <img
                    src={langbotIcon}
                    alt="LangBot"
                    className="w-full h-full object-cover"
                  />
                </div>
              ) : (
                <img
                  src={httpClient.getProviderRequesterIconURL(
                    provider.requester,
                  )}
                  alt={provider.name}
                  className="h-9 w-9 rounded-lg"
                />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-base">{provider.name}</CardTitle>
                  <Badge variant="outline" className="text-xs">
                    {t('models.modelsCount', { count: totalModels })}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground truncate">
                  {isLangBotModels ? (
                    t('models.langbotModelsDescription')
                  ) : (
                    <>
                      {provider.base_url}
                      {provider.base_url &&
                        provider.api_keys?.length > 0 &&
                        ' · '}
                      {provider.api_keys?.length > 0 &&
                        maskApiKey(provider.api_keys[0])}
                    </>
                  )}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1 ml-2">
              {isLangBotModels && accountType !== 'space' && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSpaceLogin();
                  }}
                >
                  <LogIn className="h-4 w-4 mr-1" />
                  {t('models.loginWithSpace')}
                </Button>
              )}
              {isLangBotModels &&
                accountType === 'space' &&
                spaceCredits !== null && (
                  <div className="flex items-center gap-1 border rounded-md px-2 h-8 text-sm mr-2">
                    <span>
                      {(spaceCredits / 5000).toFixed(2)} {t('models.credits')}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5"
                      onClick={(e) => {
                        e.stopPropagation();
                        window.open(
                          `${systemInfo.cloud_service_url}/profile?tab=billing`,
                          '_blank',
                        );
                      }}
                    >
                      <Plus className="h-3 w-3" />
                    </Button>
                  </div>
                )}
              {!isLangBotModels && (
                <>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={(e) => {
                      e.stopPropagation();
                      onEditProvider();
                    }}
                  >
                    <Settings className="h-4 w-4" />
                  </Button>
                  {canDelete && (
                    <Popover
                      open={deleteProviderConfirmOpen}
                      onOpenChange={setDeleteProviderConfirmOpen}
                    >
                      <PopoverTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={(e) => {
                            e.stopPropagation();
                          }}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent
                        className="w-64"
                        align="end"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div className="space-y-3">
                          <p className="text-sm">
                            {t('models.deleteProviderConfirmation')}
                          </p>
                          <div className="flex gap-2 justify-end">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() =>
                                setDeleteProviderConfirmOpen(false)
                              }
                            >
                              {t('common.cancel')}
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => {
                                onDeleteProvider();
                                setDeleteProviderConfirmOpen(false);
                              }}
                            >
                              {t('common.delete')}
                            </Button>
                          </div>
                        </div>
                      </PopoverContent>
                    </Popover>
                  )}
                </>
              )}
            </div>
          </div>
          <div className="flex items-center justify-between mt-2">
            {totalModels > 0 ? (
              <CollapsibleTrigger className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground cursor-pointer">
                {isExpanded ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronRight className="h-3 w-3" />
                )}
                <span>
                  {isExpanded
                    ? t('models.collapseModels')
                    : t('models.expandModels')}
                </span>
              </CollapsibleTrigger>
            ) : (
              <div />
            )}
            {!isLangBotModels && (
              <AddModelPopover
                isOpen={addModelPopoverOpen === provider.uuid}
                onOpen={onOpenAddModel}
                onClose={onCloseAddModel}
                onAddModel={onAddModel}
                onScanModels={onScanModels}
                onAddScannedModels={onAddScannedModels}
                onTestModel={onTestModel}
                isSubmitting={isSubmitting}
                isTesting={isTesting}
                testResult={testResult}
                onResetTestResult={onResetTestResult}
              />
            )}
          </div>
        </CardHeader>
        <CollapsibleContent>
          <CardContent className="px-4 mt-2">
            {isLoading ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                {t('common.loading')}...
              </p>
            ) : models ? (
              <div className="space-y-2">
                {models.llm.map((model) => (
                  <ModelItem
                    key={model.uuid}
                    model={model}
                    modelType="llm"
                    isLangBotModels={isLangBotModels}
                    editModelPopoverOpen={editModelPopoverOpen}
                    deleteConfirmOpen={deleteConfirmOpen}
                    onOpenEditModel={onOpenEditModel}
                    onCloseEditModel={onCloseEditModel}
                    onOpenDeleteConfirm={onOpenDeleteConfirm}
                    onCloseDeleteConfirm={onCloseDeleteConfirm}
                    onDeleteModel={() => onDeleteModel(model.uuid, 'llm')}
                    onUpdateModel={(name, abilities, extraArgs) =>
                      onUpdateModel(
                        model.uuid,
                        'llm',
                        name,
                        abilities,
                        extraArgs,
                      )
                    }
                    onTestModel={(name, abilities, extraArgs) =>
                      onTestModel(name, 'llm', abilities, extraArgs)
                    }
                    isSubmitting={isSubmitting}
                    isTesting={isTesting}
                    testResult={testResult}
                    onResetTestResult={onResetTestResult}
                  />
                ))}
                {models.embedding.map((model) => (
                  <ModelItem
                    key={model.uuid}
                    model={model}
                    modelType="embedding"
                    isLangBotModels={isLangBotModels}
                    editModelPopoverOpen={editModelPopoverOpen}
                    deleteConfirmOpen={deleteConfirmOpen}
                    onOpenEditModel={onOpenEditModel}
                    onCloseEditModel={onCloseEditModel}
                    onOpenDeleteConfirm={onOpenDeleteConfirm}
                    onCloseDeleteConfirm={onCloseDeleteConfirm}
                    onDeleteModel={() => onDeleteModel(model.uuid, 'embedding')}
                    onUpdateModel={(name, abilities, extraArgs) =>
                      onUpdateModel(
                        model.uuid,
                        'embedding',
                        name,
                        abilities,
                        extraArgs,
                      )
                    }
                    onTestModel={(name, abilities, extraArgs) =>
                      onTestModel(name, 'embedding', abilities, extraArgs)
                    }
                    isSubmitting={isSubmitting}
                    isTesting={isTesting}
                    testResult={testResult}
                    onResetTestResult={onResetTestResult}
                  />
                ))}
                {models.rerank.map((model) => (
                  <ModelItem
                    key={model.uuid}
                    model={model}
                    modelType="rerank"
                    isLangBotModels={isLangBotModels}
                    editModelPopoverOpen={editModelPopoverOpen}
                    deleteConfirmOpen={deleteConfirmOpen}
                    onOpenEditModel={onOpenEditModel}
                    onCloseEditModel={onCloseEditModel}
                    onOpenDeleteConfirm={onOpenDeleteConfirm}
                    onCloseDeleteConfirm={onCloseDeleteConfirm}
                    onDeleteModel={() => onDeleteModel(model.uuid, 'rerank')}
                    onUpdateModel={(name, abilities, extraArgs) =>
                      onUpdateModel(
                        model.uuid,
                        'rerank',
                        name,
                        abilities,
                        extraArgs,
                      )
                    }
                    onTestModel={(name, abilities, extraArgs) =>
                      onTestModel(name, 'rerank', abilities, extraArgs)
                    }
                    isSubmitting={isSubmitting}
                    isTesting={isTesting}
                    testResult={testResult}
                    onResetTestResult={onResetTestResult}
                  />
                ))}
                {models.llm.length === 0 && models.embedding.length === 0 && models.rerank.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    {t('models.noModels')}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">
                {t('models.noModels')}
              </p>
            )}
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}
