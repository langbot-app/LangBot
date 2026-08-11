import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { UUID } from 'uuidjs';
import { toast } from 'sonner';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Sparkles,
  PartyPopper,
  Loader2,
  X,
  ExternalLink,
  Rocket,
  Wrench,
} from 'lucide-react';

import { httpClient } from '@/app/infra/http/HttpClient';
import {
  userInfo,
  systemInfo,
  bootstrapWorkspaceSession,
  initializeSystemInfo,
} from '@/app/infra/http';
import {
  Adapter,
  Bot,
  Pipeline,
  WizardProgress,
} from '@/app/infra/entities/api';
import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import {
  PipelineConfigTab,
  PipelineConfigStage,
} from '@/app/infra/entities/pipeline';
import {
  DynamicFormItemConfig,
  getDefaultValues,
  parseDynamicFormItemType,
} from '@/app/home/components/dynamic-form/DynamicFormItemConfig';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import ProviderForm from '@/app/home/components/models-dialog/component/provider-form/ProviderForm';
import { BotLogListComponent } from '@/app/home/bots/components/bot-log/view/BotLogListComponent';
import { extractI18nObject } from '@/i18n/I18nProvider';
import {
  groupByCategory,
  getCategoryLabel,
} from '@/app/infra/entities/adapter-categories';
import { getAdapterDocUrl } from '@/app/infra/entities/adapter-docs';
import i18n from 'i18next';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { cn } from '@/lib/utils';
import { LanguageSelector } from '@/components/ui/language-selector';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';


// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

const TOTAL_STEPS = 4;

// ---------------------------------------------------------------------------
// Main Wizard Page (full-screen, no sidebar)
// ---------------------------------------------------------------------------

