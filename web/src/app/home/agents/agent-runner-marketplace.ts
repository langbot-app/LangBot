import { httpClient } from '@/app/infra/http/HttpClient';
import { getCloudServiceClient } from '@/app/infra/http';
import { getActiveWorkspaceUuid } from '@/app/infra/http/workspaceContext';
import type { IDynamicFormItemOption } from '@/app/infra/entities/form/dynamic';
import type { PipelineConfigTab } from '@/app/infra/entities/pipeline';
import type { PluginV4 } from '@/app/infra/entities/plugin';
import type { I18nObject } from '@/app/infra/entities/common';

export const RUNNER_COMPONENT_FILTER = 'AgentRunner';

const RUNNER_CATALOG_PAGE_SIZE = 100;
const RUNNER_INSTALL_TIMEOUT_MS = 120_000;
const RUNNER_REGISTRATION_TIMEOUT_MS = 60_000;
const RUNNER_INSTALL_INTENT_KEY_PREFIX = 'langbot-agent-runner-install';
const RUNNER_INSTALL_INTENT_EVENT = 'langbot-agent-runner-install-change';

export type AgentRunnerMarketplaceErrorCode =
  | 'version-unavailable'
  | 'install-timeout'
  | 'registration-timeout';

export class AgentRunnerMarketplaceError extends Error {
  constructor(public readonly code: AgentRunnerMarketplaceErrorCode) {
    super(code);
    this.name = 'AgentRunnerMarketplaceError';
  }
}

export interface AgentRunnerCatalog {
  marketplaceRunners: PluginV4[];
  installedPluginIds: string[];
  installedPluginDescriptions: Record<string, I18nObject>;
}

export interface InstalledAgentRunner {
  configTab: PipelineConfigTab;
  runner: IDynamicFormItemOption;
}

export interface PendingAgentRunnerInstall {
  taskId: number;
  pluginId: string;
  pluginAuthor: string;
  pluginName: string;
  pluginLabel: string;
  scope: string;
  startedAt: number;
}

interface InstallAgentRunnerOptions {
  scope: string;
  onTaskCreated?: (taskId: number) => void;
}

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object') {
    const value = error as { msg?: string; message?: string };
    return value.msg || value.message || '';
  }
  return typeof error === 'string' ? error : '';
}

export function marketplacePluginId(plugin: Pick<PluginV4, 'author' | 'name'>) {
  return `${plugin.author}/${plugin.name}`;
}

export function runnerPluginPrefix(plugin: Pick<PluginV4, 'author' | 'name'>) {
  return `plugin:${plugin.author}/${plugin.name}/`;
}

function installIntentStorageKey(scope: string) {
  return `${RUNNER_INSTALL_INTENT_KEY_PREFIX}:${getActiveWorkspaceUuid() || 'default'}:${scope}`;
}

function emitInstallIntentChange(scope: string) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent(RUNNER_INSTALL_INTENT_EVENT, { detail: { scope } }),
  );
}

export function readPendingAgentRunnerInstall(
  scope: string,
): PendingAgentRunnerInstall | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(installIntentStorageKey(scope));
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<PendingAgentRunnerInstall>;
    if (
      value.scope !== scope ||
      typeof value.taskId !== 'number' ||
      typeof value.pluginId !== 'string' ||
      typeof value.pluginAuthor !== 'string' ||
      typeof value.pluginName !== 'string' ||
      typeof value.pluginLabel !== 'string' ||
      typeof value.startedAt !== 'number'
    ) {
      sessionStorage.removeItem(installIntentStorageKey(scope));
      return null;
    }
    return value as PendingAgentRunnerInstall;
  } catch {
    return null;
  }
}

function writePendingAgentRunnerInstall(intent: PendingAgentRunnerInstall) {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(
    installIntentStorageKey(intent.scope),
    JSON.stringify(intent),
  );
  emitInstallIntentChange(intent.scope);
}

export function clearPendingAgentRunnerInstall(scope: string, taskId?: number) {
  if (typeof window === 'undefined') return;
  const current = readPendingAgentRunnerInstall(scope);
  if (taskId !== undefined && current?.taskId !== taskId) return;
  sessionStorage.removeItem(installIntentStorageKey(scope));
  emitInstallIntentChange(scope);
}

export function subscribePendingAgentRunnerInstall(
  scope: string,
  listener: () => void,
) {
  if (typeof window === 'undefined') return () => undefined;
  const handleChange = (event: Event) => {
    const detail = (event as CustomEvent<{ scope?: string }>).detail;
    if (detail?.scope === scope) listener();
  };
  window.addEventListener(RUNNER_INSTALL_INTENT_EVENT, handleChange);
  return () =>
    window.removeEventListener(RUNNER_INSTALL_INTENT_EVENT, handleChange);
}

