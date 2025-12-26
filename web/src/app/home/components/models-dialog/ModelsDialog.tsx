'use client';

import { useState, useEffect } from 'react';
import {
  Plus,
  MessageSquareText,
  Cpu,
  ChevronDown,
  ChevronRight,
  Trash2,
  Settings,
  Sparkles,
  LogIn,
  Eye,
  Wrench,
} from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  LLMModel,
  EmbeddingModel,
  ModelProvider,
} from '@/app/infra/entities/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import LLMForm from './component/llm-form/LLMForm';
import EmbeddingForm from './component/embedding-form/EmbeddingForm';
import ProviderForm from './component/provider-form/ProviderForm';

interface ModelsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const LANGBOT_MODELS_PROVIDER_NAME = 'LangBot Models';

export default function ModelsDialog({
  open,
  onOpenChange,
}: ModelsDialogProps) {
  const { t } = useTranslation();

  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [accountType, setAccountType] = useState<'local' | 'space'>('local');
  const [spaceBalance] = useState<number | null>(null);

  // Expanded providers and their models
  const [expandedProviders, setExpandedProviders] = useState<Set<string>>(
    new Set(),
  );
  const [providerModels, setProviderModels] = useState<
    Record<string, { llm: LLMModel[]; embedding: EmbeddingModel[] }>
  >({});
  const [loadingProviders, setLoadingProviders] = useState<Set<string>>(
    new Set(),
  );

  // Form modals
  const [llmFormOpen, setLLMFormOpen] = useState(false);
  const [embeddingFormOpen, setEmbeddingFormOpen] = useState(false);
  const [providerFormOpen, setProviderFormOpen] = useState(false);
  const [editingLLMId, setEditingLLMId] = useState<string | null>(null);
  const [editingEmbeddingId, setEditingEmbeddingId] = useState<string | null>(
    null,
  );
  const [editingProviderId, setEditingProviderId] = useState<string | null>(
    null,
  );

  const [requesterNameList, setRequesterNameList] = useState<
    { label: string; value: string }[]
  >([]);

  useEffect(() => {
    if (open) {
      loadUserInfo();
      loadRequesterLists();
      loadProviders();
    }
  }, [open]);

  async function loadUserInfo() {
    try {
      const userInfo = await httpClient.getUserInfo();
      setAccountType(userInfo.account_type);
    } catch {
      setAccountType('local');
    }
  }

  async function loadRequesterLists() {
    try {
      const llmRequesters = await httpClient.getProviderRequesters('llm');
      setRequesterNameList(
        llmRequesters.requesters.map((item) => ({
          label: extractI18nObject(item.label),
          value: item.name,
        })),
      );
    } catch (err) {
      console.error('Failed to load requester lists', err);
    }
  }

  async function loadProviders() {
    try {
      const resp = await httpClient.getModelProviders();
      setProviders(resp.providers);
    } catch (err) {
      console.error('Failed to load providers', err);
      toast.error(t('models.loadError'));
    }
  }

  async function loadProviderModels(providerUuid: string) {
    if (loadingProviders.has(providerUuid)) return;

    setLoadingProviders((prev) => new Set(prev).add(providerUuid));
    try {
      const [llmResp, embeddingResp] = await Promise.all([
        httpClient.getProviderLLMModels(providerUuid),
        httpClient.getProviderEmbeddingModels(providerUuid),
      ]);
      setProviderModels((prev) => ({
        ...prev,
        [providerUuid]: {
          llm: llmResp.models,
          embedding: embeddingResp.models,
        },
      }));
    } catch (err) {
      console.error('Failed to load models', err);
    } finally {
      setLoadingProviders((prev) => {
        const next = new Set(prev);
        next.delete(providerUuid);
        return next;
      });
    }
  }

  function toggleProvider(providerUuid: string) {
    setExpandedProviders((prev) => {
      const next = new Set(prev);
      if (next.has(providerUuid)) {
        next.delete(providerUuid);
      } else {
        next.add(providerUuid);
        if (!providerModels[providerUuid]) {
          loadProviderModels(providerUuid);
        }
      }
      return next;
    });
  }

  function handleCreateLLM() {
    setEditingLLMId(null);
    setLLMFormOpen(true);
  }

  function handleCreateEmbedding() {
    setEditingEmbeddingId(null);
    setEmbeddingFormOpen(true);
  }

  function handleEditLLM(modelId: string) {
    setEditingLLMId(modelId);
    setLLMFormOpen(true);
  }

  function handleEditEmbedding(modelId: string) {
    setEditingEmbeddingId(modelId);
    setEmbeddingFormOpen(true);
  }

  function handleEditProvider(providerId: string) {
    setEditingProviderId(providerId);
    setProviderFormOpen(true);
  }

  async function handleDeleteProvider(providerId: string) {
    try {
      await httpClient.deleteModelProvider(providerId);
      toast.success(t('models.providerDeleted'));
      loadProviders();
    } catch (err) {
      toast.error(t('models.providerDeleteError') + (err as Error).message);
    }
  }

  async function handleDeleteLLM(modelId: string, providerUuid: string) {
    try {
      await httpClient.deleteProviderLLMModel(modelId);
      toast.success(t('models.deleteSuccess'));
      loadProviderModels(providerUuid);
      loadProviders(); // Refresh counts
    } catch (err) {
      toast.error(t('models.deleteError') + (err as Error).message);
    }
  }

  async function handleDeleteEmbedding(modelId: string, providerUuid: string) {
    try {
      await httpClient.deleteProviderEmbeddingModel(modelId);
      toast.success(t('models.deleteSuccess'));
      loadProviderModels(providerUuid);
      loadProviders();
    } catch (err) {
      toast.error(t('models.deleteError') + (err as Error).message);
    }
  }

  function handleSpaceLogin() {
    window.location.href = '/auth/space';
  }

  function getRequesterLabel(requester: string) {
    return (
      requesterNameList.find((r) => r.value === requester)?.label || requester
    );
  }

  function maskApiKey(key: string): string {
    if (!key) return '';
    if (key.length <= 8) return '****';
    return `${key.slice(0, 4)}...${key.slice(-4)}`;
  }

  // Separate LangBot Models provider
  const langbotProvider = providers.find(
    (p) => p.name === LANGBOT_MODELS_PROVIDER_NAME,
  );
  const otherProviders = providers.filter(
    (p) => p.name !== LANGBOT_MODELS_PROVIDER_NAME,
  );

  function renderProviderCard(
    provider: ModelProvider,
    isLangBotModels: boolean = false,
  ) {
    const isExpanded = expandedProviders.has(provider.uuid);
    const isLoading = loadingProviders.has(provider.uuid);
    const models = providerModels[provider.uuid];
    const canDelete =
      !isLangBotModels &&
      (provider.llm_count || 0) === 0 &&
      (provider.embedding_count || 0) === 0;
    const totalModels =
      (provider.llm_count || 0) + (provider.embedding_count || 0);

    return (
      <Card key={provider.uuid} className="mb-2">
        <Collapsible
          open={isExpanded}
          onOpenChange={() => toggleProvider(provider.uuid)}
        >
          <CardHeader className="px-4 pb-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 flex-1">
                {isLangBotModels ? (
                  <div className="p-2 bg-gradient-to-br from-purple-500 to-blue-500 rounded-lg">
                    <Sparkles className="h-5 w-5 text-white" />
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
                    <CardTitle className="text-base">
                      {isLangBotModels
                        ? provider.name
                        : getRequesterLabel(provider.requester)}
                    </CardTitle>
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
                      handleSpaceLogin();
                    }}
                  >
                    <LogIn className="h-4 w-4 mr-1" />
                    {t('models.loginWithSpace')}
                  </Button>
                )}
                {isLangBotModels && accountType === 'space' && (
                  <Badge variant="secondary">
                    {t('models.balance')}: {spaceBalance ?? '--'}
                  </Badge>
                )}
                {!isLangBotModels && (
                  <>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleEditProvider(provider.uuid);
                      }}
                    >
                      <Settings className="h-4 w-4" />
                    </Button>
                    {canDelete && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteProvider(provider.uuid);
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    )}
                  </>
                )}
              </div>
            </div>
            <CollapsibleTrigger className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground cursor-pointer mt-2">
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
          </CardHeader>
          <CollapsibleContent>
            <CardContent className="px-4">
              {isLoading ? (
                <p className="text-sm text-muted-foreground text-center py-4">
                  {t('common.loading')}...
                </p>
              ) : models ? (
                <div className="space-y-2">
                  {models.llm.map((model) => (
                    <div
                      key={model.uuid}
                      className="flex items-center justify-between py-2 px-3 rounded-md border bg-background hover:bg-accent cursor-pointer"
                      onClick={() => handleEditLLM(model.uuid)}
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium">
                          {model.name}
                        </span>
                        <Badge variant="secondary" className="text-xs">
                          {t('models.chat')}
                        </Badge>
                        {model.abilities?.includes('vision') && (
                          <Badge variant="outline" className="text-xs gap-1">
                            <Eye className="h-3 w-3" />
                          </Badge>
                        )}
                        {model.abilities?.includes('func_call') && (
                          <Badge variant="outline" className="text-xs gap-1">
                            <Wrench className="h-3 w-3" />
                          </Badge>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 flex-shrink-0"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteLLM(model.uuid, provider.uuid);
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                      </Button>
                    </div>
                  ))}
                  {models.embedding.map((model) => (
                    <div
                      key={model.uuid}
                      className="flex items-center justify-between py-2 px-3 rounded-md border bg-background hover:bg-accent cursor-pointer"
                      onClick={() => handleEditEmbedding(model.uuid)}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">
                          {model.name}
                        </span>
                        <Badge variant="secondary" className="text-xs">
                          {t('models.embedding')}
                        </Badge>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 flex-shrink-0"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteEmbedding(model.uuid, provider.uuid);
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                      </Button>
                    </div>
                  ))}
                  {models.llm.length === 0 && models.embedding.length === 0 && (
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

  // Virtual LangBot Models card if not exists
  function renderLangBotModelsCard() {
    if (langbotProvider) {
      return renderProviderCard(langbotProvider, true);
    }
    return (
      <Card className="mb-2">
        <CardHeader className="p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="p-2 bg-gradient-to-br from-purple-500 to-blue-500 rounded-lg">
                <Sparkles className="h-5 w-5 text-white" />
              </div>
              <div>
                <CardTitle className="text-base">
                  {LANGBOT_MODELS_PROVIDER_NAME}
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  {t('models.langbotModelsDescription')}
                </p>
              </div>
            </div>
            {accountType !== 'space' && (
              <Button variant="outline" size="sm" onClick={handleSpaceLogin}>
                <LogIn className="h-4 w-4 mr-1" />
                {t('models.loginWithSpace')}
              </Button>
            )}
          </div>
        </CardHeader>
      </Card>
    );
  }

  function handleFormClose() {
    setLLMFormOpen(false);
    setEmbeddingFormOpen(false);
    setProviderFormOpen(false);
    loadProviders();
    // Refresh expanded providers
    expandedProviders.forEach((uuid) => loadProviderModels(uuid));
  }

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(newOpen) => {
          if (
            !newOpen &&
            (llmFormOpen || embeddingFormOpen || providerFormOpen)
          )
            return;
          onOpenChange(newOpen);
        }}
      >
        <DialogContent className="overflow-hidden p-0 h-[80vh] flex flex-col">
          <DialogHeader className="px-6 pt-6 pb-0">
            <DialogTitle>{t('models.title')}</DialogTitle>
          </DialogHeader>

          <div className="flex-1 flex flex-col overflow-hidden px-6 pb-6 mt-4">
            {/* Fixed LangBot Models Card */}
            <div className="flex-shrink-0">{renderLangBotModelsCard()}</div>

            {/* Add Model Button */}
            <div className="flex-shrink-0 mb-3 flex justify-end">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="sm" variant="outline">
                    <Plus className="h-4 w-4 mr-1" />
                    {t('models.addModel')}
                    <ChevronDown className="h-4 w-4 ml-1" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={handleCreateLLM}>
                    <MessageSquareText className="h-4 w-4 mr-2" />
                    {t('models.addLLMModel')}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleCreateEmbedding}>
                    <Cpu className="h-4 w-4 mr-2" />
                    {t('models.addEmbeddingModel')}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {/* Scrollable Provider List */}
            <div className="flex-1 overflow-auto">
              {otherProviders.map((p) => renderProviderCard(p))}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={llmFormOpen} onOpenChange={setLLMFormOpen}>
        <DialogContent className="w-[700px] max-h-[90vh] overflow-y-auto p-6">
          <DialogHeader>
            <DialogTitle>
              {editingLLMId ? t('models.editModel') : t('models.createModel')}
            </DialogTitle>
          </DialogHeader>
          <LLMForm
            editMode={!!editingLLMId}
            initLLMId={editingLLMId || undefined}
            providers={providers}
            onFormSubmit={handleFormClose}
            onFormCancel={() => setLLMFormOpen(false)}
            onLLMDeleted={handleFormClose}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={embeddingFormOpen} onOpenChange={setEmbeddingFormOpen}>
        <DialogContent className="w-[700px] max-h-[90vh] overflow-y-auto p-6">
          <DialogHeader>
            <DialogTitle>
              {editingEmbeddingId
                ? t('embedding.editModel')
                : t('embedding.createModel')}
            </DialogTitle>
          </DialogHeader>
          <EmbeddingForm
            editMode={!!editingEmbeddingId}
            initEmbeddingId={editingEmbeddingId || undefined}
            providers={providers}
            onFormSubmit={handleFormClose}
            onFormCancel={() => setEmbeddingFormOpen(false)}
            onEmbeddingDeleted={handleFormClose}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={providerFormOpen} onOpenChange={setProviderFormOpen}>
        <DialogContent className="w-[600px] p-6">
          <DialogHeader>
            <DialogTitle>{t('models.editProvider')}</DialogTitle>
          </DialogHeader>
          <ProviderForm
            providerId={editingProviderId || undefined}
            onFormSubmit={handleFormClose}
            onFormCancel={() => setProviderFormOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </>
  );
}