export default function WizardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  // ---- Wizard state ----
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedAdapter, setSelectedAdapter] = useState<string | null>(null);
  const [selectedRunner, setSelectedRunner] = useState<string | null>(null);
  const [botName, setBotName] = useState('');

  const [botDescription, _setBotDescription] = useState('');
  const [adapterConfig, setAdapterConfig] = useState<Record<string, unknown>>(
    {},
  );
  const [runnerConfig, setRunnerConfig] = useState<Record<string, unknown>>({});
  const [aiEngineMode, setAiEngineMode] = useState<
    'orchestrated' | 'llm' | null
  >(null);
  const [modelSource, setModelSource] = useState<'space' | 'custom' | null>(
    null,
  );
  const [providerCreated, setProviderCreated] = useState(false);
  const [createdProviderUuid, setCreatedProviderUuid] = useState<string | null>(
    null,
  );
  const [modelsAdded, setModelsAdded] = useState(false);
  // Sub-layer within Step 2: 0=main, 1=sub-choice, 2=provider, 3=scan, 4=config
  const [step2Layer, setStep2Layer] = useState(0);
  const [maxReachedLayer, setMaxReachedLayer] = useState(0);

  const goToStep2Layer = useCallback(
    (layer: number) => {
      setStep2Layer(layer);
      setMaxReachedLayer((prev) => Math.max(prev, layer));
    },
    [],
  );

  // Saved provider form data for back navigation
  const [savedProviderForm, setSavedProviderForm] = useState<{
    name?: string;
    requester?: string;
    base_url?: string;
    api_key?: string;
  }>({});
  // Saved selected scanned models for back navigation
  const [savedSelectedModels, setSavedSelectedModels] = useState<Set<string>>(
    new Set(),
  );
  const [createdBotUuid, setCreatedBotUuid] = useState<string | null>(null);
  const [webhookUrl, setWebhookUrl] = useState<string>('');
  const [extraWebhookUrl, setExtraWebhookUrl] = useState<string>('');

  // ---- Remote data ----
  const [adapters, setAdapters] = useState<Adapter[]>([]);
  const [aiConfigTab, setAiConfigTab] = useState<PipelineConfigTab | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isCreatingBot, setIsCreatingBot] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSavingBot, setIsSavingBot] = useState(false);
  const [botSaved, setBotSaved] = useState(false);

  // ---- Helper: persist wizard progress to backend (fire-and-forget) ----
  const saveProgress = useCallback(
    (overrides: Partial<WizardProgress> = {}) => {
      const progress: WizardProgress = {
        step: overrides.step ?? currentStep,
        selected_adapter: overrides.selected_adapter ?? selectedAdapter,
        created_bot_uuid: overrides.created_bot_uuid ?? createdBotUuid,
        bot_saved: overrides.bot_saved ?? botSaved,
        selected_runner: overrides.selected_runner ?? selectedRunner,
      };
      httpClient.saveWizardProgress(progress).catch((err) => {
        console.error('Failed to save wizard progress', err);
      });
    },
    [currentStep, selectedAdapter, createdBotUuid, botSaved, selectedRunner],
  );

  // ---- Fetch remote data & restore progress ----
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Resolve the Account's Workspace before loading scoped wizard data.
        const workspaceResult = await bootstrapWorkspaceSession();
        if (workspaceResult.status === 'selection-required') {
          navigate('/workspaces/select?returnTo=%2Fwizard', { replace: true });
          return;
        }
        if (workspaceResult.status === 'unavailable') {
          throw new Error('No Workspace is available for this Account');
        }
        await initializeSystemInfo({ throwOnError: true });

        const [adaptersResp, metadataResp] = await Promise.all([
          httpClient.getAdapters(),
          httpClient.getGeneralPipelineMetadata(),
        ]);
        if (cancelled) return;
        setAdapters(adaptersResp.adapters);
        const aiTab = metadataResp.configs.find((c) => c.name === 'ai');
        if (aiTab) setAiConfigTab(aiTab);

        // Restore wizard progress if available
        const progress = systemInfo.wizard_progress;
        if (progress && progress.created_bot_uuid) {
          // Verify the bot still exists before restoring
          try {
            const botData = await httpClient.getBot(progress.created_bot_uuid);
            if (cancelled) return;

            setSelectedAdapter(progress.selected_adapter);
            setCreatedBotUuid(progress.created_bot_uuid);
            setBotSaved(progress.bot_saved ?? false);
            setSelectedRunner(progress.selected_runner);

            // Restore bot name from fetched bot data
            setBotName(botData.bot.name);

            // Restore webhook URLs
            const runtimeValues = botData.bot.adapter_runtime_values as
              | Record<string, unknown>
              | undefined;
            setWebhookUrl((runtimeValues?.webhook_full_url as string) || '');
            setExtraWebhookUrl(
              (runtimeValues?.extra_webhook_full_url as string) || '',
            );

            // Restore step (cap at step 2 — step 3 means done)
            setCurrentStep(Math.min(progress.step, 2));
          } catch {
            // Bot no longer exists — clear stale progress and start fresh
            httpClient
              .saveWizardProgress({
                step: 0,
                selected_adapter: null,
                created_bot_uuid: null,
                bot_saved: false,
                selected_runner: null,
              })
              .catch(() => {});
          }
        }
      } catch (err) {
        console.error('Failed to load wizard data', err);
        toast.error(t('wizard.loadError'));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [navigate, t]);

  // ---- Derived data ----

  const runnerStage: PipelineConfigStage | undefined = useMemo(
    () => aiConfigTab?.stages.find((s) => s.name === 'runner'),
    [aiConfigTab],
  );

  const runnerOptions = useMemo(() => {
    if (!runnerStage) return [];
    const runnerField = runnerStage.config.find((c) => c.name === 'runner');
    return runnerField?.options ?? [];
  }, [runnerStage]);

  const selectedRunnerConfigStage: PipelineConfigStage | undefined =
    useMemo(() => {
      if (!selectedRunner || !aiConfigTab) return undefined;
      return aiConfigTab.stages.find((s) => s.name === selectedRunner);
    }, [selectedRunner, aiConfigTab]);

  // Adapter spec config for the selected adapter
  const selectedAdapterConfig: IDynamicFormItemSchema[] = useMemo(() => {
    const adapter = adapters.find((a) => a.name === selectedAdapter);
    if (!adapter) return [];
    return adapter.spec.config.map(
      (item) =>
        new DynamicFormItemConfig({
          default: item.default,
          id: UUID.generate(),
          label: item.label,
          description: item.description,
          name: item.name,
          required: item.required,
          type: parseDynamicFormItemType(item.type),
          options: item.options,
          show_if: item.show_if,
          login_platform: item.login_platform,
          url: item.url,
          download_filename: item.download_filename,
          help_links: item.help_links,
          help_label: item.help_label,
        }),
    );
  }, [adapters, selectedAdapter]);

  // Runner config items
  const selectedRunnerConfigItems: IDynamicFormItemSchema[] = useMemo(() => {
    if (!selectedRunnerConfigStage) return [];
    return selectedRunnerConfigStage.config.map(
      (item) =>
        new DynamicFormItemConfig({
          default: item.default,
          id: UUID.generate(),
          label: item.label,
          description: item.description,
          name: item.name,
          required: item.required,
          type: parseDynamicFormItemType(item.type),
          options: item.options,
          show_if: item.show_if,
          login_platform: item.login_platform,
          url: item.url,
          download_filename: item.download_filename,
          help_links: item.help_links,
          help_label: item.help_label,
        }),
    );
  }, [selectedRunnerConfigStage]);

  // ---- Runner selection with progress saving ----
  const handleSelectRunner = useCallback(
    (runner: string) => {
      setSelectedRunner(runner);
      goToStep2Layer(4);
      saveProgress({ step: 2, selected_runner: runner });
    },
    [saveProgress],
  );

  const handleAiEngineModeSelect = useCallback(
    (mode: 'orchestrated' | 'llm') => {
      setAiEngineMode(mode);
      setSelectedRunner(null);
      setModelSource(null);
      setProviderCreated(false);
      setCreatedProviderUuid(null);
      setModelsAdded(false);
      setSavedProviderForm({});
      setSavedSelectedModels(new Set());
      setMaxReachedLayer(0);
      goToStep2Layer(1);
    },
    [goToStep2Layer],
  );

  // ---- Navigation helpers ----

  const canProceed = useCallback((): boolean => {
    switch (currentStep) {
      case 0:
        return selectedAdapter !== null;
      case 1:
        return createdBotUuid !== null && botSaved;
      case 2:
        if (aiEngineMode === 'orchestrated') {
          return selectedRunner !== null;
        }
        if (aiEngineMode === 'llm') {
          return (
            modelSource === 'space' ||
            (modelSource === 'custom' && modelsAdded)
          );
        }
        return false;
      default:
        return false;
    }
  }, [
    currentStep,
    selectedAdapter,
    createdBotUuid,
    botSaved,
    aiEngineMode,
    selectedRunner,
    modelSource,
    modelsAdded,
  ]);

  const goNext = useCallback(() => {
    if (currentStep === 2 && step2Layer < maxReachedLayer) {
      setStep2Layer(maxReachedLayer);
      return;
    }
    if (currentStep < TOTAL_STEPS - 1 && canProceed()) {
      const nextStep = currentStep + 1;
      setCurrentStep(nextStep);
      saveProgress({ step: nextStep });
    }
  }, [currentStep, step2Layer, maxReachedLayer, canProceed, saveProgress]);

  const goPrev = useCallback(() => {
    if (currentStep === 2 && step2Layer > 0) {
      setStep2Layer(step2Layer - 1);
      return;
    }
    if (currentStep > 0) {
      const prevStep = currentStep - 1;
      setCurrentStep(prevStep);
      saveProgress({ step: prevStep });
    }
  }, [currentStep, step2Layer, saveProgress]);

  // ---- Create Bot (Step 0) ----
  // Creates a disabled bot using the adapter label as name.

  const handleCreateBot = useCallback(async () => {
    if (!selectedAdapter) return;
    setIsCreatingBot(true);

    try {
      // Use adapter label as default bot name
      const adapter = adapters.find((a) => a.name === selectedAdapter);
      const defaultName = adapter
        ? extractI18nObject(adapter.label)
        : selectedAdapter;
      setBotName(defaultName);

      const defaultConfig = adapter
        ? getDefaultValues(adapter.spec.config)
        : {};

      const bot: Bot = {
        name: defaultName,
        description: '',
        adapter: selectedAdapter,
        adapter_config: defaultConfig,
        enable: false,
      };
      const resp = await httpClient.createBot(bot);
      setCreatedBotUuid(resp.uuid);

      // Fetch runtime info to get webhook URL(s)
      try {
        const botData = await httpClient.getBot(resp.uuid);
        const runtimeValues = botData.bot.adapter_runtime_values as
          | Record<string, unknown>
          | undefined;
        setWebhookUrl((runtimeValues?.webhook_full_url as string) || '');
        setExtraWebhookUrl(
          (runtimeValues?.extra_webhook_full_url as string) || '',
        );
      } catch {
        // Non-critical — webhook URL display is optional
      }

      // Advance to Step 1
      setCurrentStep(1);

      // Persist progress
      saveProgress({
        step: 1,
        selected_adapter: selectedAdapter,
        created_bot_uuid: resp.uuid,
        bot_saved: false,
        selected_runner: null,
      });
    } catch (err) {
      const apiErr = err as { msg?: string };
      toast.error(
        t('wizard.createError') + (apiErr?.msg ? `: ${apiErr.msg}` : ''),
      );
    } finally {
      setIsCreatingBot(false);
    }
  }, [selectedAdapter, adapters, t, saveProgress]);

  // ---- Save Bot Config & Enable (Step 1) ----
  // Updates the bot's adapter config and enables it.

  const handleSaveBot = useCallback(async () => {
    if (!createdBotUuid || !selectedAdapter) return;
    setIsSavingBot(true);

    try {
      await httpClient.updateBot(createdBotUuid, {
        name: botName,
        description: botDescription || '',
        adapter: selectedAdapter,
        adapter_config: adapterConfig,
        enable: true,
      });
      setBotSaved(true);

      // Re-fetch runtime info to get updated webhook URL(s)
      try {
        const botData = await httpClient.getBot(createdBotUuid);
        const runtimeValues = botData.bot.adapter_runtime_values as
          | Record<string, unknown>
          | undefined;
        setWebhookUrl((runtimeValues?.webhook_full_url as string) || '');
        setExtraWebhookUrl(
          (runtimeValues?.extra_webhook_full_url as string) || '',
        );
      } catch {
        // Non-critical
      }

      // Persist progress
      saveProgress({ step: 1, bot_saved: true });
    } catch (err) {
      const apiErr = err as { msg?: string };
      toast.error(
        t('wizard.createError') + (apiErr?.msg ? `: ${apiErr.msg}` : ''),
      );
    } finally {
      setIsSavingBot(false);
    }
  }, [
    createdBotUuid,
    selectedAdapter,
    botName,
    botDescription,
    adapterConfig,
    t,
    saveProgress,
  ]);

  // ---- Create Pipeline & Link (Step 2 finish) ----

  const handleFinish = useCallback(async () => {
    if (!selectedRunner || !createdBotUuid) return;
    setIsSubmitting(true);

    try {
      // 1. Create pipeline (backend fills config from default template)
      const pipeline: Pipeline = {
        name: `${botName} Pipeline`,
        description: botDescription || '',
        config: {},
      };
      const pipelineResp = await httpClient.createPipeline(pipeline);

      // 2. Fetch the created pipeline to get the full default config
      //    (includes trigger, safety, ai, output sections).
      //    Then merge only the AI section with the wizard's runner config.
      const createdPipeline = await httpClient.getPipeline(pipelineResp.uuid);
      const fullConfig = createdPipeline.pipeline.config;

      const mergedConfig = {
        ...fullConfig,
        ai: {
          ...fullConfig.ai,
          runner: { runner: selectedRunner },
          [selectedRunner]: runnerConfig,
        },
      };

      await httpClient.updatePipeline(pipelineResp.uuid, {
        name: `${botName} Pipeline`,
        description: botDescription || '',
        config: mergedConfig,
      });

      // 3. Link pipeline to the bot created in Step 1
      const botData = await httpClient.getBot(createdBotUuid);
      const existingBot = botData.bot;
      await httpClient.updateBot(createdBotUuid, {
        name: existingBot.name,
        description: existingBot.description,
        adapter: existingBot.adapter,
        adapter_config: existingBot.adapter_config,
        enable: existingBot.enable,
        use_pipeline_uuid: pipelineResp.uuid,
      });

      setCurrentStep(3);
    } catch (err) {
      const apiErr = err as { msg?: string };
      toast.error(
        t('wizard.createError') + (apiErr?.msg ? `: ${apiErr.msg}` : ''),
      );
    } finally {
      setIsSubmitting(false);
    }
  }, [
    selectedRunner,
    createdBotUuid,
    botName,
    botDescription,
    runnerConfig,
    t,
  ]);

  // ---- Space auth redirect ----

  const handleSpaceAuth = useCallback(async () => {
    try {
      const callbackUrl = `${window.location.origin}/auth/space/callback`;
      const resp = await httpClient.getSpaceAuthorizeUrl(callbackUrl);
      window.location.href = resp.authorize_url;
    } catch (err) {
      console.error('Failed to get space authorize URL', err);
      toast.error(t('wizard.spaceAuthError'));
    }
  }, [t]);

  const handleModelSourceSelect = useCallback(
    (source: 'space' | 'custom') => {
      setModelSource(source);
      if (source === 'space') {
        handleSpaceAuth();
      } else if (providerCreated && modelsAdded) {
        goToStep2Layer(4);
      } else if (providerCreated) {
        goToStep2Layer(3);
      } else {
        goToStep2Layer(2);
      }
    },
    [handleSpaceAuth, providerCreated, modelsAdded],
  );

  // ---- Check if local account ----
  // Re-evaluated after remote data fetch (when userInfo is populated)
  const isLocalAccount =
    !isLoading && (!userInfo || userInfo.account_type === 'local');

  // ---- Skip handler ----
  const [showSkipConfirm, setShowSkipConfirm] = useState(false);
  const [isSkipping, setIsSkipping] = useState(false);

  const handleSkipConfirm = useCallback(async () => {
    setIsSkipping(true);
    try {
      if (systemInfo.wizard_status === 'none') {
        await httpClient.updateWizardStatus('skipped');
        systemInfo.wizard_status = 'skipped';
      }
      // Always clear persisted progress so re-entering starts fresh
      await httpClient.saveWizardProgress({
        step: 0,
        selected_adapter: null,
        created_bot_uuid: null,
        bot_saved: false,
        selected_runner: null,
      });
      systemInfo.wizard_progress = null;
    } catch {
      toast.error(t('wizard.skipSaveError'));
      setIsSkipping(false);
      return;
    }
    setIsSkipping(false);
    setShowSkipConfirm(false);
    navigate('/home');
  }, [navigate, t]);

  // ---- Render ----

  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 bg-background flex items-center justify-center">
        <LoadingSpinner text={t('wizard.loading')} />
      </div>
    );
  }

  const stepLabels = [
    t('wizard.step.platform'),
    t('wizard.step.botConfig'),
    t('wizard.step.aiEngine'),
    t('wizard.step.done'),
  ];

  return (
    <div className="fixed inset-0 z-50 bg-background flex flex-col">
      {/* Top bar: Skip button */}
      <div className="shrink-0 flex items-center justify-between px-4 sm:px-6 py-3 border-b">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-primary" />
          <span className="font-semibold text-base sm:text-lg">
            {t('sidebar.quickStart')}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <LanguageSelector />
          {currentStep < 3 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowSkipConfirm(true)}
            >
              {t('wizard.skip')}
              <X className="w-4 h-4 ml-1" />
            </Button>
          )}
        </div>
      </div>

      {/* Stepper header */}
      <div className="shrink-0 py-3 sm:py-4 px-4 sm:px-6">
        <div className="flex items-center justify-center gap-1.5 sm:gap-2">
          {stepLabels.map((label, idx) => (
            <div key={label} className="flex items-center gap-1.5 sm:gap-2">
              <div className="flex items-center gap-1 sm:gap-1.5">
                <div
                  className={cn(
                    'w-6 h-6 sm:w-7 sm:h-7 rounded-full flex items-center justify-center text-xs font-medium transition-colors',
                    idx < currentStep
                      ? 'bg-blue-600 text-white'
                      : idx === currentStep
                        ? 'bg-blue-600 text-white'
                        : 'bg-muted text-muted-foreground',
                  )}
                >
                  {idx < currentStep ? (
                    <Check className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                  ) : (
                    idx + 1
                  )}
                </div>
                <span
                  className={cn(
                    'text-sm hidden sm:inline',
                    idx === currentStep
                      ? 'font-medium text-blue-600'
                      : 'text-muted-foreground',
                  )}
                >
                  {label}
                </span>
              </div>
              {idx < TOTAL_STEPS - 1 && (
                <div
                  className={cn(
                    'w-4 sm:w-8 h-px',
                    idx < currentStep ? 'bg-blue-600' : 'bg-border',
                  )}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Step content */}
      <div
        className={cn(
          'flex-1 min-h-0 px-4 sm:px-6 pb-4 sm:pb-6',
          currentStep === 2 && selectedRunner
            ? 'lg:flex lg:flex-col lg:overflow-hidden overflow-y-auto'
            : 'overflow-y-auto',
        )}
      >
        {currentStep === 0 && (
          <StepPlatform
            adapters={adapters}
            selected={selectedAdapter}
            onSelect={setSelectedAdapter}
          />
        )}
        {currentStep === 1 && (
          <StepBotConfig
            adapterConfigItems={selectedAdapterConfig}
            adapterConfigValues={adapterConfig}
            onAdapterConfigChange={setAdapterConfig}
            selectedAdapterName={selectedAdapter}
            adapters={adapters}
            createdBotUuid={createdBotUuid}
            isSavingBot={isSavingBot}
            botSaved={botSaved}
            onSaveBot={handleSaveBot}
            webhookUrl={webhookUrl}
            extraWebhookUrl={extraWebhookUrl}
          />
        )}
        {currentStep === 2 && (
          <StepAIEngine
            runnerOptions={runnerOptions}
            step2Layer={step2Layer}
            aiEngineMode={aiEngineMode}
            onAiEngineModeSelect={handleAiEngineModeSelect}
            selectedRunner={selectedRunner}
            onSelectRunner={handleSelectRunner}
            isLocalAccount={isLocalAccount}
            onSpaceAuth={handleSpaceAuth}
            modelSource={modelSource}
            onModelSourceSelect={handleModelSourceSelect}
            providerCreated={providerCreated}
            createdProviderUuid={createdProviderUuid}
            modelsAdded={modelsAdded}
            onProviderCreated={(uuid) => {
              setProviderCreated(true);
              setCreatedProviderUuid(uuid ?? null);
              goToStep2Layer(3);
            }}
            onModelsAdded={() => {
              setModelsAdded(true);
              setSelectedRunner('local-agent');
              goToStep2Layer(4);
              saveProgress({ step: 2, selected_runner: 'local-agent' });
            }}
            onResetModelSource={() => setModelSource(null)}
            savedProviderForm={savedProviderForm}
            onSavedProviderFormChange={setSavedProviderForm}
            savedSelectedModels={savedSelectedModels}
            onSavedSelectedModelsChange={setSavedSelectedModels}
            onGoToNextLayer={() => {
              if (modelsAdded) {
                goToStep2Layer(4);
              } else {
                goToStep2Layer(3);
              }
            }}
            runnerConfigItems={selectedRunnerConfigItems}
            runnerConfigValues={runnerConfig}
            onRunnerConfigChange={setRunnerConfig}
          />
        )}
        {currentStep === 3 && <StepDone />}
      </div>

      {/* Footer navigation */}
      {currentStep < 3 && (
        <div className="shrink-0 flex justify-between items-center px-4 sm:px-6 py-3 sm:py-4 border-t">
          <Button
            variant="outline"
            onClick={goPrev}
            disabled={currentStep === 0}
          >
            <ArrowLeft className="w-4 h-4 mr-1.5" />
            {t('wizard.prev')}
          </Button>

          {currentStep === 0 ? (
            <Button
              onClick={handleCreateBot}
              disabled={!canProceed() || isCreatingBot}
            >
              {isCreatingBot && (
                <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
              )}
              {t('wizard.confirmCreateBot')}
              <ArrowRight className="w-4 h-4 ml-1.5" />
            </Button>
          ) : currentStep === 1 ? (
            <Button onClick={goNext} disabled={!canProceed()}>
              {t('wizard.next')}
              <ArrowRight className="w-4 h-4 ml-1.5" />
            </Button>
          ) : (
            <Button
              onClick={handleFinish}
              disabled={!canProceed() || isSubmitting}
            >
              {isSubmitting && (
                <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
              )}
              {t('wizard.finish')}
            </Button>
          )}
        </div>
      )}

      {/* Skip confirmation dialog */}
      <Dialog open={showSkipConfirm} onOpenChange={setShowSkipConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('wizard.skip')}</DialogTitle>
            <DialogDescription>
              {t('wizard.skipConfirmMessage')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowSkipConfirm(false)}
              disabled={isSkipping}
            >
              {t('wizard.prev')}
            </Button>
            <Button onClick={handleSkipConfirm} disabled={isSkipping}>
              {isSkipping && (
                <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
              )}
              {t('wizard.skipConfirmOk')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 0: Select Platform
// ---------------------------------------------------------------------------

function StepPlatform({
  adapters,
  selected,
  onSelect,
}: {
  adapters: Adapter[];
  selected: string | null;
  onSelect: (name: string) => void;
}) {
  const { t } = useTranslation();

  const groupedAdapters = useMemo(() => {
    const withCategories = adapters.map((a) => ({
      ...a,
      categories: a.spec.categories,
    }));
    return groupByCategory(withCategories);
  }, [adapters]);

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="text-center">
        <h2 className="text-xl font-semibold">{t('wizard.platform.title')}</h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t('wizard.platform.description')}
        </p>
      </div>
      {groupedAdapters.map((group) => (
        <div key={group.categoryId ?? 'uncategorized'} className="space-y-3">
          {group.categoryId && (
            <h3 className="text-sm font-medium text-muted-foreground">
              {getCategoryLabel(t, group.categoryId)}
            </h3>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {group.items.map((adapter) => (
              <Card
                key={adapter.name}
                className={cn(
                  'cursor-pointer transition-all hover:shadow-md',
                  selected === adapter.name
                    ? 'ring-2 ring-primary shadow-md'
                    : 'hover:border-primary/50',
                )}
                onClick={() => onSelect(adapter.name)}
              >
                <CardHeader className="flex flex-row items-center gap-3 pb-2">
                  <img
                    src={httpClient.getAdapterIconURL(adapter.name)}
                    alt=""
                    className="w-10 h-10 rounded-lg shrink-0"
                  />
                  <div className="min-w-0">
                    <CardTitle className="text-base truncate">
                      {extractI18nObject(adapter.label)}
                    </CardTitle>
                  </div>
                  {selected === adapter.name && (
                    <div className="ml-auto shrink-0">
                      <div className="w-5 h-5 rounded-full bg-primary flex items-center justify-center">
                        <Check className="w-3 h-3 text-primary-foreground" />
                      </div>
                    </div>
                  )}
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground line-clamp-2">
                    {extractI18nObject(adapter.description)}
                  </p>
                  {(() => {
                    const docUrl = getAdapterDocUrl(
                      adapter.spec.help_links,
                      i18n.language,
                    );
                    return docUrl ? (
                      <a
                        href={docUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-2 inline-flex items-center text-xs text-primary hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="mr-1 h-3 w-3" />
                        {t('bots.viewAdapterDocs')}
                      </a>
                    ) : null;
                  })()}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 1: Bot Configuration + Logs
// ---------------------------------------------------------------------------

function StepBotConfig({
  adapterConfigItems,
  adapterConfigValues,
  onAdapterConfigChange,
  selectedAdapterName,
  adapters,
  createdBotUuid,
  isSavingBot,
  botSaved,
  onSaveBot,
  webhookUrl,
  extraWebhookUrl,
}: {
  adapterConfigItems: IDynamicFormItemSchema[];
  adapterConfigValues: Record<string, unknown>;
  onAdapterConfigChange: (v: Record<string, unknown>) => void;
  selectedAdapterName: string | null;
  adapters: Adapter[];
  createdBotUuid: string | null;
  isSavingBot: boolean;
  botSaved: boolean;
  onSaveBot: () => void;
  webhookUrl: string;
  extraWebhookUrl: string;
}) {
  const { t } = useTranslation();

  const adapterLabel = useMemo(() => {
    const a = adapters.find((ad) => ad.name === selectedAdapterName);
    return a ? extractI18nObject(a.label) : (selectedAdapterName ?? '');
  }, [adapters, selectedAdapterName]);

  // Stable callback ref
  const onAdapterConfigRef = useRef(onAdapterConfigChange);
  onAdapterConfigRef.current = onAdapterConfigChange;
  const stableAdapterConfigCb = useCallback(
    (val: object) => onAdapterConfigRef.current(val as Record<string, unknown>),
    [],
  );

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold">{t('wizard.botConfig.title')}</h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t('wizard.botConfig.description')}
        </p>
      </div>

      <div className="grid gap-6 grid-cols-1 lg:grid-cols-2">
        {/* Left column: Adapter config form */}
        <div className="space-y-4">
          {adapterConfigItems.length > 0 && (
            <Card>
              <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-base">
                    {t('wizard.config.platformConfig', {
                      platform: adapterLabel,
                    })}
                  </CardTitle>
                  {selectedAdapterName &&
                    (() => {
                      const selectedAdapter = adapters.find(
                        (a) => a.name === selectedAdapterName,
                      );
                      const docUrl = getAdapterDocUrl(
                        selectedAdapter?.spec.help_links,
                        i18n.language,
                      );
                      return docUrl ? (
                        <a
                          href={docUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center text-xs text-primary hover:underline"
                        >
                          <ExternalLink className="mr-1 h-3 w-3" />
                          {t('bots.viewAdapterDocs')}
                        </a>
                      ) : null;
                    })()}
                </div>
                <Button
                  size="sm"
                  onClick={onSaveBot}
                  disabled={isSavingBot}
                  className="w-full sm:w-auto shrink-0"
                >
                  {isSavingBot && (
                    <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                  )}
                  {botSaved
                    ? t('wizard.botConfig.resaveBot')
                    : t('wizard.botConfig.saveBot')}
                </Button>
              </CardHeader>
              <CardContent>
                <DynamicFormComponent
                  itemConfigList={adapterConfigItems}
                  initialValues={adapterConfigValues as Record<string, object>}
                  onSubmit={stableAdapterConfigCb}
                  systemContext={{
                    is_wizard: true,
                    webhook_url: webhookUrl,
                    extra_webhook_url: extraWebhookUrl,
                    outbound_ips: systemInfo.outbound_ips,
                  }}
                />
              </CardContent>
            </Card>
          )}

          {/* Bot saved indicator */}
          {botSaved && (
            <div className="flex items-center gap-2 px-4 py-3 rounded-lg border border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/30">
              <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center shrink-0">
                <Check className="w-3 h-3 text-white" />
              </div>
              <span className="text-sm text-green-700 dark:text-green-300">
                {t('wizard.botConfig.botSaved')}
              </span>
            </div>
          )}
        </div>

        {/* Right column: Bot logs */}
        {createdBotUuid && (
          <Card className="flex flex-col min-h-[400px]">
            <CardHeader className="shrink-0">
              <CardTitle>{t('wizard.botConfig.logsTitle')}</CardTitle>
              <CardDescription>
                {t('wizard.botConfig.logsDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 min-h-0 overflow-hidden">
              <BotLogListComponent
                botId={createdBotUuid}
                autoExpandImages
                hideToolbar
              />
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Model scan sub-component (used within Step 2)
// ---------------------------------------------------------------------------

function WizardModelScan({
  providerUuid,
  initialSelectedModels,
  onSelectedModelsChange,
  onModelsAdded,
}: {
  providerUuid: string | null;
  initialSelectedModels: Set<string>;
  onSelectedModelsChange: (v: Set<string>) => void;
  onModelsAdded: () => void;
}) {
  const { t } = useTranslation();
  const [scanning, setScanning] = useState(false);
  const [scannedModels, setScannedModels] = useState<
    { name: string; context_length?: number | null }[]
  >([]);
  const [selectedModels, setSelectedModels] = useState<Set<string>>(
    initialSelectedModels,
  );
  const [adding, setAdding] = useState(false);
  const [scanDone, setScanDone] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [manualModelName, setManualModelName] = useState('');
  const [manualAdding, setManualAdding] = useState(false);
  const [addedModelNames, setAddedModelNames] = useState<Set<string>>(
    new Set(initialSelectedModels),
  );

  // Auto-scan on mount
  useEffect(() => {
    if (!providerUuid) return;
    let cancelled = false;
    (async () => {
      setScanning(true);
      try {
        const resp = await httpClient.scanProviderModels(
          providerUuid,
          'llm',
        );
        if (!cancelled) {
          setScannedModels(resp.models ?? []);
          setScanDone(true);
        }
      } catch {
        if (!cancelled) setScanDone(true);
      } finally {
        if (!cancelled) setScanning(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [providerUuid]);

  const filteredModels = searchQuery
    ? scannedModels.filter((m) =>
        m.name.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : scannedModels;

  const toggleModel = (name: string) => {
    setSelectedModels((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      onSelectedModelsChange(next);
      return next;
    });
  };

  const handleAddSelected = async () => {
    if (!providerUuid || selectedModels.size === 0) return;
    setAdding(true);
    try {
      for (const name of selectedModels) {
        const model = scannedModels.find((m) => m.name === name);
        await httpClient.createProviderLLMModel({
          name,
          provider_uuid: providerUuid,
          abilities: (model as { abilities?: string[] })?.abilities || ['llm'],
          reasoning_config: { level: 'provider_default' },
          context_length: model?.context_length ?? null,
          extra_args: {},
        } as never);
      }
      toast.success(
        t('wizard.provider.modelsAdded', { count: selectedModels.size }),
      );
      setAddedModelNames((prev) => {
        const next = new Set(prev);
        for (const name of selectedModels) next.add(name);
        return next;
      });
      setSelectedModels(new Set());
      onSelectedModelsChange(new Set());
    } catch {
      toast.error(t('wizard.provider.modelsAddError'));
    } finally {
      setAdding(false);
    }
  };

  const handleManualAdd = async () => {
    const name = manualModelName.trim();
    if (!providerUuid || !name) return;
    setManualAdding(true);
    try {
      await httpClient.createProviderLLMModel({
        name,
        provider_uuid: providerUuid,
        abilities: ['llm'],
        reasoning_config: { level: 'provider_default' },
        context_length: null,
        extra_args: {},
      } as never);
      toast.success(t('wizard.provider.modelsAdded', { count: 1 }));
      setAddedModelNames((prev) => new Set(prev).add(name));
      setManualModelName('');
    } catch {
      toast.error(t('wizard.provider.modelsAddError'));
    } finally {
      setManualAdding(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="text-center mb-6">
        <h2 className="text-xl font-semibold">
          {t('wizard.provider.scanTitle')}
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t('wizard.provider.scanDescription')}
        </p>
      </div>

      <div className="border rounded-lg p-6 bg-card space-y-4">
        {scanning && (
          <div className="flex items-center justify-center gap-2 py-8 text-muted-foreground">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>{t('wizard.provider.scanning')}</span>
          </div>
        )}

        {!scanning && scanDone && (
          <>
            {/* Search input for scanned models */}
            {scannedModels.length > 0 && (
              <Input
                placeholder={t('wizard.provider.searchModels')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="mb-2"
              />
            )}

            {/* Scanned models list */}
            {scannedModels.length > 0 ? (
              <>
                <div className="max-h-48 overflow-y-auto space-y-2">
                  {filteredModels.map((model) => {
                    const isAdded = addedModelNames.has(model.name);
                    return (
                      <label
                        key={model.name}
                        className={cn(
                          'flex items-center gap-3 p-3 rounded-lg border transition-colors',
                          isAdded
                            ? 'opacity-50 cursor-not-allowed bg-muted/50'
                            : 'cursor-pointer hover:bg-accent',
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={selectedModels.has(model.name) || isAdded}
                          disabled={isAdded}
                          onChange={() => toggleModel(model.name)}
                          className="w-4 h-4 rounded"
                        />
                        <div className="flex-1 min-w-0">
                          <span className="text-sm font-medium truncate block">
                            {model.name}
                          </span>
                          {model.context_length && (
                            <span className="text-xs text-muted-foreground">
                              ctx: {model.context_length.toLocaleString()}
                            </span>
                          )}
                        </div>
                        {isAdded && (
                          <span className="text-xs text-green-600 font-medium shrink-0">
                            {t('wizard.provider.alreadyAdded')}
                          </span>
                        )}
                      </label>
                    );
                  })}
                  {filteredModels.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      {t('wizard.provider.noMatch')}
                    </p>
                  )}
                </div>

                <div className="flex gap-3 pt-2">
                  <Button
                    onClick={handleAddSelected}
                    disabled={selectedModels.size === 0 || adding}
                    className="flex-1"
                  >
                    {adding && (
                      <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                    )}
                    {t('wizard.provider.addSelected', {
                      count: selectedModels.size,
                    })}
                  </Button>
                  <Button variant="outline" onClick={onModelsAdded}>
                    {t('wizard.provider.skipModelAdd')}
                  </Button>
                </div>
              </>
            ) : (
              <div className="text-center py-4 text-muted-foreground">
                <p>{t('wizard.provider.noModelsFound')}</p>
              </div>
            )}

            {/* Divider */}
            <div className="flex items-center gap-3 py-2">
              <div className="flex-1 h-px bg-border" />
              <span className="text-xs text-muted-foreground">
                {t('wizard.provider.orDivider')}
              </span>
              <div className="flex-1 h-px bg-border" />
            </div>

            {/* Manual add */}
            <div className="flex gap-2">
              <Input
                placeholder={t('wizard.provider.manualModelPlaceholder')}
                value={manualModelName}
                onChange={(e) => setManualModelName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleManualAdd()}
              />
              <Button
                onClick={handleManualAdd}
                disabled={!manualModelName.trim() || manualAdding}
              >
                {manualAdding && (
                  <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                )}
                {t('wizard.provider.addManual')}
              </Button>
            </div>
          </>
        )}

        {/* Next button when models have been added */}
        {addedModelNames.size > 0 && (
          <div className="flex justify-end pt-2 border-t">
            <Button onClick={onModelsAdded}>
              {t('wizard.next')}
              <ArrowRight className="w-4 h-4 ml-1.5" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 2: Select & Configure AI Engine
// ---------------------------------------------------------------------------

function StepAIEngine({
  runnerOptions,
  step2Layer,
  aiEngineMode,
  onAiEngineModeSelect,
  selectedRunner,
  onSelectRunner,
  isLocalAccount,
  onSpaceAuth,
  modelSource,
  onModelSourceSelect,
  providerCreated,
  createdProviderUuid,
  modelsAdded,
  onProviderCreated,
  onModelsAdded,
  onResetModelSource,
  savedProviderForm,
  onSavedProviderFormChange,
  savedSelectedModels,
  onSavedSelectedModelsChange,
  onGoToNextLayer,
  runnerConfigItems,
  runnerConfigValues,
  onRunnerConfigChange,
}: {
  runnerOptions: { name: string; label: { en_US: string; zh_Hans: string } }[];
  step2Layer: number;
  aiEngineMode: 'orchestrated' | 'llm' | null;
  onAiEngineModeSelect: (mode: 'orchestrated' | 'llm') => void;
  selectedRunner: string | null;
  onSelectRunner: (name: string) => void;
  isLocalAccount: boolean;
  onSpaceAuth: () => void;
  modelSource: 'space' | 'custom' | null;
  onModelSourceSelect: (source: 'space' | 'custom') => void;
  providerCreated: boolean;
  createdProviderUuid: string | null;
  modelsAdded: boolean;
  onProviderCreated: (uuid?: string) => void;
  onModelsAdded: () => void;
  onResetModelSource: () => void;
  savedProviderForm: { name?: string; requester?: string; base_url?: string; api_key?: string };
  onSavedProviderFormChange: (v: { name?: string; requester?: string; base_url?: string; api_key?: string }) => void;
  savedSelectedModels: Set<string>;
  onSavedSelectedModelsChange: (v: Set<string>) => void;
  onGoToNextLayer: () => void;
  runnerConfigItems: IDynamicFormItemSchema[];
  runnerConfigValues: Record<string, unknown>;
  onRunnerConfigChange: (v: Record<string, unknown>) => void;
}) {
  const { t } = useTranslation();

  // Stable callback ref
  const onRunnerConfigRef = useRef(onRunnerConfigChange);
  onRunnerConfigRef.current = onRunnerConfigChange;
  const stableRunnerConfigCb = useCallback(
    (val: object) => onRunnerConfigRef.current(val as Record<string, unknown>),
    [],
  );

  const runnerLabel = useMemo(() => {
    const r = runnerOptions.find((o) => o.name === selectedRunner);
    return r ? extractI18nObject(r.label) : (selectedRunner ?? '');
  }, [runnerOptions, selectedRunner]);

  // Orchestrated runners: everything except local-agent
  const orchestratedRunners = runnerOptions.filter(
    (o) => o.name !== 'local-agent',
  );

  // ---- Layer 0: Main choice ----
  if (step2Layer === 0) {
    return (
      <div className="space-y-6 max-w-3xl mx-auto">
        <div className="text-center">
          <h2 className="text-xl font-semibold">
            {t('wizard.aiEngine.title')}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t('wizard.aiEngine.description')}
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {/* Orchestrated Agent Apps */}
          <div
            className="relative rounded-xl border-2 border-border cursor-pointer transition-all hover:shadow-lg hover:border-primary/50 hover:scale-[1.02]"
            onClick={() => onAiEngineModeSelect('orchestrated')}
          >
            <div className="p-6 flex flex-col items-center gap-4 text-center h-full">
              <div className="w-14 h-14 rounded-full bg-muted flex items-center justify-center">
                <Wrench className="w-7 h-7 text-muted-foreground" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">
                  {t('wizard.aiEngine.orchestrated.title')}
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {t('wizard.aiEngine.orchestrated.description')}
                </p>
              </div>
              <Button variant="outline" size="lg" className="w-full">
                {t('wizard.aiEngine.orchestrated.action')}
              </Button>
            </div>
          </div>

          {/* Direct LLM */}
          <div
            className="relative rounded-xl border-2 border-border cursor-pointer transition-all hover:shadow-lg hover:border-primary/50 hover:scale-[1.02]"
            onClick={() => onAiEngineModeSelect('llm')}
          >
            <div className="p-6 flex flex-col items-center gap-4 text-center h-full">
              <div className="w-14 h-14 rounded-full bg-muted flex items-center justify-center">
                <Rocket className="w-7 h-7 text-muted-foreground" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">
                  {t('wizard.aiEngine.llm.title')}
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {t('wizard.aiEngine.llm.description')}
                </p>
              </div>
              <Button variant="outline" size="lg" className="w-full">
                {t('wizard.aiEngine.llm.action')}
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---- Layer 1a: Orchestrated runners ----
  if (step2Layer === 1 && aiEngineMode === 'orchestrated') {
    return (
      <div className="space-y-6 max-w-4xl mx-auto">
        <div className="text-center">
          <h2 className="text-xl font-semibold">
            {t('wizard.aiEngine.orchestrated.selectTitle')}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t('wizard.aiEngine.orchestrated.selectDescription')}
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {orchestratedRunners.map((opt) => (
            <Card
              key={opt.name}
              className="cursor-pointer transition-all hover:shadow-md hover:border-primary/50"
              onClick={() => onSelectRunner(opt.name)}
            >
              <CardHeader className="flex flex-row items-center gap-3">
                <div className="min-w-0 flex-1">
                  <CardTitle className="text-base">
                    {extractI18nObject(opt.label)}
                  </CardTitle>
                  <CardDescription className="mt-1 text-xs font-mono text-muted-foreground">
                    {opt.name}
                  </CardDescription>
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // ---- Layer 1b: LLM model source selection ----
  if (step2Layer === 1 && aiEngineMode === 'llm') {
    return (
      <div className="space-y-6 max-w-3xl mx-auto">
        <div className="text-center">
          <h2 className="text-xl font-semibold">
            {t('wizard.modelSource.title')}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t('wizard.modelSource.description')}
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {/* LangBot Service */}
          <div
            className="relative rounded-xl border-2 border-border cursor-pointer transition-all hover:shadow-lg hover:border-primary/50 hover:scale-[1.02]"
            onClick={() => onModelSourceSelect('space')}
          >
            <div className="p-6 flex flex-col items-center gap-4 text-center h-full">
              <div className="w-14 h-14 rounded-full bg-muted flex items-center justify-center">
                <Rocket className="w-7 h-7 text-muted-foreground" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">
                  {t('wizard.modelSource.space.title')}
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {t('wizard.modelSource.space.description')}
                </p>
              </div>
              <Button variant="outline" size="lg" className="w-full">
                {t('wizard.modelSource.space.action')}
              </Button>
            </div>
          </div>

          {/* Custom provider */}
          <div
            className="relative rounded-xl border-2 border-border cursor-pointer transition-all hover:shadow-lg hover:border-primary/50 hover:scale-[1.02]"
            onClick={() => onModelSourceSelect('custom')}
          >
            <div className="p-6 flex flex-col items-center gap-4 text-center h-full">
              <div className="w-14 h-14 rounded-full bg-muted flex items-center justify-center">
                <Wrench className="w-7 h-7 text-muted-foreground" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">
                  {t('wizard.modelSource.custom.title')}
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {t('wizard.modelSource.custom.description')}
                </p>
              </div>
              <Button variant="outline" size="lg" className="w-full">
                {t('wizard.modelSource.custom.action')}
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---- Layer 2: Custom provider creation form ----
  if (step2Layer === 2) {
    return (
      <div className="max-w-2xl mx-auto w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
        <div className="text-center mb-6">
          <h2 className="text-xl font-semibold">
            {t('wizard.provider.title')}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t('wizard.provider.description')}
          </p>
        </div>
        <div className="border rounded-lg p-6 bg-card">
          <ProviderForm
            initialValues={savedProviderForm}
            onValuesChange={onSavedProviderFormChange}
            submitButtonText={t('wizard.provider.saveAndNext')}
            onFormSubmit={(uuid) => {
              onProviderCreated(uuid);
            }}
            onFormCancel={onResetModelSource}
          />
        </div>
      </div>
    );
  }

  // ---- Layer 2.5: Model scan & add after provider creation ----
  if (step2Layer === 3) {
    return (
      <WizardModelScan
        providerUuid={createdProviderUuid}
        initialSelectedModels={savedSelectedModels}
        onSelectedModelsChange={onSavedSelectedModelsChange}
        onModelsAdded={onModelsAdded}
      />
    );
  }

  // ---- Layer 3: Runner configuration form ----
  return (
    <div className="flex flex-col lg:flex-1 lg:min-h-0 max-w-6xl mx-auto w-full">
      <div className="text-center shrink-0 mb-4">
        <h2 className="text-xl font-semibold">{t('wizard.aiEngine.title')}</h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t('wizard.aiEngine.description')}
        </p>
      </div>

      <div className="flex flex-col lg:flex-row lg:justify-center gap-6 lg:flex-1 lg:min-h-0 animate-in fade-in slide-in-from-bottom-2 duration-300">
        {/* Left: runner list (only for orchestrated mode) */}
        {aiEngineMode === 'orchestrated' && (
          <div className="w-full lg:w-[280px] shrink-0 lg:overflow-y-auto lg:pr-3">
            <div className="space-y-3 p-1">
              {orchestratedRunners.map((opt) => {
                const isSelected = selectedRunner === opt.name;
                return (
                  <Card
                    key={opt.name}
                    className={cn(
                      'cursor-pointer transition-all',
                      isSelected
                        ? 'ring-2 ring-primary shadow-md'
                        : 'opacity-50 hover:opacity-80 hover:border-primary/50',
                    )}
                    onClick={() => onSelectRunner(opt.name)}
                  >
                    <CardHeader className="flex flex-row items-center gap-3 py-3 px-4">
                      <div className="min-w-0 flex-1">
                        <CardTitle
                          className={cn(
                            'text-sm',
                            !isSelected && 'text-muted-foreground',
                          )}
                        >
                          {extractI18nObject(opt.label)}
                        </CardTitle>
                        <CardDescription className="text-xs font-mono text-muted-foreground">
                          {opt.name}
                        </CardDescription>
                      </div>
                      {isSelected && (
                        <div className="shrink-0">
                          <div className="w-5 h-5 rounded-full bg-primary flex items-center justify-center">
                            <Check className="w-3 h-3 text-primary-foreground" />
                          </div>
                        </div>
                      )}
                    </CardHeader>
                  </Card>
                );
              })}
            </div>
          </div>
        )}

        {/* Right: runner configuration */}
        <div
          className={cn(
            'shrink-0 lg:overflow-y-auto lg:pr-3 animate-in fade-in slide-in-from-right-2 duration-300',
            aiEngineMode === 'orchestrated'
              ? 'w-full lg:w-[560px]'
              : 'w-full max-w-2xl mx-auto',
          )}
        >
          <div className="p-1">
            {runnerConfigItems.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>
                    {t('wizard.config.aiConfig', { engine: runnerLabel })}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <DynamicFormComponent
                    key={selectedRunner ?? 'llm'}
                    itemConfigList={runnerConfigItems}
                    initialValues={runnerConfigValues as Record<string, object>}
                    onSubmit={stableRunnerConfigCb}
                    systemContext={{ is_wizard: true }}
                  />
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 3: Done
// ---------------------------------------------------------------------------

function StepDone() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [particles] = useState(() =>
    Array.from({ length: 30 }, (_, i) => ({
      id: i,
      left: Math.random() * 100,
      delay: Math.random() * 2,
      duration: 2 + Math.random() * 2,
      size: 4 + Math.random() * 6,
      color: [
        'bg-purple-400',
        'bg-pink-400',
        'bg-orange-400',
        'bg-blue-400',
        'bg-green-400',
        'bg-yellow-400',
      ][Math.floor(Math.random() * 6)],
    })),
  );

  const [isCompleting, setIsCompleting] = useState(false);

  const handleBack = useCallback(async () => {
    setIsCompleting(true);
    try {
      if (systemInfo.wizard_status === 'none') {
        await httpClient.updateWizardStatus('completed');
        systemInfo.wizard_status = 'completed';
      }
      // Always clear persisted progress so re-entering starts fresh
      await httpClient.saveWizardProgress({
        step: 0,
        selected_adapter: null,
        created_bot_uuid: null,
        bot_saved: false,
        selected_runner: null,
      });
      systemInfo.wizard_progress = null;
    } catch {
      toast.error(t('wizard.completeSaveError'));
      setIsCompleting(false);
      return;
    }
    setIsCompleting(false);
    navigate('/home/bots');
  }, [navigate, t]);

  return (
    <div className="relative flex flex-col items-center justify-center h-full min-h-[400px]">
      {/* Confetti particles */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {particles.map((p) => (
          <div
            key={p.id}
            className={cn('absolute rounded-full opacity-0', p.color)}
            style={{
              left: `${p.left}%`,
              width: p.size,
              height: p.size,
              animation: `wizardConfetti ${p.duration}s ease-out ${p.delay}s forwards`,
            }}
          />
        ))}
      </div>

      <PartyPopper className="w-16 h-16 text-primary mb-4" />
      <h2 className="text-2xl font-bold">{t('wizard.done.title')}</h2>
      <p className="text-muted-foreground mt-2 text-center max-w-md">
        {t('wizard.done.description')}
      </p>
      <Button className="mt-6" onClick={handleBack} disabled={isCompleting}>
        {isCompleting && <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />}
        {t('wizard.done.backToWorkbench')}
      </Button>

      <style>{`
        @keyframes wizardConfetti {
          0% {
            transform: translateY(100vh) rotate(0deg);
            opacity: 1;
          }
          100% {
            transform: translateY(-20vh) rotate(720deg);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
}
