import { useSnapshotDirty } from '@/app/infra/hooks/useSnapshotDirty';
import EntityLoadState from '@/components/EntityLoadState';
import {
  forwardRef,
  type ForwardedRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useForm, useWatch, type Control } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  BookOpen,
  Bot,
  Box,
  Cpu,
  Gauge,
  Loader2,
  MessagesSquare,
  ScrollText,
  Settings2,
  SlidersHorizontal,
  Wrench,
  Zap,
} from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  Agent,
  AgentPlatformTool,
  ApiRespPluginSystemStatus,
  DomainMeta,
  PluginTool,
  WorkspaceOperationItem,
} from '@/app/infra/entities/api';
import {
  PipelineConfigStage,
  PipelineConfigTab,
} from '@/app/infra/entities/pipeline';
import {
  getErrorMessage,
  readPendingRunnerInstall,
  resumePendingRunnerInstall,
  type InstalledRunner,
} from '@/app/home/agents/runner-marketplace';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { getDefaultValues } from '@/app/home/components/dynamic-form/DynamicFormItemConfig';
import {
  PrimaryBlock,
  RetrievalSettings,
  SubsetForm,
  Watch,
  groupRunnerFields,
  modifiedCount,
} from '@/app/home/components/runner-layout/RunnerConfigLayout';
import {
  SettingGroup,
  SettingRow,
} from '@/app/home/components/setting-row/SettingRow';
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Form, FormField, FormItem, FormMessage } from '@/components/ui/form';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import AgentEventPatternPicker from './AgentEventPatternPicker';
import RunnerSelect from './RunnerSelect';
import GuidedTour, {
  GuidedTourStep,
} from '@/app/home/components/guided-tour/GuidedTour';
import AgentApiToolPicker from './AgentApiToolPicker';
import WorkspaceOperationsPicker from '@/app/home/components/workspace-operations/WorkspaceOperationsPicker';
import { collectSensitiveTools } from '@/app/home/components/sensitive-tools/SensitiveToolsWarning';
import { operationsForRunner } from '@/app/home/components/workspace-operations/runner-operation-grants';

const OTHER_TOOL_SCOPES = [
  'platform',
  'builtin',
  'mcp',
  'plugin',
  'skill',
] as const;

// Prompt fields in Agent configuration search the Agent prompt library (LANG-439).
const AGENT_FORM_SYSTEM_CONTEXT = { prompt_library_kind: 'agent' };

export interface RunnerStatus {
  label: string;
  description?: string;
  tone: 'neutral' | 'success' | 'warning' | 'error';
}

interface AgentFormComponentProps {
  agentId: string;
  availableEventTypes: string[];
  onFinish: (agent?: Partial<Agent>) => void;
  onDirtyChange?: (dirty: boolean) => void;
  onSavingChange?: (saving: boolean) => void;
  onRunnerStatusChange?: (status: RunnerStatus) => void;
  onSupportedEventPatternsChange?: (patterns: string[]) => void;
  onPlatformToolsChange?: (tools: AgentPlatformTool[]) => void;
  onSensitiveToolsChange?: (tools: string[]) => void;
  guideEnabled?: boolean;
  debugGuideEnabled?: boolean;
}

export type AgentConfigSection = 'runner' | 'events_and_tools';

export interface AgentFormHandle {
  openSection: (section: AgentConfigSection) => void;
  save: () => Promise<boolean>;
  syncBasicInfo: (values: {
    name: string;
    description: string;
    emoji?: string;
  }) => void;
}

function isRequiredRunnerValueMissing(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim() === '';
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object' && 'primary' in value) {
    return !String((value as { primary?: unknown }).primary || '').trim();
  }
  return false;
}

function isRunnerFieldVisible(
  field: PipelineConfigStage['config'][number],
  values: Record<string, unknown>,
) {
  if (!field.show_if || field.show_if.field.startsWith('__system.')) {
    return true;
  }
  const dependentValue = values[field.show_if.field];
  if (field.show_if.operator === 'eq') {
    return dependentValue === field.show_if.value;
  }
  if (field.show_if.operator === 'neq') {
    return dependentValue !== field.show_if.value;
  }
  return (
    Array.isArray(field.show_if.value) &&
    field.show_if.value.includes(dependentValue)
  );
}

/**
 * Fill the active runner's schema defaults under its stored values, before
 * the clean snapshot is taken: required-field status sees real values and
 * reverting an edit returns to a clean form.
 */
function withRunnerDefaults(
  schema: PipelineConfigTab | null,
  runnerId: unknown,
  configs: Record<string, unknown>,
): Record<string, unknown> {
  if (typeof runnerId !== 'string' || !runnerId) return configs;
  const stage = schema?.stages.find((item) => item.name === runnerId);
  if (!stage) return configs;
  const stored = configs[runnerId];
  return {
    ...configs,
    [runnerId]: {
      ...getDefaultValues(stage.config),
      ...(stored && typeof stored === 'object' ? stored : {}),
    },
  };
}

