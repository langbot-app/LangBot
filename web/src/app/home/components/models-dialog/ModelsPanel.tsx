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
  ScanModelsResult,
  SelectedScannedModel,
  TestResult,
  ProviderModels,
  LANGBOT_MODELS_PROVIDER_REQUESTER,
} from './types';
import { CustomApiError } from '@/app/infra/entities/common';
import { PanelBody } from '../settings-dialog/panel-layout';

interface ModelsPanelProps {
  // True when this panel is the active section and the dialog is open.
  active: boolean;
  // Notify parent when a nested modal (provider form) should block outer-close.
  onBlockingChange?: (blocking: boolean) => void;
}

type ExtraArgValue = string | number | boolean | Record<string, unknown>;

function convertExtraArgsToObject(
  args: ExtraArg[],
): Record<string, ExtraArgValue> {
  const obj: Record<string, ExtraArgValue> = {};
  args.forEach((arg) => {
    if (!arg.key.trim()) return;
    if (arg.type === 'number') {
      obj[arg.key] = Number(arg.value);
    } else if (arg.type === 'boolean') {
      obj[arg.key] = arg.value === 'true';
    } else if (arg.type === 'object') {
      const raw = arg.value.trim() || '{}';
      let parsed: unknown;
      try {
        parsed = JSON.parse(raw);
      } catch {
        throw new Error(`Invalid JSON for extra parameter "${arg.key}"`);
      }
      if (
        parsed === null ||
        typeof parsed !== 'object' ||
        Array.isArray(parsed)
      ) {
        throw new Error(`Extra parameter "${arg.key}" must be a JSON object`);
      }
      obj[arg.key] = parsed as Record<string, unknown>;
    } else {
      obj[arg.key] = arg.value;
    }
  });
  return obj;
}

function parseContextLength(
  value: number | null | undefined,
  invalidMessage: string,
): number | null {
  if (value === undefined || value === null) return null;
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error(invalidMessage);
  }
  return value;
}

