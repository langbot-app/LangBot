import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { UUID } from 'uuidjs';
import { toast } from 'sonner';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronRight,
  Sparkles,
  PartyPopper,
  Loader2,
  MessageSquare,
  ShieldCheck,
  UserMinus,
  UserPlus,
  X,
  ExternalLink,
  Download,
  RefreshCw,
  CircleAlert,
} from 'lucide-react';

import { httpClient } from '@/app/infra/http/HttpClient';
import {
  userInfo,
  systemInfo,
  initializeUserInfo,
  initializeSystemInfo,
  getCloudServiceClient,
  getCloudServiceClientSync,
} from '@/app/infra/http';
import {
  Adapter,
  Bot,
  Pipeline,
  WizardProgress,
} from '@/app/infra/entities/api';
import {
  DynamicFormItemType,
  IDynamicFormItemSchema,
} from '@/app/infra/entities/form/dynamic';
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

import { Button } from '@/components/ui/button';
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
const RUNNER_COMPONENT_FILTER = 'AgentRunner';
const RUNNER_CATALOG_PAGE_SIZE = 100;
const RUNNER_INSTALL_TIMEOUT_MS = 120_000;
const RUNNER_REGISTRATION_TIMEOUT_MS = 60_000;

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object') {
    const value = error as { msg?: string; message?: string };
    return value.msg || value.message || '';
  }
  return typeof error === 'string' ? error : '';
}

function marketplacePluginId(plugin: Pick<PluginV4, 'author' | 'name'>) {
  return `${plugin.author}/${plugin.name}`;
}

function runnerPluginPrefix(plugin: Pick<PluginV4, 'author' | 'name'>) {
  return `plugin:${plugin.author}/${plugin.name}/`;
}

type WizardScenarioId =
  | 'message_reply'
  | 'welcome_members'
  | 'handle_departures'
  | 'handle_moderation';

const WIZARD_SCENARIO_PROMPT_KEYS: Partial<Record<WizardScenarioId, string>> = {
  welcome_members: 'wizard.scenario.welcomeMembersPrompt',
  handle_departures: 'wizard.scenario.handleDeparturesPrompt',
  handle_moderation: 'wizard.scenario.handleModerationPrompt',
};

const WIZARD_SCENARIOS = [
  {
    id: 'message_reply' as const,
    eventType: 'message.received',
    processorKind: 'pipeline' as const,
    labelKey: 'wizard.scenario.messageReply',
    descriptionKey: 'wizard.scenario.messageReplyDescription',
    icon: MessageSquare,
    emoji: '💬',
  },
  {
    id: 'welcome_members' as const,
    eventType: 'group.member_joined',
    processorKind: 'agent' as const,
    labelKey: 'wizard.scenario.welcomeMembers',
    descriptionKey: 'wizard.scenario.welcomeMembersDescription',
    icon: UserPlus,
    emoji: '👋',
  },
  {
    id: 'handle_departures' as const,
    eventType: 'group.member_left',
    processorKind: 'agent' as const,
    labelKey: 'wizard.scenario.handleDepartures',
    descriptionKey: 'wizard.scenario.handleDeparturesDescription',
    icon: UserMinus,
    emoji: '👤',
  },
  {
    id: 'handle_moderation' as const,
    eventType: 'group.member_banned',
    processorKind: 'agent' as const,
    labelKey: 'wizard.scenario.handleModeration',
    descriptionKey: 'wizard.scenario.handleModerationDescription',
    icon: ShieldCheck,
    emoji: '🛡️',
  },
];

function adapterSupportsScenario(
  adapter: Adapter,
  scenarioId: WizardScenarioId,
) {
  const scenario = WIZARD_SCENARIOS.find((item) => item.id === scenarioId);
  if (!scenario) return false;
  const supportedEvents = adapter.spec.supported_events?.length
    ? adapter.spec.supported_events
    : ['message.received'];
  return supportedEvents.includes(scenario.eventType);
}

// ---------------------------------------------------------------------------
// Main Wizard Page (full-screen, no sidebar)
// ---------------------------------------------------------------------------

