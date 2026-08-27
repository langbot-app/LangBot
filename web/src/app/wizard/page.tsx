import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { UUID } from 'uuidjs';
import { toast } from 'sonner';
import {
  ArrowLeft,
  ArrowRight,
  AlertTriangle,
  Check,
  Sparkles,
  Loader2,
  X,
  ExternalLink,
  Cable,
  Settings2,
  Blocks,
  Copy,
  Send,
  Webhook,
  MessageSquare,
} from 'lucide-react';

import { httpClient } from '@/app/infra/http/HttpClient';
import {
  systemInfo,
  bootstrapWorkspaceSession,
  initializeSystemInfo,
  userInfo,
} from '@/app/infra/http';
import { Adapter, Bot, WizardProgress } from '@/app/infra/entities/api';
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
import { BotLogListComponent } from '@/app/home/bots/components/bot-log/view/BotLogListComponent';
import OwnModelSetup, {
  OwnModelSelection,
} from '@/app/wizard/components/OwnModelSetup';
import { extractI18nObject } from '@/i18n/I18nProvider';
import {
  groupByCategory,
  getCategoryLabel,
} from '@/app/infra/entities/adapter-categories';
import { getAdapterDocUrl } from '@/app/infra/entities/adapter-docs';
import i18n from 'i18next';

import {
  configureLocalAgentPrimaryModel,
  ensureHttpBotSigningSecret,
  findDefaultPipeline,
  getErrorMessage,
  isRequiredRunnerConfigComplete,
  isWebhookModeEnabled,
} from '@/app/wizard/utils';

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