export async function loadAgentRunnerCatalog(): Promise<AgentRunnerCatalog> {
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
    Math.ceil((firstSearchResult.total || 0) / RUNNER_CATALOG_PAGE_SIZE) - 1,
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

  const marketplaceRunners = catalogPlugins
    .filter((plugin) => plugin.components?.[RUNNER_COMPONENT_FILTER])
    .sort((left, right) => {
      const leftOrder = recommendationOrder.get(marketplacePluginId(left));
      const rightOrder = recommendationOrder.get(marketplacePluginId(right));
      if (leftOrder !== undefined && rightOrder !== undefined) {
        return leftOrder - rightOrder;
      }
      if (leftOrder !== undefined) return -1;
      if (rightOrder !== undefined) return 1;
      return right.install_count - left.install_count;
    });

  const installedPluginDescriptions: Record<string, I18nObject> = {};
  const installedPluginIds = installedResult.plugins.map((plugin) => {
    const metadata = plugin.manifest.manifest.metadata;
    const pluginId = `${metadata.author ?? ''}/${metadata.name}`;
    if (metadata.description) {
      installedPluginDescriptions[pluginId] = metadata.description;
    }
    return pluginId;
  });

  return {
    marketplaceRunners,
    installedPluginIds,
    installedPluginDescriptions,
  };
}

export async function installMarketplaceAgentRunner(
  plugin: PluginV4,
  options: InstallAgentRunnerOptions,
): Promise<InstalledAgentRunner> {
  if (!plugin.latest_version) {
    throw new AgentRunnerMarketplaceError('version-unavailable');
  }

  const { task_id: taskId } = await httpClient.installPluginFromMarketplace(
    plugin.author,
    plugin.name,
    plugin.latest_version,
  );
  const pending: PendingAgentRunnerInstall = {
    taskId,
    pluginId: marketplacePluginId(plugin),
    pluginAuthor: plugin.author,
    pluginName: plugin.name,
    pluginLabel: extractPluginLabel(plugin),
    scope: options.scope,
    startedAt: Date.now(),
  };
  writePendingAgentRunnerInstall(pending);
  options.onTaskCreated?.(taskId);
  return finishAgentRunnerInstall(pending);
}

function extractPluginLabel(plugin: PluginV4) {
  const label = plugin.label;
  if (typeof label === 'string') return label || plugin.name;
  if (label && typeof label === 'object') {
    const localized = Object.values(label).find(
      (value): value is string => typeof value === 'string' && value.length > 0,
    );
    if (localized) return localized;
  }
  return plugin.name;
}

async function finishAgentRunnerInstall(
  pending: PendingAgentRunnerInstall,
): Promise<InstalledAgentRunner> {
  // A refreshed page receives a fresh observation window. The backend task is
  // authoritative; `startedAt` is display metadata, not a reason to abandon a
  // still-running installation immediately after recovery.
  const installDeadline = Date.now() + RUNNER_INSTALL_TIMEOUT_MS;
  let installCompleted = false;
  while (true) {
    const task = await httpClient.getAsyncTask(pending.taskId);
    if (task.runtime.done) {
      if (task.runtime.exception) {
        clearPendingAgentRunnerInstall(pending.scope, pending.taskId);
        throw new Error(task.runtime.exception);
      }
      installCompleted = true;
      break;
    }
    if (Date.now() >= installDeadline) break;
    await wait(1000);
  }
  if (!installCompleted) {
    throw new AgentRunnerMarketplaceError('install-timeout');
  }

  const registrationDeadline = Date.now() + RUNNER_REGISTRATION_TIMEOUT_MS;
  const prefix = runnerPluginPrefix({
    author: pending.pluginAuthor,
    name: pending.pluginName,
  });
  while (Date.now() < registrationDeadline) {
    const metadata = await httpClient.getGeneralPipelineMetadata();
    const configTab = metadata.configs.find((config) => config.name === 'ai');
    const runnerStage = configTab?.stages.find(
      (stage) => stage.name === 'runner',
    );
    const runnerOptions =
      runnerStage?.config.find((item) => item.name === 'id')?.options ?? [];
    const pluginRunnerOptions = runnerOptions.filter((option) =>
      option.name.startsWith(prefix),
    );
    const runner =
      pluginRunnerOptions.find((option) => option.name.endsWith('/default')) ??
      pluginRunnerOptions[0];

    if (configTab && runner) {
      clearPendingAgentRunnerInstall(pending.scope, pending.taskId);
      return { configTab, runner };
    }
    await wait(1000);
  }

  clearPendingAgentRunnerInstall(pending.scope, pending.taskId);
  throw new AgentRunnerMarketplaceError('registration-timeout');
}

export async function resumePendingAgentRunnerInstall(
  scope: string,
): Promise<InstalledAgentRunner | null> {
  const pending = readPendingAgentRunnerInstall(scope);
  if (!pending) return null;
  return finishAgentRunnerInstall(pending);
}