export default function WizardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  // ---- Wizard state ----
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedScenario, setSelectedScenario] =
    useState<WizardScenarioId | null>(null);
  const [selectedAdapter, setSelectedAdapter] = useState<string | null>(null);
  const [selectedRunner, setSelectedRunner] = useState<string | null>(null);
  const [botName, setBotName] = useState('');
  const [botDescription, _setBotDescription] = useState('');
  const [adapterConfig, setAdapterConfig] = useState<Record<string, unknown>>(
    {},
  );
  const [runnerConfig, setRunnerConfig] = useState<Record<string, unknown>>({});
  const [createdBotUuid, setCreatedBotUuid] = useState<string | null>(null);
  const [webhookUrl, setWebhookUrl] = useState<string>('');
  const [extraWebhookUrl, setExtraWebhookUrl] = useState<string>('');

  // ---- Remote data ----
  const [adapters, setAdapters] = useState<Adapter[]>([]);
  const [aiConfigTab, setAiConfigTab] = useState<PipelineConfigTab | null>(
    null,
  );
  const [marketplaceRunners, setMarketplaceRunners] = useState<PluginV4[]>([]);
  const [installedPluginIds, setInstalledPluginIds] = useState<string[]>([]);
  const [isRunnerCatalogLoading, setIsRunnerCatalogLoading] = useState(true);
  const [runnerCatalogError, setRunnerCatalogError] = useState(false);
  const [installingRunnerPluginId, setInstallingRunnerPluginId] = useState<
    string | null
  >(null);
  const [runnerInstallError, setRunnerInstallError] = useState<string | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isCreatingBot, setIsCreatingBot] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSavingBot, setIsSavingBot] = useState(false);
  const [botSaved, setBotSaved] = useState(false);

  const loadRunnerCatalog = useCallback(async () => {
    setIsRunnerCatalogLoading(true);
    setRunnerCatalogError(false);
    try {
      const cloudClient = await getCloudServiceClient();
      const [firstSearchResult, recommendationResult, installedResult] =
        await Promise.all([
          cloudClient.searchMarketplaceExtensions({
            query: '',
            page: 1,
            page_size: RUNNER_CATALOG_PAGE_SIZE,
            type_filter: 'plugin',
            component_filter: RUNNER_COMPONENT_FILTER,
          }),
          cloudClient.getRecommendationLists().catch(() => ({ lists: [] })),
          httpClient.getPlugins().catch(() => ({ plugins: [] })),
        ]);

      const remainingPageCount = Math.max(
        0,
        Math.ceil((firstSearchResult.total || 0) / RUNNER_CATALOG_PAGE_SIZE) -
          1,
      );
      const remainingResults = await Promise.all(
        Array.from({ length: remainingPageCount }, (_, index) =>
          cloudClient.searchMarketplaceExtensions({
            query: '',
            page: index + 2,
            page_size: RUNNER_CATALOG_PAGE_SIZE,
            type_filter: 'plugin',
            component_filter: RUNNER_COMPONENT_FILTER,
          }),
        ),
      );
      const catalogPlugins = [
        ...(firstSearchResult.plugins || []),
        ...remainingResults.flatMap((result) => result.plugins || []),
      ];

      const recommendationOrder = new Map<string, number>();
      let nextOrder = 0;
      for (const list of recommendationResult.lists || []) {
        for (const plugin of list.plugins || []) {
          if (!plugin.components?.[RUNNER_COMPONENT_FILTER]) continue;
          const id = marketplacePluginId(plugin);
          if (!recommendationOrder.has(id)) {
            recommendationOrder.set(id, nextOrder);
            nextOrder += 1;
          }
        }
      }

      const runners = catalogPlugins
        .filter((plugin) => plugin.components?.[RUNNER_COMPONENT_FILTER])
        .sort((left, right) => {
          const leftOrder = recommendationOrder.get(marketplacePluginId(left));
          const rightOrder = recommendationOrder.get(
            marketplacePluginId(right),
          );
          if (leftOrder !== undefined && rightOrder !== undefined) {
            return leftOrder - rightOrder;
          }
          if (leftOrder !== undefined) return -1;
          if (rightOrder !== undefined) return 1;
          return right.install_count - left.install_count;
        });

      setMarketplaceRunners(runners);
      setInstalledPluginIds(
        installedResult.plugins.map((plugin) => {
          const metadata = plugin.manifest.manifest.metadata;
          return `${metadata.author ?? ''}/${metadata.name}`;
        }),
      );
    } catch (error) {
      console.error('Failed to load AgentRunner catalog', error);
      setRunnerCatalogError(true);
    } finally {
      setIsRunnerCatalogLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRunnerCatalog();
  }, [loadRunnerCatalog]);

  // ---- Helper: persist wizard progress to backend (fire-and-forget) ----
  const saveProgress = useCallback(
    (overrides: Partial<WizardProgress> = {}) => {
      const progress: WizardProgress = {
        step: overrides.step ?? currentStep,
        selected_scenario:
          overrides.selected_scenario !== undefined
            ? overrides.selected_scenario
            : selectedScenario,
        selected_adapter:
          overrides.selected_adapter !== undefined
            ? overrides.selected_adapter
            : selectedAdapter,
        created_bot_uuid:
          overrides.created_bot_uuid !== undefined
            ? overrides.created_bot_uuid
            : createdBotUuid,
        bot_saved: overrides.bot_saved ?? botSaved,
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
      selectedScenario,
      selectedAdapter,
      createdBotUuid,
      botSaved,
      selectedRunner,
    ],
  );

  // ---- Fetch remote data & restore progress ----
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Initialize user/system info (wizard is outside /home layout)
        await Promise.all([initializeUserInfo(), initializeSystemInfo()]);

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
            setSelectedScenario(
              (progress.selected_scenario as WizardScenarioId | null) ??
                'message_reply',
            );
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

            // Step 3 is resumable so a refresh cannot create a duplicate processor.
            setCurrentStep(Math.min(progress.step, 3));
          } catch {
            // Bot no longer exists — clear stale progress and start fresh
            httpClient
              .saveWizardProgress({
                step: 0,
                selected_scenario: null,
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
  }, [t]);

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

  const selectedScenarioDefinition = useMemo(
    () => WIZARD_SCENARIOS.find((item) => item.id === selectedScenario),
    [selectedScenario],
  );

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
    (runner: string, configTab: PipelineConfigTab | null = aiConfigTab) => {
      setSelectedRunner(runner);
      const configStage = configTab?.stages.find((s) => s.name === runner);
      const defaults = configStage ? getDefaultValues(configStage.config) : {};
      const promptKey = selectedScenario
        ? WIZARD_SCENARIO_PROMPT_KEYS[selectedScenario]
        : undefined;
      const supportsPromptEditor = configStage?.config.some(
        (item) => item.type === DynamicFormItemType.PROMPT_EDITOR,
      );
      if (promptKey && supportsPromptEditor) {
        defaults.prompt = [{ role: 'system', content: t(promptKey) }];
      }
      setRunnerConfig(defaults);
      saveProgress({ step: 2, selected_runner: runner });
    },
    [aiConfigTab, saveProgress, selectedScenario, t],
  );

  const handleInstallRunner = useCallback(
    async (plugin: PluginV4) => {
      const pluginId = marketplacePluginId(plugin);
      setInstallingRunnerPluginId(pluginId);
      setRunnerInstallError(null);

      try {
        if (!plugin.latest_version) {
          throw new Error(t('wizard.aiEngine.versionUnavailable'));
        }

        const { task_id: taskId } =
          await httpClient.installPluginFromMarketplace(
            plugin.author,
            plugin.name,
            plugin.latest_version,
          );
        const installDeadline = Date.now() + RUNNER_INSTALL_TIMEOUT_MS;
        let installCompleted = false;
        while (Date.now() < installDeadline) {
          const task = await httpClient.getAsyncTask(taskId);
          if (task.runtime.done) {
            if (task.runtime.exception) {
              throw new Error(task.runtime.exception);
            }
            installCompleted = true;
            break;
          }
          await wait(1000);
        }
        if (!installCompleted) {
          throw new Error(t('wizard.aiEngine.installTimeout'));
        }

        const registrationDeadline =
          Date.now() + RUNNER_REGISTRATION_TIMEOUT_MS;
        const prefix = runnerPluginPrefix(plugin);
        while (Date.now() < registrationDeadline) {
          const metadata = await httpClient.getGeneralPipelineMetadata();
          const nextAiTab =
            metadata.configs.find((config) => config.name === 'ai') ?? null;
          const nextRunnerStage = nextAiTab?.stages.find(
            (stage) => stage.name === 'runner',
          );
          const nextRunnerOptions =
            nextRunnerStage?.config.find((item) => item.name === 'id')
              ?.options ?? [];
          const pluginRunnerOptions = nextRunnerOptions.filter((option) =>
            option.name.startsWith(prefix),
          );
          const preferredRunner =
            pluginRunnerOptions.find((option) =>
              option.name.endsWith('/default'),
            ) ?? pluginRunnerOptions[0];

          if (nextAiTab && preferredRunner) {
            setAiConfigTab(nextAiTab);
            setInstalledPluginIds((current) =>
              current.includes(pluginId) ? current : [...current, pluginId],
            );
            handleSelectRunner(preferredRunner.name, nextAiTab);
            toast.success(
              t('wizard.aiEngine.installSuccess', {
                runner: extractI18nObject(plugin.label),
              }),
            );
            return;
          }
          await wait(1000);
        }

        throw new Error(t('wizard.aiEngine.registrationTimeout'));
      } catch (error) {
        const message =
          getErrorMessage(error) || t('wizard.aiEngine.installFailed');
        setRunnerInstallError(message);
        toast.error(message);
      } finally {
        setInstallingRunnerPluginId(null);
      }
    },
    [handleSelectRunner, t],
  );

  // ---- Navigation helpers ----

  const canProceed = useCallback((): boolean => {
    switch (currentStep) {
      case 0:
        return selectedScenario !== null && selectedAdapter !== null;
      case 1:
        return createdBotUuid !== null && botSaved;
      case 2:
        return selectedRunner !== null;
      default:
        return false;
    }
  }, [
    currentStep,
    selectedScenario,
    selectedAdapter,
    createdBotUuid,
    botSaved,
    selectedRunner,
  ]);

  const handleSelectScenario = useCallback(
    (scenarioId: WizardScenarioId) => {
      const adapter = adapters.find((item) => item.name === selectedAdapter);
      const nextAdapter =
        adapter && adapterSupportsScenario(adapter, scenarioId)
          ? selectedAdapter
          : null;
      setSelectedScenario(scenarioId);
      setSelectedAdapter(nextAdapter);
      saveProgress({
        step: 0,
        selected_scenario: scenarioId,
        selected_adapter: nextAdapter,
      });
    },
    [adapters, selectedAdapter, saveProgress],
  );

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
        selected_scenario: selectedScenario,
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
  }, [selectedScenario, selectedAdapter, adapters, t, saveProgress]);

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
    if (!selectedRunner || !createdBotUuid || !selectedScenarioDefinition)
      return;
    setIsSubmitting(true);
    let processorUuid = '';

    try {
      let targetType: 'agent' | 'pipeline';

      if (selectedScenarioDefinition.processorKind === 'pipeline') {
        const pipeline: Pipeline = {
          name: `${botName} Pipeline`,
          description: botDescription || '',
          config: {},
        };
        const pipelineResp = await httpClient.createPipeline(pipeline);
        processorUuid = pipelineResp.uuid;
        const createdPipeline = await httpClient.getPipeline(pipelineResp.uuid);
        const fullConfig = createdPipeline.pipeline.config as unknown as Record<
          string,
          unknown
        >;
        const fullAiConfig =
          fullConfig.ai && typeof fullConfig.ai === 'object'
            ? (fullConfig.ai as Record<string, unknown>)
            : {};
        const existingRunner =
          fullAiConfig.runner && typeof fullAiConfig.runner === 'object'
            ? (fullAiConfig.runner as Record<string, unknown>)
            : {};
        const existingRunnerConfigs =
          fullAiConfig.runner_config &&
          typeof fullAiConfig.runner_config === 'object'
            ? (fullAiConfig.runner_config as Record<string, unknown>)
            : {};

        await httpClient.updatePipeline(pipelineResp.uuid, {
          name: `${botName} Pipeline`,
          description: botDescription || '',
          config: {
            ...fullConfig,
            ai: {
              ...fullAiConfig,
              runner: { ...existingRunner, id: selectedRunner },
              runner_config: {
                ...existingRunnerConfigs,
                [selectedRunner]: runnerConfig,
              },
            },
          },
        });
        targetType = 'pipeline';
      } else {
        const agentResp = await httpClient.createAgent({
          kind: 'agent',
          name: `${botName} - ${t(selectedScenarioDefinition.labelKey)}`,
          description: botDescription || '',
          emoji: selectedScenarioDefinition.emoji,
          component_ref: selectedRunner,
          config: {
            runner: { id: selectedRunner, 'expire-time': 0 },
            runner_config: { [selectedRunner]: runnerConfig },
          },
          enabled: true,
          supported_event_patterns: [selectedScenarioDefinition.eventType],
        });
        processorUuid = agentResp.uuid;
        targetType = 'agent';
      }

      const botData = await httpClient.getBot(createdBotUuid);
      const existingBot = botData.bot;
      await httpClient.updateBot(createdBotUuid, {
        name: existingBot.name,
        description: existingBot.description,
        adapter: existingBot.adapter,
        adapter_config: existingBot.adapter_config,
        enable: existingBot.enable,
        event_bindings: [
          {
            event_pattern: selectedScenarioDefinition.eventType,
            target_type: targetType,
            target_uuid: processorUuid,
            filters: [],
            priority: 0,
            enabled: true,
            description: '',
          },
        ],
      });

      setCurrentStep(3);
      saveProgress({ step: 3 });
    } catch (err) {
      if (processorUuid) {
        try {
          await httpClient.deleteAgent(processorUuid);
        } catch (rollbackError) {
          console.warn('Failed to roll back wizard processor', rollbackError);
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
    createdBotUuid,
    selectedScenarioDefinition,
    botName,
    botDescription,
    runnerConfig,
    t,
    saveProgress,
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
        selected_scenario: null,
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
    t('wizard.step.scenarioChannel'),
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
            selectedScenario={selectedScenario}
            onSelectScenario={handleSelectScenario}
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
            marketplaceRunners={marketplaceRunners}
            installedPluginIds={installedPluginIds}
            isRunnerCatalogLoading={isRunnerCatalogLoading}
            runnerCatalogError={runnerCatalogError}
            installingRunnerPluginId={installingRunnerPluginId}
            runnerInstallError={runnerInstallError}
            selected={selectedRunner}
            onSelect={handleSelectRunner}
            onInstall={handleInstallRunner}
            onRetryCatalog={loadRunnerCatalog}
            isLocalAccount={isLocalAccount}
            onSpaceAuth={handleSpaceAuth}
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
  selectedScenario,
  onSelectScenario,
  selected,
  onSelect,
}: {
  adapters: Adapter[];
  selectedScenario: WizardScenarioId | null;
  onSelectScenario: (scenarioId: WizardScenarioId) => void;
  selected: string | null;
  onSelect: (name: string) => void;
}) {
  const { t } = useTranslation();
  const [showLegacy, setShowLegacy] = useState(false);

  const activeAdapters = useMemo(
    () =>
      selectedScenario
        ? adapters.filter(
            (adapter) =>
              !adapter.spec.legacy &&
              adapterSupportsScenario(adapter, selectedScenario),
          )
        : [],
    [adapters, selectedScenario],
  );
  const legacyAdapters = useMemo(
    () =>
      selectedScenario
        ? adapters.filter(
            (adapter) =>
              adapter.spec.legacy &&
              adapterSupportsScenario(adapter, selectedScenario),
          )
        : [],
    [adapters, selectedScenario],
  );

  const groupedAdapters = useMemo(() => {
    const withCategories = activeAdapters.map((a) => ({
      ...a,
      categories: a.spec.categories,
    }));
    return groupByCategory(withCategories);
  }, [activeAdapters]);

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <section className="space-y-3">
        <div>
          <h2 className="text-xl font-semibold">
            {t('wizard.scenario.title')}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {t('wizard.scenario.description')}
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {WIZARD_SCENARIOS.map((scenario) => {
            const Icon = scenario.icon;
            const isSelected = selectedScenario === scenario.id;
            return (
              <button
                key={scenario.id}
                type="button"
                onClick={() => onSelectScenario(scenario.id)}
                className={cn(
                  'rounded-md border bg-card p-3 text-left transition-colors',
                  isSelected
                    ? 'border-primary ring-2 ring-primary/20'
                    : 'hover:border-primary/60',
                )}
              >
                <div className="flex items-start gap-3">
                  <span
                    className={cn(
                      'flex h-8 w-8 shrink-0 items-center justify-center rounded-md',
                      isSelected
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground',
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-medium">
                        {t(scenario.labelKey)}
                      </span>
                      <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        {t(
                          scenario.processorKind === 'pipeline'
                            ? 'wizard.scenario.pipelineBadge'
                            : 'wizard.scenario.agentBadge',
                        )}
                      </span>
                    </span>
                    <span className="mt-1 block text-sm leading-snug text-muted-foreground">
                      {t(scenario.descriptionKey)}
                    </span>
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      <section className="space-y-5 border-t pt-6">
        <div className="text-center">
          <h2 className="text-xl font-semibold">
            {t('wizard.platform.title')}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t('wizard.platform.description')}
          </p>
        </div>
        {!selectedScenario && (
          <div className="rounded-md border border-dashed p-5 text-center text-sm text-muted-foreground">
            {t('wizard.platform.chooseScenarioFirst')}
          </div>
        )}
        {selectedScenario &&
          activeAdapters.length === 0 &&
          legacyAdapters.length === 0 && (
            <div className="rounded-md border border-dashed p-5 text-center text-sm text-muted-foreground">
              {t('wizard.platform.noCompatiblePlatforms')}
            </div>
          )}
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
// Step 2: Select & Configure AI Engine
// ---------------------------------------------------------------------------

function StepAIEngine({
  runnerOptions,
  marketplaceRunners,
  installedPluginIds,
  isRunnerCatalogLoading,
  runnerCatalogError,
  installingRunnerPluginId,
  runnerInstallError,
  selected,
  onSelect,
  onInstall,
  onRetryCatalog,
  isLocalAccount,
  onSpaceAuth,
  runnerConfigItems,
  runnerConfigValues,
  onRunnerConfigChange,
}: {
  runnerOptions: { name: string; label: { en_US: string; zh_Hans: string } }[];
  marketplaceRunners: PluginV4[];
  installedPluginIds: string[];
  isRunnerCatalogLoading: boolean;
  runnerCatalogError: boolean;
  installingRunnerPluginId: string | null;
  runnerInstallError: string | null;
  selected: string | null;
  onSelect: (name: string) => void;
  onInstall: (plugin: PluginV4) => void;
  onRetryCatalog: () => void;
  isLocalAccount: boolean;
  onSpaceAuth: () => void;
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

  // Before any runner is selected: centered grid layout
  if (!selected) {
    return (
      <div className="space-y-6 max-w-4xl mx-auto">
        <div className="text-center">
          <h2 className="text-xl font-semibold">
            {t('wizard.aiEngine.title')}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t('wizard.aiEngine.description')}
          </p>
        </div>
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

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {marketplaceRunners.map((plugin) => {
            const pluginId = marketplacePluginId(plugin);
            const prefix = runnerPluginPrefix(plugin);
            const registeredOptions = runnerOptions.filter((option) =>
              option.name.startsWith(prefix),
            );
            const preferredOption =
              registeredOptions.find((option) =>
                option.name.endsWith('/default'),
              ) ?? registeredOptions[0];
            const isInstalled = installedPluginIds.includes(pluginId);
            const isInstalling = installingRunnerPluginId === pluginId;
            const iconUrl =
              getCloudServiceClientSync().resolveMarketplaceIconURL(
                plugin.type,
                plugin.author,
                plugin.name,
                plugin.icon,
              );

            return (
              <Card key={pluginId} className="flex min-h-52 flex-col">
                <CardHeader className="flex flex-row items-start gap-3 pb-3">
                  <img
                    src={iconUrl}
                    alt=""
                    className="size-10 shrink-0 rounded-md border bg-muted object-cover"
                  />
                  <div className="min-w-0 flex-1">
                    <CardTitle className="text-base">
                      {extractI18nObject(plugin.label) || plugin.name}
                    </CardTitle>
                    <CardDescription className="mt-1 text-xs font-mono">
                      {plugin.author}/{plugin.name}
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col">
                  <p className="line-clamp-3 text-sm text-muted-foreground">
                    {extractI18nObject(plugin.description)}
                  </p>
                  <div className="mt-auto pt-4">
                    {preferredOption ? (
                      <Button
                        type="button"
                        className="w-full"
                        onClick={() => onSelect(preferredOption.name)}
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
                        className="w-full"
                        disabled={installingRunnerPluginId !== null}
                        onClick={() => onInstall(plugin)}
                      >
                        {isInstalling ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Download className="size-4" />
                        )}
                        {isInstalling
                          ? t('wizard.aiEngine.installing')
                          : t('wizard.aiEngine.installAndContinue')}
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}

          {standaloneRunnerOptions.map((opt) => (
            <Card
              key={opt.name}
              className="min-h-40 cursor-pointer transition-all hover:border-primary/50 hover:shadow-md"
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
            <Link to="/home/extensions?type=plugin&component=AgentRunner">
              {t('wizard.aiEngine.browseRunners')}
              <ExternalLink className="size-4" />
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  // After a runner is selected: left-right split layout
  // On mobile (< lg): single column, normal scroll from parent
  // On desktop (>= lg): side-by-side with independent scroll per column
  return (
    <div className="flex flex-col lg:flex-1 lg:min-h-0 max-w-6xl mx-auto w-full">
      <div className="text-center shrink-0 mb-4">
        <h2 className="text-xl font-semibold">{t('wizard.aiEngine.title')}</h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t('wizard.aiEngine.description')}
        </p>
      </div>

      <div className="flex flex-col lg:flex-row lg:justify-center gap-6 lg:flex-1 lg:min-h-0 animate-in fade-in slide-in-from-bottom-2 duration-300">
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

            {/* Space promotion banner */}
            {selected === 'plugin:langbot-team/LocalAgent/default' &&
              isLocalAccount && (
                <div className="animate-in fade-in slide-in-from-left-2 duration-300">
                  <div className="relative rounded-lg p-[2px] bg-gradient-to-r from-purple-500 via-pink-500 to-orange-500">
                    <div className="rounded-[calc(0.5rem-2px)] bg-background p-3 flex flex-col items-center gap-2 text-center">
                      <Sparkles className="w-6 h-6 text-purple-500 shrink-0" />
                      <p className="text-xs font-medium">
                        {t('wizard.spaceBanner.message')}
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={onSpaceAuth}
                        className="w-full"
                      >
                        {t('wizard.spaceBanner.action')}
                      </Button>
                    </div>
                  </div>
                </div>
              )}
          </div>
        </div>

        {/* Right: runner configuration — fixed width on desktop */}
        <div className="w-full lg:w-[560px] shrink-0 lg:overflow-y-auto lg:pr-3 animate-in fade-in slide-in-from-right-2 duration-300">
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