const TOTAL_STEPS = 3;

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
  const [createdBotUuid, setCreatedBotUuid] = useState<string | null>(null);
  const [createdPipelineUuid, setCreatedPipelineUuid] = useState<string | null>(
    null,
  );
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
  const [messageReceived, setMessageReceived] = useState(false);
  const [aiChoice, setAiChoice] = useState<
    'external' | 'own-model' | 'more-features' | null
  >('more-features');
  const [ownModelSelection, setOwnModelSelection] =
    useState<OwnModelSelection | null>(null);

  // ---- Helper: persist wizard progress to backend (fire-and-forget) ----
  const saveProgress = useCallback(
    (overrides: Partial<WizardProgress> = {}) => {
      const progress: WizardProgress = {
        step: overrides.step ?? currentStep,
        selected_adapter: overrides.selected_adapter ?? selectedAdapter,
        created_bot_uuid: overrides.created_bot_uuid ?? createdBotUuid,
        created_pipeline_uuid:
          overrides.created_pipeline_uuid ?? createdPipelineUuid,
        bot_saved: overrides.bot_saved ?? botSaved,
        message_received: overrides.message_received ?? messageReceived,
        selected_runner: overrides.selected_runner ?? selectedRunner,
      };
      httpClient.saveWizardProgress(progress).catch((err) => {
        console.error('Failed to save wizard progress', err);
      });
    },
    [
      currentStep,
      selectedAdapter,
      createdBotUuid,
      createdPipelineUuid,
      botSaved,
      messageReceived,
      selectedRunner,
    ],
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

            const restoredAdapter =
              progress.selected_adapter ?? botData.bot.adapter;
            const restoredConfig = (botData.bot.adapter_config ?? {}) as Record<
              string,
              unknown
            >;
            const configToRestore = ensureHttpBotSigningSecret(
              restoredAdapter,
              restoredConfig,
            );
            const configNeedsSave = configToRestore !== restoredConfig;

            setSelectedAdapter(restoredAdapter);
            setCreatedBotUuid(progress.created_bot_uuid);
            setCreatedPipelineUuid(progress.created_pipeline_uuid ?? null);
            setBotSaved(
              configNeedsSave ? false : (progress.bot_saved ?? false),
            );
            setMessageReceived(progress.message_received ?? false);
            setSelectedRunner(progress.selected_runner);

            // Restore bot name from fetched bot data
            setBotName(botData.bot.name);
            setAdapterConfig(configToRestore);

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
                created_pipeline_uuid: null,
                bot_saved: false,
                message_received: false,
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
    return (runnerField?.options ?? []).filter(
      (option) => option.name !== 'local-agent',
    );
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

  const isRunnerConfigComplete = useMemo(
    () =>
      isRequiredRunnerConfigComplete(selectedRunnerConfigItems, runnerConfig),
    [selectedRunnerConfigItems, runnerConfig],
  );

  // ---- Runner selection with progress saving ----
  const handleSelectRunner = useCallback(
    (runner: string) => {
      if (runner !== selectedRunner) setRunnerConfig({});
      setSelectedRunner(runner);
      saveProgress({ step: 2, selected_runner: runner });
    },
    [saveProgress, selectedRunner],
  );

  // ---- Navigation helpers ----

  const canProceed = useCallback((): boolean => {
    switch (currentStep) {
      case 0:
        return selectedAdapter !== null;
      case 1:
        return createdBotUuid !== null && botSaved && messageReceived;
      case 2:
        return aiChoice !== null;
      default:
        return false;
    }
  }, [
    currentStep,
    selectedAdapter,
    createdBotUuid,
    botSaved,
    messageReceived,
    aiChoice,
  ]);

  const goNext = useCallback(() => {
    if (currentStep < TOTAL_STEPS - 1 && canProceed()) {
      const nextStep = currentStep + 1;
      setCurrentStep(nextStep);
      saveProgress({ step: nextStep });
    }
  }, [currentStep, canProceed, saveProgress]);

  const goPrev = useCallback(() => {
    if (currentStep > 0) {
      const prevStep = currentStep - 1;
      if (currentStep === 2) {
        setOwnModelSelection(null);
      }
      setCurrentStep(prevStep);
      saveProgress({ step: prevStep });
    }
  }, [currentStep, saveProgress]);

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
      const initialConfig = ensureHttpBotSigningSecret(
        selectedAdapter,
        defaultConfig,
      );
      setAdapterConfig(initialConfig);

      const bot: Bot = {
        name: defaultName,
        description: '',
        adapter: selectedAdapter,
        adapter_config: initialConfig,
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
        created_pipeline_uuid: null,
        bot_saved: false,
        message_received: false,
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
  // Binds the bot to the Workspace default pipeline and enables it.

  const handleSaveBot = useCallback(async () => {
    if (!createdBotUuid || !selectedAdapter) return;
    setIsSavingBot(true);

    let createdPipelineThisAttempt: string | null = null;
    try {
      const pipelinesResponse = await httpClient.getPipelines(
        'updated_at',
        'DESC',
      );
      const defaultPipeline = findDefaultPipeline(pipelinesResponse.pipelines);
      let pipelineUuid = defaultPipeline?.uuid ?? null;
      let createdDefaultPipeline = false;

      if (!pipelineUuid) {
        const pipelineResp = await httpClient.createPipeline({
          name: `${botName} Agent`,
          description: botDescription || '',
          config: {},
          is_default: true,
        });
        pipelineUuid = pipelineResp.uuid;
        createdPipelineThisAttempt = pipelineUuid;
        createdDefaultPipeline = true;
      }

      const pipelineData = await httpClient.getPipeline(pipelineUuid);
      const fullConfig = pipelineData.pipeline.config as unknown as Record<
        string,
        unknown
      >;
      const aiConfig = (fullConfig.ai ?? {}) as Record<string, unknown>;
      const runnerConfig = (aiConfig.runner ?? {}) as Record<string, unknown>;
      const localAgentConfig = (aiConfig['local-agent'] ?? {}) as Record<
        string,
        unknown
      >;
      const modelConfig = (localAgentConfig.model ?? {}) as Record<
        string,
        unknown
      >;
      const usesLocalAgent =
        createdDefaultPipeline || runnerConfig.runner === 'local-agent';
      const needsPrimaryModel =
        usesLocalAgent &&
        (typeof modelConfig.primary !== 'string' || !modelConfig.primary);

      if (createdDefaultPipeline || needsPrimaryModel) {
        const recommendedModel = await httpClient.getWizardRecommendedModel();
        await httpClient.updatePipeline(pipelineUuid, {
          name: pipelineData.pipeline.name,
          description: pipelineData.pipeline.description || '',
          config: {
            ...fullConfig,
            ai: {
              ...aiConfig,
              runner: createdDefaultPipeline
                ? { ...runnerConfig, runner: 'local-agent' }
                : runnerConfig,
              'local-agent': {
                ...localAgentConfig,
                model: {
                  ...modelConfig,
                  primary: recommendedModel.uuid,
                  fallbacks: Array.isArray(modelConfig.fallbacks)
                    ? modelConfig.fallbacks
                    : [],
                },
              },
            },
          },
        });
      }
      setCreatedPipelineUuid(pipelineUuid);

      const configToSave = ensureHttpBotSigningSecret(
        selectedAdapter,
        adapterConfig,
      );
      setAdapterConfig(configToSave);

      await httpClient.updateBot(createdBotUuid, {
        name: botName,
        description: botDescription || '',
        adapter: selectedAdapter,
        adapter_config: configToSave,
        enable: true,
        use_pipeline_uuid: pipelineUuid,
      });
      setBotSaved(true);
      setMessageReceived(false);

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
      saveProgress({
        step: 1,
        bot_saved: true,
        message_received: false,
        created_pipeline_uuid: pipelineUuid,
      });
    } catch (err) {
      if (createdPipelineThisAttempt) {
        await httpClient
          .deletePipeline(createdPipelineThisAttempt)
          .catch(() => {});
        setCreatedPipelineUuid(null);
      }
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

  const handleMessageReceived = useCallback(() => {
    if (messageReceived) return;
    setMessageReceived(true);
    saveProgress({ step: 1, message_received: true });
  }, [messageReceived, saveProgress]);

  const completeWizard = useCallback(async () => {
    await httpClient.updateWizardStatus('completed');
    systemInfo.wizard_status = 'completed';
    systemInfo.wizard_progress = null;
  }, []);

  // ---- Complete the optional AI Engine step ----

  const handleFinish = useCallback(async () => {
    if (!aiChoice || !createdBotUuid || !createdPipelineUuid) return;
    if (aiChoice === 'external' && (!selectedRunner || !isRunnerConfigComplete))
      return;
    if (aiChoice === 'own-model' && !ownModelSelection) return;
    setIsSubmitting(true);
    let externalPipelineUuid: string | null = null;
    let externalPipelineBound = false;
    let createdOwnModelUuid: string | null = null;
    let ownModelPipelineUuid: string | null = null;
    let ownModelPipelineBound = false;
    let originalOwnModelBot: Bot | null = null;

    try {
      if (aiChoice === 'external' && selectedRunner) {
        const pipelineResp = await httpClient.createPipeline({
          name: `${botName} External Agent`,
          description: botDescription || '',
          config: {},
        });
        externalPipelineUuid = pipelineResp.uuid;
        const createdPipeline = await httpClient.getPipeline(pipelineResp.uuid);
        const fullConfig = createdPipeline.pipeline.config;
        await httpClient.updatePipeline(pipelineResp.uuid, {
          name: `${botName} External Agent`,
          description: botDescription || '',
          config: {
            ...fullConfig,
            ai: {
              ...fullConfig.ai,
              runner: { runner: selectedRunner },
              [selectedRunner]: runnerConfig,
            },
          },
        });

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
        externalPipelineBound = true;
      }

      if (aiChoice === 'own-model' && ownModelSelection) {
        const modelResponse = await httpClient.createProviderLLMModel({
          name: ownModelSelection.model.name,
          provider_uuid: ownModelSelection.providerUuid,
          abilities: ownModelSelection.model.abilities ?? [],
          reasoning_config: { level: 'provider_default' },
          context_length: ownModelSelection.model.context_length ?? null,
          extra_args: {},
        });
        createdOwnModelUuid = modelResponse.uuid;

        const pipelineResponse = await httpClient.createPipeline({
          name: `${botName} Custom Agent`,
          description: botDescription || '',
          config: {},
        });
        ownModelPipelineUuid = pipelineResponse.uuid;
        const createdPipeline =
          await httpClient.getPipeline(ownModelPipelineUuid);
        const fullConfig = createdPipeline.pipeline.config as unknown as Record<
          string,
          unknown
        >;
        await httpClient.updatePipeline(ownModelPipelineUuid, {
          name: `${botName} Custom Agent`,
          description: botDescription || '',
          config: configureLocalAgentPrimaryModel(
            fullConfig,
            createdOwnModelUuid,
          ),
        });

        originalOwnModelBot = (await httpClient.getBot(createdBotUuid)).bot;
        await httpClient.updateBot(createdBotUuid, {
          name: originalOwnModelBot.name,
          description: originalOwnModelBot.description,
          adapter: originalOwnModelBot.adapter,
          adapter_config: originalOwnModelBot.adapter_config,
          enable: originalOwnModelBot.enable,
          use_pipeline_uuid: ownModelPipelineUuid,
        });
        ownModelPipelineBound = true;
      }

      await completeWizard();
      navigate('/home', { replace: true });
    } catch (err) {
      if (externalPipelineUuid && !externalPipelineBound) {
        await httpClient.deletePipeline(externalPipelineUuid).catch(() => {});
      }
      if (createdOwnModelUuid) {
        let canCleanUpOwnModelResources = !ownModelPipelineBound;
        if (ownModelPipelineBound && originalOwnModelBot) {
          try {
            await httpClient.updateBot(createdBotUuid, {
              name: originalOwnModelBot.name,
              description: originalOwnModelBot.description,
              adapter: originalOwnModelBot.adapter,
              adapter_config: originalOwnModelBot.adapter_config,
              enable: originalOwnModelBot.enable,
              use_pipeline_uuid: originalOwnModelBot.use_pipeline_uuid,
            });
            canCleanUpOwnModelResources = true;
          } catch {
            canCleanUpOwnModelResources = false;
          }
        }

        if (canCleanUpOwnModelResources) {
          let pipelineDeleted = ownModelPipelineUuid === null;
          if (ownModelPipelineUuid) {
            try {
              await httpClient.deletePipeline(ownModelPipelineUuid);
              pipelineDeleted = true;
            } catch {
              pipelineDeleted = false;
            }
          }
          if (pipelineDeleted) {
            await httpClient
              .deleteProviderLLMModel(createdOwnModelUuid)
              .catch(() => {});
          }
        }
      }
      const apiErr = err as { msg?: string };
      toast.error(
        t('wizard.createError') + (apiErr?.msg ? `: ${apiErr.msg}` : ''),
      );
    } finally {
      setIsSubmitting(false);
    }
  }, [
    selectedRunner,
    isRunnerConfigComplete,
    createdBotUuid,
    createdPipelineUuid,
    aiChoice,
    botName,
    botDescription,
    runnerConfig,
    ownModelSelection,
    completeWizard,
    navigate,
    t,
  ]);

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
        created_pipeline_uuid: null,
        bot_saved: false,
        message_received: false,
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
          {currentStep < TOTAL_STEPS && (
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
          currentStep === 2 && aiChoice === 'external' && selectedRunner
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
            messageReceived={messageReceived}
            onMessageReceived={handleMessageReceived}
            onSaveBot={handleSaveBot}
            webhookUrl={webhookUrl}
            extraWebhookUrl={extraWebhookUrl}
          />
        )}
        {currentStep === 2 && (
          <StepAIEngine
            runnerOptions={runnerOptions}
            choice={aiChoice}
            onChoiceChange={setAiChoice}
            selected={selectedRunner}
            onSelect={handleSelectRunner}
            runnerConfigItems={selectedRunnerConfigItems}
            runnerConfigValues={runnerConfig}
            onRunnerConfigChange={setRunnerConfig}
            onOwnModelSelectionChange={setOwnModelSelection}
          />
        )}
      </div>

      {/* Footer navigation */}
      {currentStep < TOTAL_STEPS && (
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
              disabled={
                !canProceed() ||
                isSubmitting ||
                (aiChoice === 'external' &&
                  (!selectedRunner || !isRunnerConfigComplete)) ||
                (aiChoice === 'own-model' && !ownModelSelection)
              }
            >
              {isSubmitting && (
                <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
              )}
              {aiChoice === 'external'
                ? t('wizard.aiEngine.createExternal')
                : aiChoice === 'own-model'
                  ? t('wizard.aiEngine.finishWithModel')
                  : t('wizard.aiEngine.openWorkbench')}
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
    const uniqueAdapters = Array.from(
      new Map(adapters.map((adapter) => [adapter.name, adapter])).values(),
    );
    const withCategories = uniqueAdapters.map((a) => ({
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

function PageBotFloatingWidget({
  botUuid,
  title,
  testNotice,
}: {
  botUuid: string;
  title?: string;
  testNotice: string;
}) {
  useEffect(() => {
    const script = document.createElement('script');
    script.src = `${window.location.origin}/api/v1/embed/${botUuid}/widget.js?preview=wizard&v=${Date.now()}`;
    script.dataset.title = title || 'LangBot';
    script.dataset.testNotice = testNotice;
    document.body.appendChild(script);

    return () => {
      script.remove();
      const root = document.getElementById('langbot-widget-root') as
        | (HTMLElement & { langbotDestroy?: () => void })
        | null;
      if (root?.langbotDestroy) {
        root.langbotDestroy();
      } else {
        root?.remove();
      }
    };
  }, [botUuid, testNotice, title]);

  return null;
}

function StepBotConfig({
  adapterConfigItems,
  adapterConfigValues,
  onAdapterConfigChange,
  selectedAdapterName,
  adapters,
  createdBotUuid,
  isSavingBot,
  botSaved,
  messageReceived,
  onMessageReceived,
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
  messageReceived: boolean;
  onMessageReceived: () => void;
  onSaveBot: () => void;
  webhookUrl: string;
  extraWebhookUrl: string;
}) {
  const { t } = useTranslation();
  const [testMessage, setTestMessage] = useState(
    t('wizard.botConfig.httpTestDefaultMessage'),
  );
  const [isSendingTest, setIsSendingTest] = useState(false);

  const adapterLabel = useMemo(() => {
    const a = adapters.find((ad) => ad.name === selectedAdapterName);
    return a ? extractI18nObject(a.label) : (selectedAdapterName ?? '');
  }, [adapters, selectedAdapterName]);

  const webhookModeEnabled = useMemo(
    () =>
      isWebhookModeEnabled(adapterConfigItems, adapterConfigValues) &&
      Boolean(webhookUrl),
    [adapterConfigItems, adapterConfigValues, webhookUrl],
  );
  const receivedMessageWithoutLangBotAccount =
    messageReceived && userInfo?.account_type !== 'space';
  const receivedMessageSuccessfully =
    messageReceived && !receivedMessageWithoutLangBotAccount;

  // Stable callback ref
  const onAdapterConfigRef = useRef(onAdapterConfigChange);
  onAdapterConfigRef.current = onAdapterConfigChange;
  const stableAdapterConfigCb = useCallback(
    (val: object) => onAdapterConfigRef.current(val as Record<string, unknown>),
    [],
  );

  const copyWebhookUrl = useCallback(async () => {
    if (!webhookUrl) return;
    await navigator.clipboard.writeText(webhookUrl);
    toast.success(t('common.copySuccess'));
  }, [t, webhookUrl]);

  const sendHttpBotTest = useCallback(async () => {
    if (!createdBotUuid || !testMessage.trim()) return;
    setIsSendingTest(true);
    try {
      await httpClient.testHttpBotInbound(createdBotUuid, testMessage.trim());
      toast.success(t('wizard.botConfig.httpTestAccepted'));
    } catch (error) {
      toast.error(
        t('wizard.botConfig.httpTestFailed', {
          error: getErrorMessage(error),
        }),
      );
    } finally {
      setIsSendingTest(false);
    }
  }, [createdBotUuid, testMessage, t]);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {selectedAdapterName === 'web_page_bot' && botSaved && createdBotUuid && (
        <PageBotFloatingWidget
          botUuid={createdBotUuid}
          title={
            typeof adapterConfigValues.title === 'string'
              ? adapterConfigValues.title
              : undefined
          }
          testNotice={t('wizard.botConfig.pageBotTestNotice')}
        />
      )}

      <div className="text-center">
        <h2 className="text-xl font-semibold">{t('wizard.botConfig.title')}</h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t('wizard.botConfig.description')}
        </p>
      </div>

      {botSaved && (
        <div
          className={cn(
            'border px-4 py-3',
            receivedMessageSuccessfully
              ? 'border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/30'
              : 'border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30',
          )}
        >
          <div className="flex items-start gap-3">
            <div
              className={cn(
                'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full',
                receivedMessageSuccessfully ? 'bg-green-500' : 'bg-amber-500',
              )}
            >
              {receivedMessageWithoutLangBotAccount ? (
                <AlertTriangle className="size-3 text-white" />
              ) : messageReceived ? (
                <Check className="size-3 text-white" />
              ) : selectedAdapterName === 'web_page_bot' ? (
                <MessageSquare className="size-3 text-white" />
              ) : selectedAdapterName === 'http_bot' ? (
                <Send className="size-3 text-white" />
              ) : webhookModeEnabled ? (
                <Webhook className="size-3 text-white" />
              ) : (
                <Loader2 className="size-3 animate-spin text-white" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <p
                className={cn(
                  'text-sm font-medium',
                  receivedMessageSuccessfully
                    ? 'text-green-800 dark:text-green-200'
                    : 'text-amber-800 dark:text-amber-200',
                )}
              >
                {messageReceived
                  ? t(
                      receivedMessageWithoutLangBotAccount
                        ? 'wizard.botConfig.messageReceivedLocalAccountWarning'
                        : 'wizard.botConfig.messageReceived',
                    )
                  : selectedAdapterName === 'web_page_bot'
                    ? t('wizard.botConfig.pageBotTestPrompt')
                    : selectedAdapterName === 'http_bot'
                      ? t('wizard.botConfig.httpTestPrompt')
                      : webhookModeEnabled
                        ? t('wizard.botConfig.webhookTestPrompt')
                        : t('wizard.botConfig.waitingForMessage')}
              </p>

              {!messageReceived && webhookModeEnabled && (
                <div className="mt-3 space-y-3">
                  <div className="flex items-center gap-2">
                    <code className="min-w-0 flex-1 overflow-hidden text-ellipsis whitespace-nowrap border bg-background px-2.5 py-2 text-xs">
                      {webhookUrl}
                    </code>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="size-9 shrink-0"
                      onClick={copyWebhookUrl}
                      title={t('common.copy')}
                    >
                      <Copy className="size-4" />
                    </Button>
                  </div>

                  {selectedAdapterName === 'http_bot' && (
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <Input
                        value={testMessage}
                        onChange={(event) => setTestMessage(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') void sendHttpBotTest();
                        }}
                        className="bg-background"
                      />
                      <Button
                        type="button"
                        onClick={() => void sendHttpBotTest()}
                        disabled={isSendingTest || !testMessage.trim()}
                        className="shrink-0"
                      >
                        {isSendingTest ? (
                          <Loader2 className="mr-1.5 size-4 animate-spin" />
                        ) : (
                          <Send className="mr-1.5 size-4" />
                        )}
                        {t('wizard.botConfig.sendHttpTest')}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

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
                onMessageReceived={onMessageReceived}
              />
            </CardContent>
          </Card>
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
  choice,
  onChoiceChange,
  selected,
  onSelect,
  runnerConfigItems,
  runnerConfigValues,
  onRunnerConfigChange,
  onOwnModelSelectionChange,
}: {
  runnerOptions: { name: string; label: { en_US: string; zh_Hans: string } }[];
  choice: 'external' | 'own-model' | 'more-features' | null;
  onChoiceChange: (
    choice: 'external' | 'own-model' | 'more-features' | null,
  ) => void;
  selected: string | null;
  onSelect: (name: string) => void;
  runnerConfigItems: IDynamicFormItemSchema[];
  runnerConfigValues: Record<string, unknown>;
  onRunnerConfigChange: (v: Record<string, unknown>) => void;
  onOwnModelSelectionChange: (selection: OwnModelSelection | null) => void;
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
    const r = runnerOptions.find((o) => o.name === selected);
    return r ? extractI18nObject(r.label) : (selected ?? '');
  }, [runnerOptions, selected]);

  const choices = [
    {
      id: 'more-features' as const,
      icon: Blocks,
      title: t('wizard.aiEngine.moreFeaturesTitle'),
      description: t('wizard.aiEngine.moreFeaturesDescription'),
    },
    {
      id: 'external' as const,
      icon: Cable,
      title: t('wizard.aiEngine.externalTitle'),
      description: t('wizard.aiEngine.externalDescription'),
    },
    {
      id: 'own-model' as const,
      icon: Settings2,
      title: t('wizard.aiEngine.ownModelTitle'),
      description: t('wizard.aiEngine.ownModelDescription'),
    },
  ];

  if (choice === 'own-model') {
    return (
      <div
        key="ai-engine-own-model"
        className="w-full animate-in fade-in-0 slide-in-from-right-4 duration-300 ease-out motion-reduce:animate-none"
      >
        <OwnModelSetup
          onBack={() => onChoiceChange('more-features')}
          onSelectionChange={onOwnModelSelectionChange}
        />
      </div>
    );
  }

  if (choice !== 'external') {
    return (
      <div
        key="ai-engine-choices"
        className="mx-auto max-w-4xl space-y-6 animate-in fade-in-0 slide-in-from-left-4 duration-300 ease-out motion-reduce:animate-none"
      >
        <div className="text-center">
          <h2 className="text-xl font-semibold">
            {t('wizard.aiEngine.title')}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t('wizard.aiEngine.optionalDescription')}
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {choices.map((item) => {
            const Icon = item.icon;
            return (
              <Card
                key={item.id}
                className={cn(
                  'cursor-pointer transition-all hover:border-primary/50',
                  choice === item.id && 'ring-2 ring-primary',
                )}
                onClick={() => onChoiceChange(item.id)}
              >
                <CardHeader>
                  <Icon className="size-6 text-primary" />
                  <CardTitle className="text-base">{item.title}</CardTitle>
                  <CardDescription>{item.description}</CardDescription>
                </CardHeader>
              </Card>
            );
          })}
        </div>
      </div>
    );
  }

  // Before any runner is selected: centered grid layout
  if (!selected) {
    return (
      <div
        key="ai-engine-external-picker"
        className="mx-auto max-w-4xl space-y-6 animate-in fade-in-0 slide-in-from-right-4 duration-300 ease-out motion-reduce:animate-none"
      >
        <div className="text-center">
          <h2 className="text-xl font-semibold">
            {t('wizard.aiEngine.externalTitle')}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t('wizard.aiEngine.runnerDescription')}
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onChoiceChange('more-features')}
        >
          <ArrowLeft className="size-4 mr-1.5" />
          {t('wizard.aiEngine.backToChoices')}
        </Button>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {runnerOptions.map((opt) => (
            <Card
              key={opt.name}
              className="cursor-pointer transition-all hover:shadow-md hover:border-primary/50"
              onClick={() => onSelect(opt.name)}
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

  // After a runner is selected: left-right split layout
  // On mobile (< lg): single column, normal scroll from parent
  // On desktop (>= lg): side-by-side with independent scroll per column
  return (
    <div
      key={`ai-engine-external-config-${selected}`}
      className="mx-auto flex w-full max-w-6xl flex-col animate-in fade-in-0 slide-in-from-right-4 duration-300 ease-out motion-reduce:animate-none lg:min-h-0 lg:flex-1"
    >
      <div className="text-center shrink-0 mb-4">
        <h2 className="text-xl font-semibold">
          {t('wizard.aiEngine.externalTitle')}
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t('wizard.aiEngine.description')}
        </p>
      </div>

      <Button
        variant="ghost"
        size="sm"
        className="self-start mb-3"
        onClick={() => onChoiceChange('more-features')}
      >
        <ArrowLeft className="size-4 mr-1.5" />
        {t('wizard.aiEngine.backToChoices')}
      </Button>

      <div className="flex flex-col gap-6 lg:min-h-0 lg:flex-1 lg:flex-row lg:justify-center">
        {/* Left: runner list */}
        <div className="w-full lg:w-[280px] shrink-0 lg:overflow-y-auto lg:pr-3">
          {/* p-1 provides space for ring-2 (4px) to render without clipping */}
          <div className="space-y-3 p-1">
            {runnerOptions.map((opt) => {
              const isSelected = selected === opt.name;
              return (
                <Card
                  key={opt.name}
                  className={cn(
                    'cursor-pointer transition-all',
                    isSelected
                      ? 'ring-2 ring-primary shadow-md'
                      : 'opacity-50 hover:opacity-80 hover:border-primary/50',
                  )}
                  onClick={() => onSelect(opt.name)}
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

        {/* Right: runner configuration — fixed width on desktop */}
        <div className="w-full shrink-0 lg:w-[560px] lg:overflow-y-auto lg:pr-3">
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
                    key={selected}
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
