'use client';

import { useState, useEffect } from 'react';
import { Plus, Boxes } from 'lucide-react';
import { httpClient, systemInfo } from '@/app/infra/http/HttpClient';
import { ModelProvider } from '@/app/infra/entities/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import ProviderForm from './component/provider-form/ProviderForm';
import { ProviderCard } from './components';
import {
  ExtraArg,
  ModelType,
  TestResult,
  ProviderModels,
  LANGBOT_MODELS_PROVIDER_REQUESTER,
} from './types';
import { CustomApiError } from '@/app/infra/entities/common';

interface ModelsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function convertExtraArgsToObject(
  args: ExtraArg[],
): Record<string, string | number | boolean> {
  const obj: Record<string, string | number | boolean> = {};
  args.forEach((arg) => {
    if (arg.key.trim()) {
      if (arg.type === 'number') obj[arg.key] = Number(arg.value);
      else if (arg.type === 'boolean') obj[arg.key] = arg.value === 'true';
      else obj[arg.key] = arg.value;
    }
  });
  return obj;
}

export default function ModelsDialog({
  open,
  onOpenChange,
}: ModelsDialogProps) {
  const { t } = useTranslation();

  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [accountType, setAccountType] = useState<'local' | 'space'>('local');
  const [spaceCredits, setSpaceCredits] = useState<number | null>(null);

  // Expanded providers and their models
  const [expandedProviders, setExpandedProviders] = useState<Set<string>>(
    new Set(),
  );
  const [providerModels, setProviderModels] = useState<
    Record<string, ProviderModels>
  >({});
  const [loadingProviders, setLoadingProviders] = useState<Set<string>>(
    new Set(),
  );

  // Provider form modal
  const [providerFormOpen, setProviderFormOpen] = useState(false);
  const [editingProviderId, setEditingProviderId] = useState<string | null>(
    null,
  );

  // Popover states
  const [addModelPopoverOpen, setAddModelPopoverOpen] = useState<string | null>(
    null,
  );
  const [editModelPopoverOpen, setEditModelPopoverOpen] = useState<
    string | null
  >(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState<string | null>(
    null,
  );

  // Form states
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  // Track if providers have been loaded initially
  const [providersLoaded, setProvidersLoaded] = useState(false);

  // Separate LangBot Models provider (hide when models service is disabled)
  const langbotProvider = systemInfo.disable_models_service
    ? undefined
    : providers.find((p) => p.requester === LANGBOT_MODELS_PROVIDER_REQUESTER);
  const otherProviders = providers.filter(
    (p) => p.requester !== LANGBOT_MODELS_PROVIDER_REQUESTER,
  );

  useEffect(() => {
    if (open) {
      loadUserInfo();
      loadProviders();
    }
  }, [open]);

  // Auto-expand LangBot Models when no external providers exist
  useEffect(() => {
    if (providersLoaded && langbotProvider && otherProviders.length === 0) {
      if (!expandedProviders.has(langbotProvider.uuid)) {
        setExpandedProviders(new Set([langbotProvider.uuid]));
        if (!providerModels[langbotProvider.uuid]) {
          loadProviderModels(langbotProvider.uuid);
        }
      }
    }
  }, [providersLoaded, providers]);

  async function loadUserInfo() {
    try {
      const userInfo = await httpClient.getUserInfo();
      setAccountType(userInfo.account_type);
      if (userInfo.account_type === 'space') {
        const creditsInfo = await httpClient.getSpaceCredits();
        setSpaceCredits(creditsInfo.credits);
      }
    } catch {
      setAccountType('local');
    }
  }

  async function loadProviders() {
    try {
      const resp = await httpClient.getModelProviders();
      setProviders(resp.providers);
      setProvidersLoaded(true);
    } catch (err) {
      console.error('Failed to load providers', err);
      toast.error(t('models.loadError'));
    }
  }

  async function loadProviderModels(providerUuid: string, silent = false) {
    if (loadingProviders.has(providerUuid)) return;

    if (!silent) {
      setLoadingProviders((prev) => new Set(prev).add(providerUuid));
    }
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
      if (!silent) {
        setLoadingProviders((prev) => {
          const next = new Set(prev);
          next.delete(providerUuid);
          return next;
        });
      }
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

  function handleCreateProvider() {
    setEditingProviderId(null);
    setProviderFormOpen(true);
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

  async function handleSpaceLogin() {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        toast.error(t('common.error'));
        return;
      }
      const currentOrigin = window.location.origin;
      const redirectUri = `${currentOrigin}/auth/space/callback?mode=bind`;
      const response = await httpClient.getSpaceAuthorizeUrl(
        redirectUri,
        token,
      );
      window.location.href = response.authorize_url;
    } catch {
      toast.error(t('common.spaceLoginFailed'));
    }
  }

  async function handleAddModel(
    providerUuid: string,
    modelType: ModelType,
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) {
    if (!name.trim()) {
      toast.error(t('models.modelNameRequired'));
      return;
    }
    setIsSubmitting(true);
    try {
      const extraArgsObj = convertExtraArgsToObject(extraArgs);

      if (modelType === 'llm') {
        await httpClient.createProviderLLMModel({
          name,
          provider_uuid: providerUuid,
          abilities,
          extra_args: extraArgsObj,
        } as never);
      } else {
        await httpClient.createProviderEmbeddingModel({
          name,
          provider_uuid: providerUuid,
          extra_args: extraArgsObj,
        } as never);
      }
      setAddModelPopoverOpen(null);
      loadProviderModels(providerUuid, true);
      loadProviders();
    } catch (err) {
      toast.error(t('models.createError') + (err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleUpdateModel(
    providerUuid: string,
    modelId: string,
    modelType: ModelType,
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) {
    if (!name.trim()) {
      toast.error(t('models.modelNameRequired'));
      return;
    }
    setIsSubmitting(true);
    try {
      const extraArgsObj = convertExtraArgsToObject(extraArgs);

      if (modelType === 'llm') {
        await httpClient.updateProviderLLMModel(modelId, {
          name,
          provider_uuid: providerUuid,
          abilities,
          extra_args: extraArgsObj,
        } as never);
      } else {
        await httpClient.updateProviderEmbeddingModel(modelId, {
          name,
          provider_uuid: providerUuid,
          extra_args: extraArgsObj,
        } as never);
      }
      setEditModelPopoverOpen(null);
      loadProviderModels(providerUuid, true);
      loadProviders();
    } catch (err) {
      toast.error(t('models.saveError') + (err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteModel(
    providerUuid: string,
    modelId: string,
    modelType: ModelType,
  ) {
    try {
      if (modelType === 'llm') {
        await httpClient.deleteProviderLLMModel(modelId);
      } else {
        await httpClient.deleteProviderEmbeddingModel(modelId);
      }
      toast.success(t('models.deleteSuccess'));
      loadProviderModels(providerUuid, true);
      loadProviders();
    } catch (err) {
      toast.error(t('models.deleteError') + (err as Error).message);
    }
  }

  async function handleTestModel(
    providerUuid: string,
    name: string,
    modelType: ModelType,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) {
    setIsTesting(true);
    setTestResult(null);
    const startTime = Date.now();
    try {
      const extraArgsObj = convertExtraArgsToObject(extraArgs);

      // Get the provider info
      const provider = providers.find((p) => p.uuid === providerUuid);
      const providerData = {
        requester: provider?.requester || '',
        base_url: provider?.base_url || '',
        api_keys: provider?.api_keys || [],
      };

      if (modelType === 'llm') {
        await httpClient.testLLMModel('_', {
          uuid: '',
          name,
          provider_uuid: '',
          provider: providerData,
          abilities,
          extra_args: extraArgsObj,
        } as never);
      } else {
        await httpClient.testEmbeddingModel('_', {
          uuid: '',
          name,
          provider_uuid: '',
          provider: providerData,
          extra_args: extraArgsObj,
        } as never);
      }
      const duration = Date.now() - startTime;
      setTestResult({ success: true, duration });
    } catch (err) {
      console.error('Failed to test model', err);
      toast.error(t('models.testError') + ': ' + (err as CustomApiError).msg);
      setTestResult(null);
    } finally {
      setIsTesting(false);
    }
  }

  function handleFormClose() {
    setProviderFormOpen(false);
    loadProviders();
    // Refresh expanded providers
    expandedProviders.forEach((uuid) => loadProviderModels(uuid));
  }

  function renderProviderCard(
    provider: ModelProvider,
    isLangBotModels: boolean = false,
  ) {
    return (
      <ProviderCard
        key={provider.uuid}
        provider={provider}
        isLangBotModels={isLangBotModels}
        isExpanded={expandedProviders.has(provider.uuid)}
        isLoading={loadingProviders.has(provider.uuid)}
        models={providerModels[provider.uuid]}
        accountType={accountType}
        spaceCredits={spaceCredits}
        addModelPopoverOpen={addModelPopoverOpen}
        editModelPopoverOpen={editModelPopoverOpen}
        deleteConfirmOpen={deleteConfirmOpen}
        onToggle={() => toggleProvider(provider.uuid)}
        onEditProvider={() => handleEditProvider(provider.uuid)}
        onDeleteProvider={() => handleDeleteProvider(provider.uuid)}
        onSpaceLogin={handleSpaceLogin}
        onOpenAddModel={() => setAddModelPopoverOpen(provider.uuid)}
        onCloseAddModel={() => setAddModelPopoverOpen(null)}
        onAddModel={(modelType, name, abilities, extraArgs) =>
          handleAddModel(provider.uuid, modelType, name, abilities, extraArgs)
        }
        onOpenEditModel={(modelId) => setEditModelPopoverOpen(modelId)}
        onCloseEditModel={() => setEditModelPopoverOpen(null)}
        onUpdateModel={(modelId, modelType, name, abilities, extraArgs) =>
          handleUpdateModel(
            provider.uuid,
            modelId,
            modelType,
            name,
            abilities,
            extraArgs,
          )
        }
        onOpenDeleteConfirm={(modelId) => setDeleteConfirmOpen(modelId)}
        onCloseDeleteConfirm={() => setDeleteConfirmOpen(null)}
        onDeleteModel={(modelId, modelType) =>
          handleDeleteModel(provider.uuid, modelId, modelType)
        }
        onTestModel={(name, modelType, abilities, extraArgs) =>
          handleTestModel(provider.uuid, name, modelType, abilities, extraArgs)
        }
        isSubmitting={isSubmitting}
        isTesting={isTesting}
        testResult={testResult}
        onResetTestResult={() => setTestResult(null)}
      />
    );
  }

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(newOpen) => {
          if (!newOpen && providerFormOpen) return;
          onOpenChange(newOpen);
        }}
      >
        <DialogContent className="overflow-hidden p-0 h-[80vh] flex flex-col !max-w-[37rem]">
          <DialogHeader className="px-6 pt-6 pb-0 flex-shrink-0">
            <DialogTitle>{t('models.title')}</DialogTitle>
          </DialogHeader>

          <div className="flex-1 overflow-auto px-6 pb-6 mt-0">
            {/* LangBot Models Card */}
            {langbotProvider && renderProviderCard(langbotProvider, true)}

            {/* Add Provider Button */}
            <div className="mb-3 flex justify-between items-center sticky top-0 bg-background py-2 z-10">
              <span className="text-sm text-muted-foreground">
                {otherProviders.length === 0
                  ? t(
                      systemInfo.disable_models_service
                        ? 'models.addProviderHintSimple'
                        : 'models.addProviderHint',
                    )
                  : t('models.providerCount', { count: otherProviders.length })}
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={handleCreateProvider}
              >
                <Plus className="h-4 w-4 mr-1" />
                {t('models.addProvider')}
              </Button>
            </div>

            {/* Provider List */}
            {otherProviders.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Boxes className="h-12 w-12 mb-3 opacity-50" />
                <p className="text-sm">{t('models.noProviders')}</p>
              </div>
            ) : (
              otherProviders.map((p) => renderProviderCard(p))
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={providerFormOpen} onOpenChange={setProviderFormOpen}>
        <DialogContent className="w-[600px] p-6">
          <DialogHeader>
            <DialogTitle>
              {editingProviderId
                ? t('models.editProvider')
                : t('models.addProvider')}
            </DialogTitle>
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