function AgentFormComponent(
  {
    agentId,
    availableEventTypes,
    onFinish,
    onDirtyChange,
    onSavingChange,
    onRunnerStatusChange,
    onSupportedEventPatternsChange,
    onPlatformToolsChange,
    onSensitiveToolsChange,
    guideEnabled = true,
    debugGuideEnabled = false,
  }: AgentFormComponentProps,
  ref: ForwardedRef<AgentFormHandle>,
) {
  const { t } = useTranslation();
  const [runnerConfigSchema, setRunnerConfigSchema] =
    useState<PipelineConfigTab | null>(null);
  const [platformTools, setPlatformTools] = useState<AgentPlatformTool[]>([]);
  useEffect(() => {
    onPlatformToolsChange?.(platformTools);
  }, [onPlatformToolsChange, platformTools]);
  const [platformToolCatalogAvailable, setPlatformToolCatalogAvailable] =
    useState(true);
  const [hostTools, setHostTools] = useState<PluginTool[]>([]);
  const [hostToolCatalogAvailable, setHostToolCatalogAvailable] =
    useState(true);
  const [workspaceOperations, setWorkspaceOperations] = useState<
    WorkspaceOperationItem[]
  >([]);
  const [domains, setDomains] = useState<DomainMeta[]>([]);
  const [operationGrants, setOperationGrants] = useState<
    Record<string, string[]>
  >({});
  const [dangerousModalOpen, setDangerousModalOpen] = useState(false);
  const pendingSaveValuesRef = useRef<FormValues | null>(null);
  const pendingResolveRef = useRef<((value: boolean) => void) | null>(null);
  const [pluginSystemStatus, setPluginSystemStatus] =
    useState<ApiRespPluginSystemStatus | null>(null);
  const [pluginStatusLoading, setPluginStatusLoading] = useState(true);
  const [pluginStatusError, setPluginStatusError] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [initialDataLoaded, setInitialDataLoaded] = useState(false);
  const [runnerInstallRecovering, setRunnerInstallRecovering] = useState(false);
  const [toolsOpen, setToolsOpen] = useState(false);
  const isSavingRef = useRef(false);
  const loadedHostToolPolicyRef = useRef<string[] | undefined>(undefined);

  const formSchema = z.object({
    basic: z.object({
      name: z.string().min(1, { message: t('agents.nameRequired') }),
      description: z.string().optional(),
      emoji: z.string().optional(),
    }),
    runner: z.record(z.string(), z.any()),
    runner_config: z.record(z.string(), z.any()),
    supported_event_patterns: z.array(z.string()),
    allowed_platform_tools: z.array(z.string()),
    allowed_tools: z.array(z.string()),
    allowed_workspace_operations: z.array(z.string()),
  });
  type FormValues = z.infer<typeof formSchema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      basic: {
        name: '',
        description: '',
        emoji: '🤖',
      },
      runner: {},
      runner_config: {},
      supported_event_patterns: ['*'],
      allowed_platform_tools: [],
      allowed_tools: [],
      allowed_workspace_operations: [],
    },
  });
  const runnerInstallScope = `agent:${agentId}`;

  const applyInstalledRunner = useCallback((installed: InstalledRunner) => {
    setRunnerConfigSchema(installed.configTab);
  }, []);

  const savedSnapshotRef = useRef('');
  const initializedStagesRef = useRef<Set<string>>(new Set());
  const {
    isDirty: hasUnsavedChanges,
    dirtyRef: hasUnsavedChangesRef,
    refreshDirty,
  } = useSnapshotDirty(form, savedSnapshotRef);

  useEffect(() => {
    onDirtyChange?.(hasUnsavedChanges);
  }, [hasUnsavedChanges, onDirtyChange]);

  const supportedEventPatterns = useWatch({
    control: form.control,
    name: 'supported_event_patterns',
  });
  useEffect(() => {
    onSupportedEventPatternsChange?.(supportedEventPatterns);
  }, [onSupportedEventPatternsChange, supportedEventPatterns]);

  const selectedPlatformTools = useWatch({
    control: form.control,
    name: 'allowed_platform_tools',
  });
  const selectedWorkspaceOperations = useWatch({
    control: form.control,
    name: 'allowed_workspace_operations',
  });
  useEffect(() => {
    onSensitiveToolsChange?.(
      collectSensitiveTools(
        platformTools,
        selectedPlatformTools ?? [],
        workspaceOperations,
        selectedWorkspaceOperations ?? [],
      ),
    );
  }, [
    onSensitiveToolsChange,
    platformTools,
    selectedPlatformTools,
    workspaceOperations,
    selectedWorkspaceOperations,
  ]);

  useEffect(() => {
    let cancelled = false;
    setInitialDataLoaded(false);
    setLoadFailed(false);
    Promise.all([httpClient.getAgentMetadata(), httpClient.getAgent(agentId)])
      .then(([metadata, resp]) => {
        if (cancelled) return;
        setRunnerConfigSchema(metadata.runner_config ?? null);
        const hasPlatformToolCatalog = Array.isArray(metadata.platform_tools);
        setPlatformToolCatalogAvailable(hasPlatformToolCatalog);
        const availablePlatformTools = hasPlatformToolCatalog
          ? metadata.platform_tools
          : [];
        setPlatformTools(availablePlatformTools);
        const hasHostToolCatalog = Array.isArray(metadata.host_tools);
        const availableHostTools: PluginTool[] = Array.isArray(
          metadata.host_tools,
        )
          ? metadata.host_tools
          : [];
        setHostToolCatalogAvailable(hasHostToolCatalog);
        setHostTools(availableHostTools);
        setWorkspaceOperations(metadata.workspace_operations || []);
        setOperationGrants(metadata.workspace_operation_grants || {});
        setDomains(metadata.domains || []);
        const agent = resp.agent;
        const config = (agent.config ?? {}) as Record<string, any>;
        const configuredHostTools = Array.isArray(config.allowed_tools)
          ? config.allowed_tools.filter(
              (name): name is string => typeof name === 'string',
            )
          : undefined;
        const configuredPlatformTools = Array.isArray(
          config.allowed_platform_tools,
        )
          ? config.allowed_platform_tools.filter(
              (name): name is string => typeof name === 'string',
            )
          : [];
        const configuredWorkspaceOperations = Array.isArray(
          config.allowed_workspace_operations,
        )
          ? config.allowed_workspace_operations.filter(
              (name): name is string => typeof name === 'string',
            )
          : [];
        const configuredEventPatterns =
          agent.supported_event_patterns ??
          agent.capability?.supported_event_patterns;
        const normalizedEventPatterns = Array.isArray(configuredEventPatterns)
          ? configuredEventPatterns.filter(
              (pattern): pattern is string => typeof pattern === 'string',
            )
          : ['*'];
        loadedHostToolPolicyRef.current = configuredHostTools;
        const loadedValues: FormValues = {
          basic: {
            name: agent.name ?? '',
            description: agent.description ?? '',
            emoji: agent.emoji || '🤖',
          },
          runner: (config.runner as Record<string, unknown>) ?? {},
          runner_config: withRunnerDefaults(
            metadata.runner_config ?? null,
            (config.runner as Record<string, unknown>)?.id,
            (config.runner_config as Record<string, unknown>) ?? {},
          ),
          supported_event_patterns: normalizedEventPatterns,
          allowed_platform_tools: configuredPlatformTools.filter((name) => {
            const tool = availablePlatformTools.find(
              (candidate) => candidate.name === name,
            );
            return !tool || tool.scope === 'platform';
          }),
          allowed_tools:
            configuredHostTools ?? availableHostTools.map((tool) => tool.name),
          allowed_workspace_operations: configuredWorkspaceOperations,
        };
        form.reset(loadedValues);
        savedSnapshotRef.current = JSON.stringify(loadedValues);
        refreshDirty();
        initializedStagesRef.current.clear();
        setInitialDataLoaded(true);
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadFailed(true);
        toast.error(t('agents.loadError') + err.msg);
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, form, t, loadAttempt, refreshDirty]);

  useEffect(() => {
    if (!initialDataLoaded || !readPendingRunnerInstall(runnerInstallScope)) {
      return;
    }
    let cancelled = false;
    setRunnerInstallRecovering(true);
    void resumePendingRunnerInstall(runnerInstallScope)
      .then((installed) => {
        if (cancelled || !installed) return;
        applyInstalledRunner(installed);
        toast.success(
          t('agents.runnerInstallSuccess', {
            runner: extractI18nObject(installed.runner.label),
          }),
        );
      })
      .catch((error) => {
        if (!cancelled) {
          toast.error(
            getErrorMessage(error) || t('wizard.aiEngine.installFailed'),
          );
        }
      })
      .finally(() => {
        if (!cancelled) setRunnerInstallRecovering(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applyInstalledRunner, initialDataLoaded, runnerInstallScope, t]);

  const loadPluginSystemStatus = useCallback(async () => {
    setPluginStatusLoading(true);
    setPluginStatusError(false);
    try {
      setPluginSystemStatus(await httpClient.getPluginSystemStatus());
    } catch {
      setPluginSystemStatus(null);
      setPluginStatusError(true);
    } finally {
      setPluginStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPluginSystemStatus();
  }, [loadPluginSystemStatus]);

  const currentRunner = useWatch({
    control: form.control,
    name: 'runner',
    compute: (runner) => runner?.id,
  });
  const runnerOptions = useMemo(() => {
    const runnerStage = runnerConfigSchema?.stages.find(
      (stage) => stage.name === 'runner',
    );
    return (
      runnerStage?.config.find((item) => item.name === 'id')?.options ?? []
    );
  }, [runnerConfigSchema]);
  const selectedRunnerOption = runnerOptions.find(
    (option) => option.name === currentRunner,
  );
  const selectableWorkspaceOperations = operationsForRunner(
    workspaceOperations,
    currentRunner,
    operationGrants,
  );
  const runnerSelectorStage = runnerConfigSchema?.stages.find(
    (stage) => stage.name === 'runner',
  );
  const activeRunnerStage = runnerConfigSchema?.stages.find(
    (stage) => stage.name === currentRunner,
  );
  const runnerConfigValues = form.getValues('runner_config') as Record<
    string,
    Record<string, unknown>
  >;
  useWatch({
    control: form.control,
    compute: (values) =>
      (activeRunnerStage?.config ?? [])
        .filter(
          (field) =>
            field.required &&
            isRunnerFieldVisible(
              field,
              values.runner_config?.[currentRunner] ?? {},
            ) &&
            isRequiredRunnerValueMissing(
              values.runner_config?.[currentRunner]?.[field.name],
            ),
        )
        .map((field) => field.name)
        .join('\n'),
  });
  const activeRunnerValues = runnerConfigValues?.[currentRunner] ?? {};
  const missingRunnerFields = (activeRunnerStage?.config ?? []).filter(
    (field) =>
      field.required &&
      isRunnerFieldVisible(field, activeRunnerValues) &&
      isRequiredRunnerValueMissing(activeRunnerValues[field.name]),
  );
  const missingRunnerFieldNames = missingRunnerFields
    .map((field) => extractI18nObject(field.label))
    .join(', ');
  const runnerStatus = useMemo<RunnerStatus>(() => {
    if (loadFailed) return { label: t('common.loadFailed'), tone: 'error' };
    if (!initialDataLoaded || pluginStatusLoading) {
      return {
        label: t('agents.runnerStatusLoading'),
        tone: 'neutral',
      };
    }

    if (pluginStatusError || !pluginSystemStatus) {
      return {
        label: t('agents.runnerStatusCheckFailed'),
        description: t('agents.runnerStatusCheckFailedDescription'),
        tone: 'error',
      };
    }

    if (!pluginSystemStatus.is_enable) {
      return {
        label: t('plugins.systemDisabled'),
        description: t('plugins.systemDisabledDesc'),
        tone: 'error',
      };
    }

    if (!pluginSystemStatus.is_connected) {
      return {
        label: t('plugins.connectionError'),
        description: t('plugins.connectionErrorDesc'),
        tone: 'error',
      };
    }

    if (runnerOptions.length === 0) {
      return {
        label: t('agents.noRunnersAvailable'),
        description: t('agents.noRunnersAvailableDescription'),
        tone: 'error',
      };
    }

    if (!currentRunner || !selectedRunnerOption) {
      return {
        label: t('agents.selectedRunnerUnavailable'),
        description: t('agents.selectedRunnerUnavailableDescription', {
          runner: currentRunner || t('agents.noRunnerSelected'),
        }),
        tone: 'warning',
      };
    }

    if (missingRunnerFields.length > 0) {
      return {
        label: t('agents.runnerConfigIncomplete'),
        description: t('agents.runnerConfigIncompleteDescription', {
          fields: missingRunnerFieldNames,
        }),
        tone: 'warning',
      };
    }

    return {
      label: t('agents.runnerReady'),
      description: t('agents.runnerReadyDescription', {
        runner: extractI18nObject(selectedRunnerOption.label),
      }),
      tone: 'success',
    };
  }, [
    initialDataLoaded,
    loadFailed,
    currentRunner,
    pluginStatusError,
    pluginStatusLoading,
    pluginSystemStatus,
    runnerOptions.length,
    missingRunnerFieldNames,
    missingRunnerFields.length,
    selectedRunnerOption,
    t,
  ]);

  const runnerGuideSteps = useMemo<GuidedTourStep[]>(() => {
    const steps: GuidedTourStep[] = [
      {
        id: 'runner',
        target: '[data-guide="runner-selector"]',
        title: t('guidedTour.runner.select.title'),
        description: t('guidedTour.runner.select.description'),
        action: {
          href: 'https://space.langbot.app/market?type=plugin&component=Runner&runner_usage=agent',
          label: t('guidedTour.runner.select.action'),
        },
      },
    ];

    if (activeRunnerStage) {
      steps.push({
        id: 'parameters',
        target: '[data-guide="runner-parameters"]',
        title: t('guidedTour.runner.parameters.title'),
        description: t('guidedTour.runner.parameters.description'),
      });
    }

    steps.push({
      id: 'events',
      target: '[data-guide="agent-sections"]',
      title: t('guidedTour.runner.events.title'),
      description: t('guidedTour.runner.events.description'),
    });
    if (debugGuideEnabled) {
      steps.push({
        id: 'debug',
        target: '[data-guide="agent-event-debug"]',
        title: t('guidedTour.runner.debug.title'),
        description: t('guidedTour.eventDebugDescription'),
      });
    }
    return steps;
  }, [activeRunnerStage, debugGuideEnabled, t]);

  useEffect(() => {
    onRunnerStatusChange?.(runnerStatus);
  }, [onRunnerStatusChange, runnerStatus]);

  // --- One-page layout: runner, then what the answer is built from and
  // what the Agent handles, then folded rows with summaries. ---
  const runnerGroups = useMemo(
    () => groupRunnerFields(activeRunnerStage?.config ?? []),
    [activeRunnerStage],
  );
  const runnerIdItems = useMemo(
    () => (runnerSelectorStage?.config ?? []).filter((i) => i.name === 'id'),
    [runnerSelectorStage],
  );
  const runnerExtraItems = useMemo(
    () => (runnerSelectorStage?.config ?? []).filter((i) => i.name !== 'id'),
    [runnerSelectorStage],
  );
  const readRunner = () =>
    (form.getValues('runner') as Record<string, unknown>) ?? {};
  const writeRunner = (next: Record<string, unknown>) => {
    form.setValue('runner', next, { shouldDirty: true });
    const id = next.id;
    const configs =
      (form.getValues('runner_config') as Record<string, unknown>) ?? {};
    const stage = runnerConfigSchema?.stages.find((item) => item.name === id);
    // A newly chosen runner starts from its schema defaults.
    if (typeof id === 'string' && id && stage && !(id in configs)) {
      form.setValue(
        'runner_config',
        { ...configs, [id]: getDefaultValues(stage.config) },
        { shouldDirty: true },
      );
    }
  };
  const readRunnerConfig = () =>
    ((form.getValues('runner_config') as Record<string, any>) ?? {})[
      currentRunner
    ] ?? {};
  const writeRunnerConfig = (next: Record<string, unknown>) =>
    form.setValue(
      'runner_config',
      {
        ...((form.getValues('runner_config') as Record<string, unknown>) ?? {}),
        [currentRunner]: next,
      },
      { shouldDirty: true },
    );
  const runnerForm = (items: PipelineConfigStage['config']) => (
    <SubsetForm
      key={`${currentRunner}:${items.map((item) => item.name).join(',')}`}
      items={items}
      read={readRunnerConfig}
      write={writeRunnerConfig}
      systemContext={AGENT_FORM_SYSTEM_CONTEXT}
    />
  );
  const ck = (key: string) => `pipelines.chatConfig.${key}`;
  const watchControl = form.control as unknown as Control;
  const firstRunnerBlock = runnerGroups.model.length
    ? 'model'
    : runnerGroups.prompt.length
      ? 'prompt'
      : runnerGroups.knowledge.length
        ? 'knowledge'
        : 'basic';
  const parametersGuide = (block: string) =>
    block === firstRunnerBlock ? 'runner-parameters' : undefined;
  const changedSummary = (
    items: PipelineConfigStage['config'],
    configs: Record<string, Record<string, unknown>> | undefined,
  ) => {
    const changed = modifiedCount(items, configs?.[currentRunner] ?? {});
    return changed ? t(ck('modified'), { count: changed }) : t(ck('default'));
  };
  const toolCount = (count: number, all?: number) =>
    all !== undefined && all > 0 && count >= all
      ? t(ck('all'))
      : count > 0
        ? t(ck('countItems'), { count })
        : t(ck('none'));

  const saveValues = useCallback(
    async (values: FormValues) => {
      if (isSavingRef.current) return false;
      const submittedSnapshot = JSON.stringify(values);
      const runner = values.runner || {};
      const config: Record<string, unknown> = {
        runner,
        runner_config: values.runner_config ?? {},
        allowed_platform_tools: values.allowed_platform_tools,
        allowed_workspace_operations: values.allowed_workspace_operations,
      };
      if (hostToolCatalogAvailable) {
        config.allowed_tools = values.allowed_tools;
      } else if (loadedHostToolPolicyRef.current !== undefined) {
        config.allowed_tools = loadedHostToolPolicyRef.current;
      }
      const agent: Partial<Agent> = {
        name: values.basic.name,
        description: values.basic.description ?? '',
        emoji: values.basic.emoji,
        component_ref: (runner.id as string) || null,
        supported_event_patterns: values.supported_event_patterns,
        config,
      };

      isSavingRef.current = true;
      onSavingChange?.(true);
      try {
        await httpClient.updateAgent(agentId, agent);
        if (hostToolCatalogAvailable) {
          loadedHostToolPolicyRef.current = [...values.allowed_tools];
        }
        savedSnapshotRef.current = submittedSnapshot;
        refreshDirty();
        onFinish(agent);
        toast.success(t('agents.saveSuccess'));
        return true;
      } catch (err) {
        const message =
          typeof err === 'object' && err && 'msg' in err
            ? String((err as { msg?: string }).msg || '')
            : '';
        toast.error(t('agents.saveError') + message);
        return false;
      } finally {
        isSavingRef.current = false;
        onSavingChange?.(false);
      }
    },
    [
      agentId,
      hostToolCatalogAvailable,
      onFinish,
      onSavingChange,
      refreshDirty,
      t,
    ],
  );

  const confirmAndSave = useCallback(
    (values: FormValues): Promise<boolean> => {
      const ungrantableOps = values.allowed_workspace_operations.filter(
        (opId) => {
          const op = selectableWorkspaceOperations.find(
            (item) => item.id === opId,
          );
          return op && op.grantable === false;
        },
      );

      let effectiveValues = values;
      if (ungrantableOps.length > 0) {
        const filteredOps = values.allowed_workspace_operations.filter(
          (opId) => {
            const op = selectableWorkspaceOperations.find(
              (item) => item.id === opId,
            );
            return !op || op.grantable !== false;
          },
        );
        toast.warning(
          t('workspaceOperations.ungrantableRemoved', {
            count: ungrantableOps.length,
          }),
        );
        effectiveValues = {
          ...values,
          allowed_workspace_operations: filteredOps,
        };
        form.setValue('allowed_workspace_operations', filteredOps, {
          shouldDirty: true,
        });
      }

      const hasDangerous = effectiveValues.allowed_workspace_operations.some(
        (opId) => {
          const op = workspaceOperations.find((item) => item.id === opId);
          return op?.risk === 'dangerous';
        },
      );
      if (hasDangerous) {
        return new Promise<boolean>((resolve) => {
          pendingSaveValuesRef.current = effectiveValues;
          pendingResolveRef.current = resolve;
          setDangerousModalOpen(true);
        });
      }
      return saveValues(effectiveValues);
    },
    [form, saveValues, t, workspaceOperations, selectableWorkspaceOperations],
  );

  function handleSubmit(values: FormValues) {
    void confirmAndSave(values);
  }

  useImperativeHandle(
    ref,
    () => ({
      openSection(section: AgentConfigSection) {
        document
          .querySelector(
            section === 'runner'
              ? '[data-guide="runner-selector"]'
              : '[data-guide="agent-sections"]',
          )
          ?.scrollIntoView({ block: 'start', behavior: 'smooth' });
      },
      syncBasicInfo(values) {
        form.setValue('basic', {
          ...form.getValues('basic'),
          name: values.name,
          description: values.description,
          emoji: values.emoji || '🤖',
        });
        if (savedSnapshotRef.current) {
          const snapshot = JSON.parse(savedSnapshotRef.current) as FormValues;
          snapshot.basic = {
            ...snapshot.basic,
            name: values.name,
            description: values.description,
            emoji: values.emoji || '🤖',
          };
          savedSnapshotRef.current = JSON.stringify(snapshot);
          refreshDirty();
        }
      },
      async save() {
        if (!initialDataLoaded || loadFailed) return false;
        if (!hasUnsavedChangesRef.current) return true;
        if (isSavingRef.current) return false;
        const valid = await form.trigger();
        if (!valid) return false;
        return (await confirmAndSave(form.getValues())) ?? false;
      },
    }),
    [
      confirmAndSave,
      form,
      initialDataLoaded,
      loadFailed,
      hasUnsavedChangesRef,
      refreshDirty,
    ],
  );

  if (loadFailed)
    return (
      <EntityLoadState error onRetry={() => setLoadAttempt((n) => n + 1)} />
    );
  if (!initialDataLoaded) return <EntityLoadState />;

  return (
    <div className="h-full p-0 flex flex-col">
      <Form {...form}>
        <form
          id="agent-form"
          onSubmit={form.handleSubmit(handleSubmit)}
          className="mb-2 flex h-full min-h-0 min-w-0 flex-1 flex-col"
        >
          {/* relative: contain absolutely positioned form internals (hidden
              native inputs) so they cannot stretch the page frame. */}
          <div className="relative min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-none">
            <div
              className="mx-auto w-full min-w-0 max-w-5xl space-y-6 pb-8"
              data-testid="agent-config"
            >
              {/* Who answers */}
              {runnerSelectorStage ? (
                <PrimaryBlock icon={Bot} guide="runner-selector">
                  <SubsetForm
                    items={runnerIdItems}
                    read={readRunner}
                    write={writeRunner}
                    systemContext={AGENT_FORM_SYSTEM_CONTEXT}
                    renderItem={({ config, field }) =>
                      config.name === 'id' ? (
                        <RunnerSelect
                          options={config.options ?? []}
                          label={extractI18nObject(config.label)}
                          value={String(field.value ?? '')}
                          onValueChange={field.onChange}
                          installScope={runnerInstallScope}
                          onInstalled={applyInstalledRunner}
                        />
                      ) : undefined
                    }
                  />
                  {activeRunnerStage?.description && (
                    <p className="text-xs text-muted-foreground">
                      {extractI18nObject(activeRunnerStage.description)}
                    </p>
                  )}
                </PrimaryBlock>
              ) : (
                !runnerConfigSchema && (
                  <Card>
                    <CardHeader>
                      <CardTitle>{t('agents.runnerSettings')}</CardTitle>
                      <CardDescription>
                        {t('agents.noRunnerMetadata')}
                      </CardDescription>
                    </CardHeader>
                  </Card>
                )
              )}
              {runnerInstallRecovering ? (
                <Card>
                  <CardHeader>
                    <CardTitle>{t('agents.runnerSettings')}</CardTitle>
                    <CardDescription className="flex items-center gap-2">
                      <Loader2 className="size-4 animate-spin" />
                      {t('agents.restoringRunnerInstall')}
                    </CardDescription>
                  </CardHeader>
                </Card>
              ) : (
                !activeRunnerStage &&
                runnerConfigSchema && (
                  <Card>
                    <CardHeader>
                      <CardTitle>{t('agents.runnerSettings')}</CardTitle>
                      <CardDescription>
                        {t('agents.noRunnerMetadata')}
                      </CardDescription>
                    </CardHeader>
                  </Card>
                )
              )}

              {/* What the answer is built from */}
              {!runnerInstallRecovering && activeRunnerStage && (
                <>
                  {runnerGroups.model.length > 0 && (
                    <PrimaryBlock icon={Cpu} guide={parametersGuide('model')}>
                      {runnerForm(runnerGroups.model)}
                    </PrimaryBlock>
                  )}
                  {runnerGroups.prompt.length > 0 && (
                    <PrimaryBlock
                      icon={ScrollText}
                      guide={parametersGuide('prompt')}
                    >
                      {runnerForm(runnerGroups.prompt)}
                    </PrimaryBlock>
                  )}
                </>
              )}

              {/* What this Agent handles, and what it may call */}
              <PrimaryBlock
                icon={Zap}
                guide="agent-sections"
                title={t('agents.bindableEvents')}
                hint={t('agents.bindableEventsDescription')}
              >
                <FormField
                  control={form.control}
                  name="supported_event_patterns"
                  render={({ field }) => (
                    <FormItem>
                      <AgentEventPatternPicker
                        events={availableEventTypes}
                        value={field.value}
                        onChange={field.onChange}
                        tools={platformTools}
                        catalogAvailable={platformToolCatalogAvailable}
                      />
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </PrimaryBlock>
              <PrimaryBlock
                icon={Wrench}
                title={t('agents.otherTools')}
                hint={t('agents.otherToolsDescription')}
                action={
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setToolsOpen(true)}
                    data-testid="agent-manage-tools"
                  >
                    {t(ck('manageTools'))}
                  </Button>
                }
              >
                <dl className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  {[
                    {
                      label: t('agents.layout.platformTools'),
                      value: toolCount(selectedPlatformTools?.length ?? 0),
                    },
                    {
                      label: t('agents.layout.hostTools'),
                      value: hostToolCatalogAvailable
                        ? toolCount(
                            form.watch('allowed_tools').length,
                            hostTools.length,
                          )
                        : '—',
                    },
                    {
                      label: t(ck('operations')),
                      value: toolCount(
                        selectedWorkspaceOperations?.length ?? 0,
                      ),
                    },
                  ].map((stat) => (
                    <div
                      key={stat.label}
                      className="rounded-md bg-muted/40 px-3 py-2"
                    >
                      <dt className="text-xs text-muted-foreground">
                        {stat.label}
                      </dt>
                      <dd className="text-sm font-medium">{stat.value}</dd>
                    </div>
                  ))}
                </dl>
              </PrimaryBlock>

              {!runnerInstallRecovering && activeRunnerStage && (
                <>
                  {runnerGroups.knowledge.length > 0 && (
                    <PrimaryBlock
                      icon={BookOpen}
                      guide={parametersGuide('knowledge')}
                    >
                      {runnerForm(runnerGroups.knowledge)}
                      {runnerGroups.retrieval.length > 0 && (
                        <RetrievalSettings label={t(ck('retrieval'))}>
                          {runnerForm(runnerGroups.retrieval)}
                        </RetrievalSettings>
                      )}
                    </PrimaryBlock>
                  )}
                  {runnerGroups.basic.length > 0 && (
                    <PrimaryBlock
                      icon={Settings2}
                      guide={parametersGuide('basic')}
                      title={t(ck('runnerSettings'), {
                        runner: extractI18nObject(activeRunnerStage.label),
                      })}
                    >
                      {runnerForm(runnerGroups.basic)}
                    </PrimaryBlock>
                  )}
                  {(runnerExtraItems.length > 0 ||
                    runnerGroups.context.length > 0 ||
                    runnerGroups.runtime.length > 0 ||
                    runnerGroups.sandbox.length > 0 ||
                    runnerGroups.advanced.length > 0) && (
                    <SettingGroup title={t(ck('more'))}>
                      {(runnerExtraItems.length > 0 ||
                        runnerGroups.context.length > 0) && (
                        <Watch<Record<string, Record<string, unknown>>>
                          control={watchControl}
                          name="runner_config"
                        >
                          {(configs) => (
                            <SettingRow
                              id="context"
                              icon={MessagesSquare}
                              title={t(ck('context'))}
                              summary={changedSummary(
                                runnerGroups.context,
                                configs,
                              )}
                            >
                              <SubsetForm
                                items={runnerExtraItems}
                                read={readRunner}
                                write={writeRunner}
                                systemContext={AGENT_FORM_SYSTEM_CONTEXT}
                              />
                              {runnerForm(runnerGroups.context)}
                            </SettingRow>
                          )}
                        </Watch>
                      )}
                      {runnerGroups.runtime.length > 0 && (
                        <Watch<Record<string, Record<string, unknown>>>
                          control={watchControl}
                          name="runner_config"
                        >
                          {(configs) => (
                            <SettingRow
                              id="runtime"
                              icon={Gauge}
                              title={t(ck('runtime'))}
                              summary={changedSummary(
                                runnerGroups.runtime,
                                configs,
                              )}
                            >
                              {runnerForm(runnerGroups.runtime)}
                            </SettingRow>
                          )}
                        </Watch>
                      )}
                      {runnerGroups.sandbox.length > 0 && (
                        <Watch<Record<string, Record<string, unknown>>>
                          control={watchControl}
                          name="runner_config"
                        >
                          {(configs) => (
                            <SettingRow
                              id="sandbox"
                              icon={Box}
                              title={t(ck('sandbox'))}
                              summary={
                                configs?.[currentRunner]?.['box-enabled'] ===
                                false
                                  ? t(ck('off'))
                                  : t(ck('on'))
                              }
                            >
                              {runnerForm(runnerGroups.sandbox)}
                            </SettingRow>
                          )}
                        </Watch>
                      )}
                      {runnerGroups.advanced.length > 0 && (
                        <Watch<Record<string, Record<string, unknown>>>
                          control={watchControl}
                          name="runner_config"
                        >
                          {(configs) => (
                            <SettingRow
                              id="advanced"
                              icon={SlidersHorizontal}
                              title={t(ck('advanced'))}
                              summary={changedSummary(
                                runnerGroups.advanced,
                                configs,
                              )}
                            >
                              {runnerForm(runnerGroups.advanced)}
                            </SettingRow>
                          )}
                        </Watch>
                      )}
                    </SettingGroup>
                  )}
                </>
              )}
            </div>
          </div>
          <Sheet open={toolsOpen} onOpenChange={setToolsOpen}>
            <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
              <SheetHeader>
                <SheetTitle>{t('agents.otherTools')}</SheetTitle>
                <SheetDescription>
                  {t('agents.layout.toolsSheetDescription')}
                </SheetDescription>
              </SheetHeader>
              <div className="px-4 pb-6">
                <FormField
                  control={form.control}
                  name="allowed_platform_tools"
                  render={({ field }) => (
                    <FormItem>
                      <AgentApiToolPicker
                        platformTools={platformTools}
                        platformValue={field.value}
                        onPlatformChange={field.onChange}
                        hostTools={hostTools}
                        hostValue={form.watch('allowed_tools')}
                        onHostChange={(value) =>
                          form.setValue('allowed_tools', value, {
                            shouldDirty: true,
                            shouldValidate: true,
                          })
                        }
                        platformCatalogAvailable={platformToolCatalogAvailable}
                        hostCatalogAvailable={hostToolCatalogAvailable}
                        scopes={OTHER_TOOL_SCOPES}
                        workspaceTools={{
                          count: workspaceOperations.length,
                          selectedCount: form.watch(
                            'allowed_workspace_operations',
                          ).length,
                          content: (
                            <FormField
                              control={form.control}
                              name="allowed_workspace_operations"
                              render={({ field: opsField }) => (
                                <FormItem>
                                  <WorkspaceOperationsPicker
                                    operations={selectableWorkspaceOperations}
                                    domains={domains}
                                    value={opsField.value}
                                    onChange={(next) =>
                                      form.setValue(
                                        'allowed_workspace_operations',
                                        next,
                                        {
                                          shouldDirty: true,
                                          shouldValidate: true,
                                        },
                                      )
                                    }
                                  />
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                          ),
                        }}
                      />
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            </SheetContent>
          </Sheet>
          <GuidedTour
            enabled={guideEnabled}
            storageKey="langbot_runner_setup_guide_v1"
            steps={runnerGuideSteps}
            testId="runner-setup-guide"
          />
          <AlertDialog
            open={dangerousModalOpen}
            onOpenChange={setDangerousModalOpen}
          >
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>
                  {t('workspaceOperations.dangerousConfirmTitle')}
                </AlertDialogTitle>
                <AlertDialogDescription>
                  {t('workspaceOperations.dangerousConfirmDescription')}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel
                  onClick={() => {
                    setDangerousModalOpen(false);
                    pendingResolveRef.current?.(false);
                    pendingSaveValuesRef.current = null;
                    pendingResolveRef.current = null;
                  }}
                >
                  {t('workspaceOperations.dangerousConfirmCancel')}
                </AlertDialogCancel>
                <AlertDialogAction
                  onClick={async () => {
                    setDangerousModalOpen(false);
                    if (pendingSaveValuesRef.current) {
                      const vals = pendingSaveValuesRef.current;
                      pendingSaveValuesRef.current = null;
                      const resolve = pendingResolveRef.current;
                      pendingResolveRef.current = null;
                      const success = await saveValues(vals);
                      resolve?.(success);
                    }
                  }}
                >
                  {t('workspaceOperations.dangerousConfirmAction')}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </form>
      </Form>
    </div>
  );
}

export default forwardRef(AgentFormComponent);