export default function ModelsPanel({
  active,
  onBlockingChange,
}: ModelsPanelProps) {
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

  // Map of requester name -> support_type[] (from requester manifests),
  // used to restrict which model-type tabs are shown when adding models.
  const [requesterSupportTypes, setRequesterSupportTypes] = useState<
    Record<string, string[]>
  >({});

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
    if (active) {
      loadUserInfo();
      loadProviders();
      loadRequesterSupportTypes();
    }
  }, [active]);

  // Notify parent of blocking state so it can guard outer-close.
  useEffect(() => {
    onBlockingChange?.(providerFormOpen);
  }, [providerFormOpen, onBlockingChange]);

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

  async function loadRequesterSupportTypes() {
    try {
      const resp = await httpClient.getProviderRequesters();
      const map: Record<string, string[]> = {};
      for (const r of resp.requesters) {
        map[r.name] = r.spec?.support_type ?? [];
      }
      setRequesterSupportTypes(map);
    } catch (err) {
      console.error('Failed to load requester support types', err);
    }
  }

  async function loadProviderModels(providerUuid: string, silent = false) {
    if (loadingProviders.has(providerUuid)) return;

    if (!silent) {
      setLoadingProviders((prev) => new Set(prev).add(providerUuid));
    }
    try {
      const [llmResp, embeddingResp, rerankResp] = await Promise.all([
        httpClient.getProviderLLMModels(providerUuid),
        httpClient.getProviderEmbeddingModels(providerUuid),
        httpClient.getProviderRerankModels(providerUuid),
      ]);
      setProviderModels((prev) => ({
        ...prev,
        [providerUuid]: {
          llm: llmResp.models,
          embedding: embeddingResp.models,
          rerank: rerankResp.models,
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
    contextLength?: number | null,
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
          context_length: parseContextLength(
            contextLength,
            t('models.contextLengthInvalid'),
          ),
          extra_args: extraArgsObj,
        } as never);
      } else if (modelType === 'embedding') {
        await httpClient.createProviderEmbeddingModel({
          name,
          provider_uuid: providerUuid,
          extra_args: extraArgsObj,
        } as never);
      } else {
        await httpClient.createProviderRerankModel({
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

  async function handleScanModels(
    providerUuid: string,
    modelType?: ModelType,
  ): Promise<ScanModelsResult> {
    try {
      const resp = await httpClient.scanProviderModels(providerUuid, modelType);
      return {
        models: resp.models,
        debug: resp.debug,
      };
    } catch (err) {
      toast.error(t('models.getModelListError') + (err as CustomApiError).msg);
      return { models: [] };
    }
  }

  async function handleAddScannedModels(
    providerUuid: string,
    modelType: ModelType,
    models: SelectedScannedModel[],
  ) {
    if (models.length === 0) return;

    setIsSubmitting(true);
    try {
      for (const item of models) {
        const effectiveType = item.model.type || modelType;
        if (effectiveType === 'llm') {
          await httpClient.createProviderLLMModel({
            name: item.model.name,
            provider_uuid: providerUuid,
            abilities: item.abilities,
            context_length: item.model.context_length ?? null,
            extra_args: {},
          } as never);
        } else if (effectiveType === 'embedding') {
          await httpClient.createProviderEmbeddingModel({
            name: item.model.name,
            provider_uuid: providerUuid,
            extra_args: {},
          } as never);
        } else {
          await httpClient.createProviderRerankModel({
            name: item.model.name,
            provider_uuid: providerUuid,
            extra_args: {},
          } as never);
        }
      }
      setAddModelPopoverOpen(null);
      loadProviderModels(providerUuid, true);
      loadProviders();
      toast.success(
        t('models.addSelectedModelsSuccess', { count: models.length }),
      );
    } catch (err) {
      toast.error(t('models.createError') + (err as CustomApiError).msg);
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
    contextLength?: number | null,
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
          context_length: parseContextLength(
            contextLength,
            t('models.contextLengthInvalid'),
          ),
          extra_args: extraArgsObj,
        } as never);
      } else if (modelType === 'embedding') {
        await httpClient.updateProviderEmbeddingModel(modelId, {
          name,
          provider_uuid: providerUuid,
          extra_args: extraArgsObj,
        } as never);
      } else {
        await httpClient.updateProviderRerankModel(modelId, {
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
      } else if (modelType === 'embedding') {
        await httpClient.deleteProviderEmbeddingModel(modelId);
      } else {
        await httpClient.deleteProviderRerankModel(modelId);
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
      } else if (modelType === 'embedding') {
        await httpClient.testEmbeddingModel('_', {
          uuid: '',
          name,
          provider_uuid: '',
          provider: providerData,
          extra_args: extraArgsObj,
        } as never);
      } else {
        await httpClient.testRerankModel('_', {
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
        supportTypes={requesterSupportTypes[provider.requester]}
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
        onAddModel={(modelType, name, abilities, extraArgs, contextLength) =>
          handleAddModel(
            provider.uuid,
            modelType,
            name,
            abilities,
            extraArgs,
            contextLength,
          )
        }
        onScanModels={(modelType) => handleScanModels(provider.uuid, modelType)}
        onAddScannedModels={(modelType, models) =>
          handleAddScannedModels(provider.uuid, modelType, models)
        }
        onOpenEditModel={(modelId) => setEditModelPopoverOpen(modelId)}
        onCloseEditModel={() => setEditModelPopoverOpen(null)}
        onUpdateModel={(
          modelId,
          modelType,
          name,
          abilities,
          extraArgs,
          contextLength,
        ) =>
          handleUpdateModel(
            provider.uuid,
            modelId,
            modelType,
            name,
            abilities,
            extraArgs,
            contextLength,
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
      <PanelBody>
        {/* LangBot Models (Space) provider card is intentionally pinned to the
            top, above the "add custom provider" action row. */}
        {langbotProvider && renderProviderCard(langbotProvider, true)}

        {/* Add-provider row: stays below the pinned card by design. */}
        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="text-sm text-muted-foreground">
            {otherProviders.length === 0
              ? t(
                  systemInfo.disable_models_service
                    ? 'models.addProviderHintSimple'
                    : 'models.addProviderHint',
                )
              : t('models.providerCount', { count: otherProviders.length })}
          </span>
          <Button size="sm" variant="outline" onClick={handleCreateProvider}>
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
      </PanelBody>

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
