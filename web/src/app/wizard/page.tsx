import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { UUID } from 'uuidjs';
import { toast } from 'sonner';
import {
  Bug,
  Blocks,
  Cable,
  Settings2,
  ArrowLeft,
  ArrowRight,
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronRight,
  Sparkles,
  MessageSquare,
  PartyPopper,
  Loader2,
  X,
  ExternalLink,
  Download,
  RefreshCw,
  CircleAlert,
  Copy,
  Send,
  Webhook,
} from 'lucide-react';

import { httpClient } from '@/app/infra/http/HttpClient';
import {
  systemInfo,
  bootstrapWorkspaceSession,
  initializeSystemInfo,
  getCloudServiceClientSync,
  getCloudServiceClient,
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
import { extractI18nObject } from '@/i18n/I18nProvider';
import {
  groupByCategory,
  getCategoryLabel,
} from '@/app/infra/entities/adapter-categories';
import { getAdapterDocUrl } from '@/app/infra/entities/adapter-docs';
import i18n from 'i18next';
import { PluginV4 } from '@/app/infra/entities/plugin';
import type { I18nObject } from '@/app/infra/entities/common';
import {
  RunnerMarketplaceError,
  getErrorMessage,
  installMarketplaceRunner,
  loadRunnerCatalog as fetchRunnerCatalog,
  marketplacePluginId,
  readPendingRunnerInstall,
  resumePendingRunnerInstall,
  runnerPluginPrefix,
} from '@/app/home/agents/runner-marketplace';
import {
  LOCAL_AGENT_RUNNER_ID,
  configureLocalAgentPrimaryModel,
  ensureHttpBotSigningSecret,
  isRequiredRunnerConfigComplete,
  isWebhookModeEnabled,
} from '@/app/wizard/utils';

import OwnModelSetup, {
  type OwnModelSelection,
} from '@/app/wizard/components/OwnModelSetup';

type RunnerInstallProgress = { stage: InstallStage; percent: number };

type RunnerPluginStatus = 'installed' | 'debug';

type AIChoice = 'more-features' | 'external' | 'own-model';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { AsyncTask } from '@/app/infra/entities/api';
import {
  InstallStage,
  asyncTaskToPluginInstallTask,
} from '@/app/home/plugins/components/plugin-install-task/PluginInstallTaskContext';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
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
const WIZARD_RUNNER_INSTALL_SCOPE = 'wizard';

function adapterSupportsMessages(adapter: Adapter) {
  const events = adapter.spec.supported_events;
  return !events?.length || events.includes('message.received');
}

// ---------------------------------------------------------------------------
// Main Wizard Page (full-screen, no sidebar)
// ---------------------------------------------------------------------------

export default function WizardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  // ---- Wizard state ----
  const [currentStep, setCurrentStep] = useState(0);
  const [aiChoice, setAiChoice] = useState<AIChoice>('more-features');
  const [ownModelSelection, setOwnModelSelection] =
    useState<OwnModelSelection | null>(null);
  const [preparingDefault, setPreparingDefault] = useState(false);
  const [defaultPreparationProgress, setDefaultPreparationProgress] =
    useState(0);
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
  const [marketplaceRunners, setMarketplaceRunners] = useState<PluginV4[]>([]);
  const [installedPluginIds, setInstalledPluginIds] = useState<string[]>([]);
  const [runnerPluginStatuses, setRunnerPluginStatuses] = useState<
    Record<string, RunnerPluginStatus>
  >({});
  const [runnerPluginDescriptions, setRunnerPluginDescriptions] = useState<
    Record<string, I18nObject>
  >({});
  const [isRunnerCatalogLoading, setIsRunnerCatalogLoading] = useState(true);
  const [runnerCatalogError, setRunnerCatalogError] = useState(false);
  const [installingRunnerPluginId, setInstallingRunnerPluginId] = useState<
    string | null
  >(null);
  const [runnerInstallProgress, setRunnerInstallProgress] = useState<
    Record<string, RunnerInstallProgress>
  >({});
  const [runnerInstallError, setRunnerInstallError] = useState<string | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isCreatingBot, setIsCreatingBot] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSavingBot, setIsSavingBot] = useState(false);
  const [botSaved, setBotSaved] = useState(false);
  const [pageBotPreviewRequest, setPageBotPreviewRequest] = useState(0);
  const [messageReceived, setMessageReceived] = useState(false);

  const loadRunnerCatalog = useCallback(async () => {
    setIsRunnerCatalogLoading(true);
    setRunnerCatalogError(false);
    try {
      const catalog = await fetchRunnerCatalog('agent');
      setMarketplaceRunners(catalog.marketplaceRunners);
      setInstalledPluginIds(catalog.installedPluginIds);
    } catch (error) {
      console.error('Failed to load Runner catalog', error);
      setRunnerCatalogError(true);
    } finally {
      setIsRunnerCatalogLoading(false);
    }
  }, []);

  useEffect(() => {
    if (currentStep !== 2 || aiChoice !== 'external') return;
    void loadRunnerCatalog();
    let cancelled = false;
    // Local status remains available even when the marketplace cannot be reached.
    void httpClient
      .getPlugins()
      .then(({ plugins }) => {
        if (cancelled) return;
        setRunnerPluginDescriptions(
          Object.fromEntries(
            plugins.flatMap((plugin) => {
              const { author, name, description } =
                plugin.manifest.manifest.metadata;
              return description
                ? [[`${author ?? ''}/${name}`, description]]
                : [];
            }),
          ),
        );
        setRunnerPluginStatuses(
          Object.fromEntries(
            plugins.map((plugin) => {
              const { author, name } = plugin.manifest.manifest.metadata;
              return [
                `${author ?? ''}/${name}`,
                plugin.debug ? 'debug' : 'installed',
              ];
            }),
          ),
        );
      })
      .catch((error) =>
        console.error('Failed to load local Runner status', error),
      );
    return () => {
      cancelled = true;
    };
  }, [loadRunnerCatalog, currentStep, aiChoice]);

  // ---- Helper: persist wizard progress to backend (fire-and-forget) ----
  const saveProgress = useCallback(
    (overrides: Partial<WizardProgress> = {}) => {
      const progress: WizardProgress = {
        step: overrides.step ?? currentStep,
        selected_scenario: null,
        selected_adapter:
          overrides.selected_adapter !== undefined
            ? overrides.selected_adapter
            : selectedAdapter,
        created_bot_uuid:
          overrides.created_bot_uuid !== undefined
            ? overrides.created_bot_uuid
            : createdBotUuid,
        created_pipeline_uuid:
          overrides.created_pipeline_uuid !== undefined
            ? overrides.created_pipeline_uuid
            : createdPipelineUuid,
        bot_saved: overrides.bot_saved ?? botSaved,
        message_received: overrides.message_received ?? messageReceived,
        selected_runner:
          overrides.selected_runner !== undefined
            ? overrides.selected_runner
            : selectedRunner,
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
            // Scenario-based drafts may point at Agents. Leave those resources
            // untouched and start a new message-only setup instead.
            if (
              progress.selected_scenario &&
              progress.selected_scenario !== 'message_reply'
            ) {
              throw new Error(
                'Scenario-based wizard draft is no longer supported',
              );
            }
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
            const restoredPipelineUuid =
              progress.created_pipeline_uuid ??
              botData.bot.event_bindings?.find(
                (binding) =>
                  binding.event_pattern === 'message.received' &&
                  binding.target_type === 'pipeline',
              )?.target_uuid ??
              null;
            setCreatedPipelineUuid(restoredPipelineUuid);
            let pipelineReady = false;
            if (restoredPipelineUuid) {
              const { pipeline } =
                await httpClient.getPipeline(restoredPipelineUuid);
              const config = pipeline.config as unknown as Record<
                string,
                unknown
              >;
              const ai = config.ai as
                | {
                    runner?: { id?: string };
                    runner_config?: Record<
                      string,
                      { model?: { primary?: string } }
                    >;
                  }
                | undefined;
              const id = ai?.runner?.id;
              pipelineReady =
                !!id &&
                !!aiTab?.stages.some((stage) => stage.name === id) &&
                (id !== LOCAL_AGENT_RUNNER_ID ||
                  !!ai?.runner_config?.[id]?.model?.primary);
            }
            if (cancelled) return;
            setBotSaved(
              !configNeedsSave &&
                pipelineReady &&
                (progress.bot_saved ?? false),
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

            // Step 3 is resumable so a refresh cannot create a duplicate processor.
            setCurrentStep(pipelineReady ? Math.min(progress.step, 3) : 1);
          } catch {
            // Clear stale or unsupported progress without modifying its resources.
            httpClient
              .saveWizardProgress({
                step: 0,
                selected_scenario: null,
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
    const runnerField = runnerStage.config.find((c) => c.name === 'id');
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

  const isRunnerConfigComplete = useMemo(
    () =>
      isRequiredRunnerConfigComplete(selectedRunnerConfigItems, runnerConfig),
    [selectedRunnerConfigItems, runnerConfig],
  );

  // ---- Runner selection with progress saving ----
  const handleSelectRunner = useCallback(
    (
      runner: string | null,
      configTab: PipelineConfigTab | null = aiConfigTab,
    ) => {
      setSelectedRunner(runner);
      const configStage = configTab?.stages.find((s) => s.name === runner);
      const defaults = configStage ? getDefaultValues(configStage.config) : {};
      setRunnerConfig(defaults);
      saveProgress({ step: 2, selected_runner: runner });
    },
    [aiConfigTab, saveProgress],
  );

  const updateRunnerInstallProgress = useCallback(
    (pluginId: string, task: AsyncTask) => {
      const progress = asyncTaskToPluginInstallTask(task);
      const registering = task.runtime.done && !task.runtime.exception;
      setRunnerInstallProgress((current) => ({
        ...current,
        [pluginId]: {
          stage: registering ? InstallStage.ACTIVATING : progress.stage,
          percent: registering ? 95 : progress.overallProgress,
        },
      }));
    },
    [],
  );

  const finishRunnerProgress = useCallback(
    (pluginId: string, failed = false) => {
      setRunnerInstallProgress((current) => ({
        ...current,
        [pluginId]: {
          stage: failed ? InstallStage.ERROR : InstallStage.DONE,
          percent: failed ? (current[pluginId]?.percent ?? 0) : 100,
        },
      }));
    },
    [],
  );

  const handleInstallRunner = useCallback(
    async (plugin: PluginV4) => {
      const pluginId = marketplacePluginId(plugin);
      setInstallingRunnerPluginId(pluginId);
      setRunnerInstallError(null);
      setRunnerInstallProgress((current) => ({
        ...current,
        [pluginId]: { stage: InstallStage.CHECKING, percent: 0 },
      }));

      try {
        const installed = await installMarketplaceRunner(plugin, {
          scope: WIZARD_RUNNER_INSTALL_SCOPE,
          onProgress: (task) => updateRunnerInstallProgress(pluginId, task),
        });
        finishRunnerProgress(pluginId);
        setAiConfigTab(installed.configTab);
        setRunnerPluginStatuses((current) => ({
          ...current,
          [pluginId]: 'installed',
        }));
        setInstalledPluginIds((current) =>
          current.includes(pluginId) ? current : [...current, pluginId],
        );
        handleSelectRunner(installed.runner.name, installed.configTab);
        toast.success(
          t('wizard.aiEngine.installSuccess', {
            runner: extractI18nObject(plugin.label),
          }),
        );
      } catch (error) {
        finishRunnerProgress(pluginId, true);
        let message = getErrorMessage(error);
        if (error instanceof RunnerMarketplaceError) {
          const key =
            error.code === 'version-unavailable'
              ? 'wizard.aiEngine.versionUnavailable'
              : error.code === 'install-timeout'
                ? 'wizard.aiEngine.installTimeout'
                : 'wizard.aiEngine.registrationTimeout';
          message = t(key);
        }
        message ||= t('wizard.aiEngine.installFailed');
        setRunnerInstallError(message);
        toast.error(message);
      } finally {
        setInstallingRunnerPluginId(null);
      }
    },
    [handleSelectRunner, updateRunnerInstallProgress, finishRunnerProgress, t],
  );

  useEffect(() => {
    if (isLoading) return;
    const pending = readPendingRunnerInstall(WIZARD_RUNNER_INSTALL_SCOPE);
    if (!pending) return;

    let cancelled = false;
    setInstallingRunnerPluginId(pending.pluginId);
    setRunnerInstallError(null);
    void resumePendingRunnerInstall(WIZARD_RUNNER_INSTALL_SCOPE, (task) => {
      if (!cancelled) updateRunnerInstallProgress(pending.pluginId, task);
    })
      .then((installed) => {
        if (cancelled || !installed) return;
        finishRunnerProgress(pending.pluginId);
        setAiConfigTab(installed.configTab);
        setRunnerPluginStatuses((current) => ({
          ...current,
          [pending.pluginId]: 'installed',
        }));
        setInstalledPluginIds((current) =>
          current.includes(pending.pluginId)
            ? current
            : [...current, pending.pluginId],
        );
        handleSelectRunner(installed.runner.name, installed.configTab);
        toast.success(
          t('wizard.aiEngine.installSuccess', {
            runner: pending.pluginLabel,
          }),
        );
      })
      .catch((error) => {
        if (cancelled) return;
        finishRunnerProgress(pending.pluginId, true);
        const message =
          getErrorMessage(error) || t('wizard.aiEngine.installFailed');
        setRunnerInstallError(message);
        toast.error(message);
      })
      .finally(() => {
        if (!cancelled) setInstallingRunnerPluginId(null);
      });

    return () => {
      cancelled = true;
    };
  }, [
    handleSelectRunner,
    isLoading,
    updateRunnerInstallProgress,
    finishRunnerProgress,
    t,
  ]);

  // ---- Navigation helpers ----

  const canProceed = useCallback((): boolean => {
    switch (currentStep) {
      case 0:
        return selectedAdapter !== null;
      case 1:
        return createdBotUuid !== null && botSaved && messageReceived;
      case 2:
        if (aiChoice === 'own-model') return ownModelSelection !== null;
        if (aiChoice === 'external')
          return selectedRunner !== null && isRunnerConfigComplete;
        return createdPipelineUuid !== null;
      default:
        return false;
    }
  }, [
    currentStep,
    aiChoice,
    ownModelSelection,
    createdPipelineUuid,
    selectedAdapter,
    createdBotUuid,
    botSaved,
    messageReceived,
    selectedRunner,
    isRunnerConfigComplete,
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
      setCreatedPipelineUuid(null);

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
        selected_scenario: null,
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
  // Updates the bot's adapter config and enables it.

  const handleSaveBot = useCallback(async () => {
    if (!createdBotUuid || !selectedAdapter) return;
    setIsSavingBot(true);
    setBotSaved(false);
    let previewPipelineUuid = createdPipelineUuid;
    let createdPreviewPipelineUuid: string | null = null;

    try {
      const configToSave = ensureHttpBotSigningSecret(
        selectedAdapter,
        adapterConfig,
      );
      setAdapterConfig(configToSave);

      setDefaultPreparationProgress(0);
      setPreparingDefault(true);
      const onDefaultInstallProgress = (task: AsyncTask) => {
        const progress = asyncTaskToPluginInstallTask(task);
        // Reserve the final 10% for registration, model setup and bot binding.
        setDefaultPreparationProgress(
          Math.min(90, Math.round(progress.overallProgress * 0.9)),
        );
      };
      const metadata = await httpClient.getGeneralPipelineMetadata();
      let configTab = metadata.configs.find((tab) => tab.name === 'ai');
      if (
        !configTab?.stages.some((stage) => stage.name === LOCAL_AGENT_RUNNER_ID)
      ) {
        const scope = 'wizard-default';
        const pending = readPendingRunnerInstall(scope);
        const installed = pending
          ? await resumePendingRunnerInstall(scope, onDefaultInstallProgress)
          : await installMarketplaceRunner(
              (
                await (
                  await getCloudServiceClient()
                ).getPluginDetail('langbot-team', 'LocalAgent')
              ).plugin,
              { scope, onProgress: onDefaultInstallProgress },
            );
        configTab = installed?.configTab;
      }
      const localStage = configTab?.stages.find(
        (stage) => stage.name === LOCAL_AGENT_RUNNER_ID,
      );
      if (!localStage)
        throw new Error(t('wizard.aiEngine.defaultRunnerUnavailable'));
      setAiConfigTab(configTab ?? null);
      setDefaultPreparationProgress(92);

      if (!previewPipelineUuid) {
        const pipelineResp = await httpClient.createPipeline({
          name: `${botName} Pipeline`,
          description: botDescription || '',
          config: {},
        });
        previewPipelineUuid = pipelineResp.uuid;
        createdPreviewPipelineUuid = pipelineResp.uuid;
      }

      const { pipeline } = await httpClient.getPipeline(previewPipelineUuid);
      const config = pipeline.config as unknown as Record<string, unknown>;
      const ai = (config.ai ?? {}) as Record<string, unknown>;
      const configs = (ai.runner_config ?? {}) as Record<
        string,
        Record<string, unknown>
      >;
      const localConfig = {
        ...getDefaultValues(localStage.config),
        ...configs[LOCAL_AGENT_RUNNER_ID],
      };
      const model = localConfig.model as { primary?: string } | undefined;
      const modelUuid =
        model?.primary || (await httpClient.getWizardRecommendedModel()).uuid;
      if (!modelUuid)
        throw new Error(t('wizard.aiEngine.defaultModelUnavailable'));
      setDefaultPreparationProgress(96);
      await httpClient.updatePipeline(previewPipelineUuid, {
        config: configureLocalAgentPrimaryModel(
          {
            ...config,
            ai: {
              ...ai,
              runner_config: {
                ...configs,
                [LOCAL_AGENT_RUNNER_ID]: localConfig,
              },
            },
          },
          modelUuid,
        ),
      });
      setDefaultPreparationProgress(98);

      const botUpdate: Partial<Bot> = {
        name: botName,
        description: botDescription || '',
        adapter: selectedAdapter,
        adapter_config: configToSave,
        enable: true,
      };
      if (previewPipelineUuid) {
        botUpdate.event_bindings = [
          {
            event_pattern: 'message.received',
            target_type: 'pipeline',
            target_uuid: previewPipelineUuid,
            filters: [],
            priority: 0,
            enabled: true,
            description: '',
          },
        ];
      }

      await httpClient.updateBot(createdBotUuid, botUpdate);
      setDefaultPreparationProgress(100);
      if (previewPipelineUuid !== createdPipelineUuid) {
        setCreatedPipelineUuid(previewPipelineUuid);
      }
      setBotSaved(true);
      if (selectedAdapter === 'web_page_bot') {
        setPageBotPreviewRequest((request) => request + 1);
      }
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
        created_pipeline_uuid: previewPipelineUuid,
        bot_saved: true,
        message_received: false,
      });
    } catch (err) {
      if (createdPreviewPipelineUuid) {
        try {
          await httpClient.deletePipeline(createdPreviewPipelineUuid);
        } catch (rollbackError) {
          console.warn(
            'Failed to roll back wizard preview pipeline',
            rollbackError,
          );
        }
      }
      toast.error(`${t('wizard.createError')}: ${getErrorMessage(err)}`);
    } finally {
      setPreparingDefault(false);
      setIsSavingBot(false);
    }
  }, [
    createdBotUuid,
    selectedAdapter,
    botName,
    botDescription,
    adapterConfig,
    createdPipelineUuid,
    t,
    saveProgress,
  ]);

  const handleMessageReceived = useCallback(() => {
    if (messageReceived) return;
    setMessageReceived(true);
    saveProgress({ step: 1, message_received: true });
  }, [messageReceived, saveProgress]);

  // ---- Create Pipeline & Link (Step 2 finish) ----

  const handleFinish = useCallback(async () => {
    if (!createdBotUuid || !createdPipelineUuid || !canProceed()) return;
    setIsSubmitting(true);
    let createdModelUuid: string | null = null;
    let modelBound = false;
    try {
      // The preview pipeline is already connected. Keeping the default requires no changes.
      if (aiChoice !== 'more-features') {
        const { pipeline } = await httpClient.getPipeline(createdPipelineUuid);
        const config = pipeline.config as unknown as Record<string, unknown>;
        let updatedConfig: Record<string, unknown>;
        if (aiChoice === 'own-model' && ownModelSelection) {
          const model = await httpClient.createProviderLLMModel({
            name: ownModelSelection.model.name,
            provider_uuid: ownModelSelection.providerUuid,
            abilities: ownModelSelection.model.abilities ?? [],
            reasoning_config: { level: 'provider_default' },
            context_length: ownModelSelection.model.context_length ?? null,
            extra_args: {},
          });
          createdModelUuid = model.uuid;
          updatedConfig = configureLocalAgentPrimaryModel(config, model.uuid);
        } else if (aiChoice === 'external' && selectedRunner) {
          const ai = (config.ai ?? {}) as Record<string, unknown>;
          updatedConfig = {
            ...config,
            ai: {
              ...ai,
              runner: {
                ...(ai.runner as Record<string, unknown>),
                id: selectedRunner,
              },
              runner_config: {
                ...(ai.runner_config as Record<string, unknown>),
                [selectedRunner]: runnerConfig,
              },
            },
          };
        } else {
          return;
        }
        await httpClient.updatePipeline(createdPipelineUuid, {
          config: updatedConfig,
        });
        modelBound = true;
      }
      setCurrentStep(3);
      saveProgress({ step: 3, created_pipeline_uuid: createdPipelineUuid });
    } catch (err) {
      if (createdModelUuid && !modelBound) {
        try {
          await httpClient.deleteProviderLLMModel(createdModelUuid);
        } catch (rollbackError) {
          console.warn('Failed to roll back wizard model', rollbackError);
        }
      }
      toast.error(`${t('wizard.createError')}: ${getErrorMessage(err)}`);
    } finally {
      setIsSubmitting(false);
    }
  }, [
    createdBotUuid,
    createdPipelineUuid,
    canProceed,
    aiChoice,
    ownModelSelection,
    selectedRunner,
    runnerConfig,
    saveProgress,
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
        selected_scenario: null,
        selected_adapter: null,
        created_bot_uuid: null,
        created_pipeline_uuid: null,
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
            preparingDefault={preparingDefault}
            defaultPreparationProgress={defaultPreparationProgress}
            botSaved={botSaved}
            pageBotPreviewRequest={pageBotPreviewRequest}
            messageReceived={messageReceived}
            requiresMessageVerification
            onMessageReceived={handleMessageReceived}
            onSaveBot={handleSaveBot}
            webhookUrl={webhookUrl}
            extraWebhookUrl={extraWebhookUrl}
          />
        )}
        {currentStep === 2 && (
          <StepAIEngine
            choice={aiChoice}
            onChoiceChange={setAiChoice}
            onOwnModelSelectionChange={setOwnModelSelection}
            runnerOptions={runnerOptions.filter(
              (runner) => runner.name !== LOCAL_AGENT_RUNNER_ID,
            )}
            marketplaceRunners={marketplaceRunners.filter(
              (plugin) =>
                marketplacePluginId(plugin) !== 'langbot-team/LocalAgent',
            )}
            installedPluginIds={installedPluginIds}
            runnerPluginStatuses={runnerPluginStatuses}
            runnerPluginDescriptions={runnerPluginDescriptions}
            isRunnerCatalogLoading={isRunnerCatalogLoading}
            runnerCatalogError={runnerCatalogError}
            installingRunnerPluginId={installingRunnerPluginId}
            runnerInstallError={runnerInstallError}
            runnerInstallProgress={runnerInstallProgress}
            selected={selectedRunner}
            onSelect={handleSelectRunner}
            onInstall={handleInstallRunner}
            onRetryCatalog={loadRunnerCatalog}
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
            disabled={
              currentStep === 0 || isSavingBot || isSubmitting || isCreatingBot
            }
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
              {aiChoice === 'more-features'
                ? t('wizard.step.done')
                : aiChoice === 'own-model'
                  ? t('wizard.aiEngine.finishWithModel')
                  : t('wizard.finish')}
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
  const [showLegacy, setShowLegacy] = useState(false);

  const messageAdapters = useMemo(
    () =>
      Array.from(
        new Map(adapters.map((adapter) => [adapter.name, adapter])).values(),
      ).filter(adapterSupportsMessages),
    [adapters],
  );
  const activeAdapters = messageAdapters.filter(
    (adapter) => !adapter.spec.legacy,
  );
  const legacyAdapters = messageAdapters.filter(
    (adapter) => adapter.spec.legacy,
  );

  const groupedAdapters = useMemo(() => {
    const withCategories = activeAdapters.map((a) => ({
      ...a,
      categories: a.spec.categories,
    }));
    return groupByCategory(withCategories);
  }, [activeAdapters]);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <section className="space-y-5">
        <div className="text-center">
          <h2 className="text-xl font-semibold">
            {t('wizard.platform.title')}
          </h2>
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
        {legacyAdapters.length > 0 && (
          <div className="border-t pt-4 space-y-3">
            <button
              type="button"
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
              onClick={() => setShowLegacy((v) => !v)}
            >
              {showLegacy ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              {t('bots.legacyAdapters')}
              <span className="rounded bg-muted px-1.5 py-0.5 text-xs">
                {legacyAdapters.length}
              </span>
            </button>
            {showLegacy && (
              <>
                <p className="text-xs text-muted-foreground">
                  {t('bots.legacyAdaptersHint')}
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 opacity-60">
                  {legacyAdapters.map((adapter) => (
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
                          className="w-10 h-10 rounded-lg shrink-0 grayscale"
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
                    </Card>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </section>
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
  openRequest,
}: {
  botUuid: string;
  title?: string;
  testNotice: string;
  openRequest: number;
}) {
  const { t } = useTranslation();
  useEffect(() => {
    const script = document.createElement('script');
    const backendUrl = httpClient.getBaseUrl().replace(/\/$/, '');
    script.src = `${backendUrl}/api/v1/embed/${botUuid}/widget.js?preview=wizard&v=${Date.now()}`;
    script.dataset.title = title || 'LangBot';
    script.dataset.testNotice = testNotice;
    script.dataset.autoOpen = 'true';
    script.onerror = () =>
      toast.error(t('wizard.botConfig.pageBotPreviewFailed'), {
        id: `wizard-page-bot-${botUuid}`,
      });
    document.body.appendChild(script);

    return () => {
      script.onerror = null;
      script.remove();
      const root = document.getElementById('langbot-widget-root') as
        | (HTMLElement & {
            langbotDestroy?: () => void;
            langbotOpen?: () => void;
          })
        | null;
      if (root?.langbotDestroy) {
        root.langbotDestroy();
      } else {
        root?.remove();
      }
    };
  }, [botUuid, testNotice, title, openRequest, t]);

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
  preparingDefault,
  defaultPreparationProgress,
  botSaved,
  pageBotPreviewRequest,
  messageReceived,
  requiresMessageVerification,
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
  preparingDefault: boolean;
  defaultPreparationProgress: number;
  botSaved: boolean;
  pageBotPreviewRequest: number;
  messageReceived: boolean;
  requiresMessageVerification: boolean;
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
          openRequest={pageBotPreviewRequest}
        />
      )}

      <div className="text-center">
        <h2 className="text-xl font-semibold">{t('wizard.botConfig.title')}</h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t('wizard.botConfig.description')}
        </p>
      </div>

      {botSaved && requiresMessageVerification && (
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
                className={cn(
                  'relative w-full shrink-0 overflow-hidden sm:w-auto',
                  preparingDefault && 'disabled:opacity-100',
                )}
                aria-busy={isSavingBot}
                aria-live="polite"
              >
                {preparingDefault && (
                  <span
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-y-0 left-0 bg-white/20 transition-[width] duration-300 motion-reduce:transition-none"
                    style={{ width: `${defaultPreparationProgress}%` }}
                  />
                )}
                <span className="relative flex min-w-0 items-center justify-center gap-2">
                  {isSavingBot && (
                    <Loader2 className="size-4 shrink-0 animate-spin" />
                  )}
                  <span className="truncate">
                    {preparingDefault
                      ? t('wizard.aiEngine.preparingDefault')
                      : botSaved
                        ? t('wizard.botConfig.resaveBot')
                        : t('wizard.botConfig.saveBot')}
                  </span>
                  {preparingDefault && (
                    <span className="shrink-0 tabular-nums">
                      {defaultPreparationProgress}%
                    </span>
                  )}
                </span>
              </Button>
            </CardHeader>
            {adapterConfigItems.length > 0 && (
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
            )}
          </Card>

          {/* Bot saved indicator */}
          {botSaved && !requiresMessageVerification && (
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

const RUNNER_INSTALL_STAGE_LABELS: Record<InstallStage, string> = {
  [InstallStage.CHECKING]: 'plugins.installProgress.checkingUpdate',
  [InstallStage.DOWNLOADING]: 'plugins.installProgress.downloading',
  [InstallStage.VALIDATING]: 'plugins.installProgress.validating',
  [InstallStage.INSTALLING_DEPS]: 'plugins.installProgress.installingDeps',
  [InstallStage.ACTIVATING]: 'plugins.installProgress.activating',
  [InstallStage.DONE]: 'plugins.installProgress.completed',
  [InstallStage.ERROR]: 'plugins.installProgress.failed',
};

function RunnerStatusBadge({ status }: { status?: RunnerPluginStatus }) {
  const { t } = useTranslation();
  if (status !== 'debug') return null;
  return (
    <Badge
      variant="outline"
      className="w-fit shrink-0 border-orange-400 text-xs font-normal text-orange-400"
    >
      <Bug className="size-3" />
      {t('plugins.debugging')}
    </Badge>
  );
}

function runnerPluginId(runner: string) {
  return runner
    .replace(/^plugin:/, '')
    .split('/')
    .slice(0, 2)
    .join('/');
}

function StepAIEngine({
  choice,
  onChoiceChange,
  onOwnModelSelectionChange,
  runnerOptions,
  marketplaceRunners,
  installedPluginIds,
  runnerPluginStatuses,
  runnerPluginDescriptions,
  isRunnerCatalogLoading,
  runnerCatalogError,
  installingRunnerPluginId,
  runnerInstallError,
  runnerInstallProgress,
  selected,
  onSelect,
  onInstall,
  onRetryCatalog,
  runnerConfigItems,
  runnerConfigValues,
  onRunnerConfigChange,
}: {
  choice: AIChoice;
  onChoiceChange: (choice: AIChoice) => void;
  onOwnModelSelectionChange: (selection: OwnModelSelection | null) => void;
  runnerOptions: { name: string; label: { en_US: string; zh_Hans: string } }[];
  marketplaceRunners: PluginV4[];
  installedPluginIds: string[];
  runnerPluginStatuses: Record<string, RunnerPluginStatus>;
  runnerPluginDescriptions: Record<string, I18nObject>;
  isRunnerCatalogLoading: boolean;
  runnerCatalogError: boolean;
  installingRunnerPluginId: string | null;
  runnerInstallError: string | null;
  runnerInstallProgress: Record<string, RunnerInstallProgress>;
  selected: string | null;
  onSelect: (name: string | null) => void;
  onInstall: (plugin: PluginV4) => void;
  onRetryCatalog: () => void;
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
    const r = runnerOptions.find((o) => o.name === selected);
    return r ? extractI18nObject(r.label) : (selected ?? '');
  }, [runnerOptions, selected]);

  const marketplaceRunnerIds = useMemo(
    () => new Set(marketplaceRunners.map(marketplacePluginId)),
    [marketplaceRunners],
  );
  const standaloneRunnerOptions = useMemo(
    () =>
      runnerOptions.filter((option) => {
        if (!option.name.startsWith('plugin:')) return true;
        const pluginId = option.name.slice('plugin:'.length).split('/');
        return !marketplaceRunnerIds.has(`${pluginId[0]}/${pluginId[1]}`);
      }),
    [marketplaceRunnerIds, runnerOptions],
  );

  const orderedRunnerEntries = useMemo(() => {
    const installedIds = new Set([
      ...installedPluginIds,
      ...Object.keys(runnerPluginStatuses),
      ...runnerOptions.map((option) => runnerPluginId(option.name)),
    ]);
    const entries: (
      | { kind: 'marketplace'; plugin: PluginV4; installed: boolean }
      | {
          kind: 'local';
          option: (typeof runnerOptions)[number];
          installed: boolean;
        }
    )[] = [
      ...marketplaceRunners.map((plugin) => ({
        kind: 'marketplace' as const,
        plugin,
        installed: installedIds.has(marketplacePluginId(plugin)),
      })),
      ...standaloneRunnerOptions.map((option) => ({
        kind: 'local' as const,
        option,
        installed: true,
      })),
    ];
    return entries.sort((a, b) => Number(b.installed) - Number(a.installed));
  }, [
    marketplaceRunners,
    standaloneRunnerOptions,
    installedPluginIds,
    runnerPluginStatuses,
    runnerOptions,
  ]);

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
        <ToggleGroup
          type="single"
          value={choice}
          onValueChange={(value) => {
            if (value) onChoiceChange(value as AIChoice);
          }}
          aria-label={t('wizard.aiEngine.title')}
          variant="outline"
          spacing={3}
          className="grid w-full grid-cols-1 items-stretch gap-3 md:grid-cols-3"
        >
          {choices.map((item) => {
            const Icon = item.icon;
            return (
              <ToggleGroupItem
                key={item.id}
                value={item.id}
                aria-label={item.title}
                className="h-auto min-h-28 w-full items-start justify-start gap-3 rounded-lg border px-4 py-4 text-left whitespace-normal shadow-none hover:bg-muted/40 data-[state=on]:border-[#2288ee]/50 data-[state=on]:bg-blue-50/60 data-[state=on]:text-foreground data-[state=on]:shadow-none dark:data-[state=on]:border-blue-500/50 dark:data-[state=on]:bg-blue-500/10"
              >
                <span className="flex size-9 shrink-0 items-center justify-center rounded-md border bg-background text-[#2288ee] shadow-xs">
                  <Icon className="size-4" />
                </span>
                <span className="min-w-0 space-y-1.5">
                  <span className="block text-sm font-medium text-foreground">
                    {item.title}
                  </span>
                  <span className="block text-sm font-normal leading-relaxed text-muted-foreground">
                    {item.description}
                  </span>
                </span>
              </ToggleGroupItem>
            );
          })}
        </ToggleGroup>
      </div>
    );
  }

  // The catalog is shared by the picker and the configuration sidebar.
  const runnerCatalog = (
    <div className="space-y-4">
      {runnerCatalogError && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-4">
          <div className="flex items-start gap-3">
            <CircleAlert className="mt-0.5 size-5 shrink-0 text-destructive" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">
                {t('wizard.aiEngine.catalogUnavailable')}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {t('wizard.aiEngine.catalogUnavailableDescription')}
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={onRetryCatalog}
              >
                <RefreshCw className="size-4" />
                {t('common.retry')}
              </Button>
            </div>
          </div>
        </div>
      )}

      {runnerInstallError && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {runnerInstallError}
        </div>
      )}

      {isRunnerCatalogLoading && marketplaceRunners.length === 0 && (
        <div className="flex min-h-32 items-center justify-center rounded-md border border-dashed">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            {t('wizard.aiEngine.loadingCatalog')}
          </div>
        </div>
      )}

      <div
        className={cn(
          'grid grid-cols-1 gap-4',
          !selected && 'sm:grid-cols-2 lg:grid-cols-3',
        )}
      >
        {orderedRunnerEntries.map((entry) => {
          if (entry.kind === 'marketplace') {
            const plugin = entry.plugin;
            const pluginId = marketplacePluginId(plugin);
            const prefix = runnerPluginPrefix(plugin);
            const registeredOptions = runnerOptions.filter((option) =>
              option.name.startsWith(prefix),
            );
            const preferredOption =
              registeredOptions.find((option) =>
                option.name.endsWith('/default'),
              ) ?? registeredOptions[0];
            const isSelected = registeredOptions.some(
              (option) => option.name === selected,
            );
            const isInstalled = installedPluginIds.includes(pluginId);
            const isInstalling = installingRunnerPluginId === pluginId;
            const progress = runnerInstallProgress[pluginId];
            const progressLabel = progress
              ? t(RUNNER_INSTALL_STAGE_LABELS[progress.stage])
              : t('wizard.aiEngine.installing');
            const iconUrl =
              getCloudServiceClientSync().resolveMarketplaceIconURL(
                plugin.type,
                plugin.author,
                plugin.name,
                plugin.icon,
              );

            return (
              <Card
                key={pluginId}
                className={cn(
                  'flex flex-col gap-3 py-4 shadow-none',
                  !selected && 'min-h-52',
                  isSelected &&
                    'border-[#2288ee]/50 bg-blue-50/60 dark:border-blue-500/50 dark:bg-blue-500/10',
                )}
              >
                <CardHeader className="flex flex-row items-start gap-3 px-4">
                  <img
                    src={iconUrl}
                    alt=""
                    className="size-10 shrink-0 rounded-md border bg-muted object-cover"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <CardTitle className="text-base">
                        {extractI18nObject(plugin.label) || plugin.name}
                      </CardTitle>
                      <RunnerStatusBadge
                        status={runnerPluginStatuses[pluginId]}
                      />
                    </div>
                    <CardDescription className="mt-1 break-all text-xs">
                      {plugin.author}/{plugin.name}
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col px-4">
                  <p className="line-clamp-3 text-sm text-muted-foreground">
                    {extractI18nObject(plugin.description)}
                  </p>
                  <div className="mt-auto pt-4">
                    {preferredOption ? (
                      <Button
                        type="button"
                        className="w-full"
                        variant={isSelected ? 'secondary' : 'outline'}
                        aria-pressed={isSelected}
                        onClick={() => {
                          if (!isSelected) onSelect(preferredOption.name);
                        }}
                      >
                        <Check className="size-4" />
                        {t('wizard.aiEngine.useInstalled')}
                      </Button>
                    ) : isInstalled ? (
                      <Button
                        type="button"
                        variant="outline"
                        disabled
                        className="w-full"
                      >
                        <CircleAlert className="size-4" />
                        {t('wizard.aiEngine.installedUnavailable')}
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        className={cn(
                          'relative w-full overflow-hidden',
                          isInstalling && 'disabled:opacity-100',
                        )}
                        disabled={installingRunnerPluginId !== null}
                        aria-busy={isInstalling}
                        aria-live="polite"
                        title={isInstalling ? progressLabel : undefined}
                        onClick={() => onInstall(plugin)}
                      >
                        {isInstalling && (
                          <span
                            aria-hidden="true"
                            className="pointer-events-none absolute inset-y-0 left-0 bg-white/20 transition-[width] duration-300 motion-reduce:transition-none"
                            style={{ width: `${progress?.percent ?? 0}%` }}
                          />
                        )}
                        <span className="relative flex min-w-0 items-center justify-center gap-2">
                          {isInstalling ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <Download className="size-4" />
                          )}
                          <span className="truncate">
                            {isInstalling
                              ? progressLabel
                              : progress?.stage === InstallStage.ERROR
                                ? `${t('plugins.installProgress.failed')} · ${t('common.retry')}`
                                : t('wizard.aiEngine.installAndContinue')}
                          </span>
                          {isInstalling && (
                            <span className="shrink-0 tabular-nums">
                              {progress?.percent ?? 0}%
                            </span>
                          )}
                        </span>
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          }
          const opt = entry.option;
          const pluginId = runnerPluginId(opt.name);
          const [author, name] = pluginId.split('/');
          const description = runnerPluginDescriptions[pluginId];
          const isSelected = selected === opt.name;
          return (
            <Card
              key={opt.name}
              className={cn(
                'flex flex-col gap-3 py-4 shadow-none',
                !selected && 'min-h-52',
                isSelected &&
                  'border-[#2288ee]/50 bg-blue-50/60 dark:border-blue-500/50 dark:bg-blue-500/10',
              )}
            >
              <CardHeader className="flex flex-row items-start gap-3 px-4">
                {author && name ? (
                  <img
                    src={httpClient.getPluginIconURL(author, name)}
                    alt=""
                    className="size-10 shrink-0 rounded-md border bg-muted object-cover"
                  />
                ) : (
                  <Blocks className="size-10 shrink-0 rounded-md border bg-muted p-2 text-muted-foreground" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <CardTitle className="text-base">
                      {extractI18nObject(opt.label)}
                    </CardTitle>
                    <RunnerStatusBadge
                      status={runnerPluginStatuses[pluginId]}
                    />
                  </div>
                  <CardDescription className="mt-1 break-all text-xs">
                    {pluginId}
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col px-4">
                {description && (
                  <p className="line-clamp-3 text-sm text-muted-foreground">
                    {extractI18nObject(description)}
                  </p>
                )}
                <div className="mt-auto pt-4">
                  <Button
                    type="button"
                    className="w-full"
                    variant={isSelected ? 'secondary' : 'outline'}
                    aria-pressed={isSelected}
                    onClick={() => {
                      if (!isSelected) onSelect(opt.name);
                    }}
                  >
                    <Check className="size-4" />
                    {t('wizard.aiEngine.useInstalled')}
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {!isRunnerCatalogLoading &&
        marketplaceRunners.length === 0 &&
        standaloneRunnerOptions.length === 0 &&
        !runnerCatalogError && (
          <div className="rounded-md border border-dashed p-6 text-center">
            <p className="font-medium">
              {t('wizard.aiEngine.noMarketplaceRunners')}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {t('wizard.aiEngine.noMarketplaceRunnersDescription')}
            </p>
          </div>
        )}

      <div className="flex justify-center">
        <Button variant="outline" size="sm" asChild>
          <a
            href="https://space.langbot.app/market?type=plugin&component=Runner"
            target="_blank"
            rel="noopener noreferrer"
          >
            {t('wizard.aiEngine.browseRunners')}
            <ExternalLink className="size-4" />
          </a>
        </Button>
      </div>
    </div>
  );

  return (
    <div
      key={selected ? 'ai-engine-external-config' : 'ai-engine-external-picker'}
      className="mx-auto flex w-full max-w-4xl flex-col gap-6 animate-in fade-in-0 slide-in-from-right-4 duration-300 ease-out motion-reduce:animate-none lg:min-h-0 lg:flex-1"
    >
      <div className="shrink-0 text-center">
        <h2 className="text-xl font-semibold">
          {t('wizard.aiEngine.externalTitle')}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {t(
            selected
              ? 'wizard.aiEngine.description'
              : 'wizard.aiEngine.runnerDescription',
          )}
        </p>
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="shrink-0 self-start"
        onClick={() => {
          if (selected) onSelect(null);
          else onChoiceChange('more-features');
        }}
      >
        <ArrowLeft className="size-4 mr-1.5" />
        {t(
          selected
            ? 'wizard.aiEngine.backToList'
            : 'wizard.aiEngine.backToChoices',
        )}
      </Button>
      {selected ? (
        <div className="flex min-h-0 flex-col gap-6 lg:flex-1 lg:flex-row">
          <div className="w-full shrink-0 lg:w-[300px] lg:overflow-y-auto lg:pr-2">
            {runnerCatalog}
          </div>
          <div className="min-w-0 flex-1 lg:overflow-y-auto lg:pr-2">
            {runnerConfigItems.length > 0 && (
              <Card
                key={selected}
                className="animate-in fade-in-0 slide-in-from-right-2 duration-300 motion-reduce:animate-none"
              >
                <CardHeader>
                  <CardTitle>
                    {t('wizard.config.aiConfig', { engine: runnerLabel })}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <DynamicFormComponent
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
      ) : (
        runnerCatalog
      )}
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
        selected_scenario: null,
        selected_adapter: null,
        created_bot_uuid: null,
        created_pipeline_uuid: null,
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
