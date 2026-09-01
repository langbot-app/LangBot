import { httpClient } from '@/app/infra/http/HttpClient';
import { getCloudServiceClient } from '@/app/infra/http';
import type { IDynamicFormItemOption } from '@/app/infra/entities/form/dynamic';
import type { PipelineConfigTab } from '@/app/infra/entities/pipeline';
import type { PluginV4 } from '@/app/infra/entities/plugin';

export const RUNNER_COMPONENT_FILTER = 'AgentRunner';

const RUNNER_CATALOG_PAGE_SIZE = 100;
const RUNNER_INSTALL_TIMEOUT_MS = 120_000;
const RUNNER_REGISTRATION_TIMEOUT_MS = 60_000;

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
}

export interface InstalledAgentRunner {
  configTab: PipelineConfigTab;
  runner: IDynamicFormItemOption;
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

  return {
    marketplaceRunners,
    installedPluginIds: installedResult.plugins.map((plugin) => {
      const metadata = plugin.manifest.manifest.metadata;
      return `${metadata.author ?? ''}/${metadata.name}`;
    }),
  };
}

export async function installMarketplaceAgentRunner(
  plugin: PluginV4,
): Promise<InstalledAgentRunner> {
  if (!plugin.latest_version) {
    throw new AgentRunnerMarketplaceError('version-unavailable');
  }

  const { task_id: taskId } = await httpClient.installPluginFromMarketplace(
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
    throw new AgentRunnerMarketplaceError('install-timeout');
  }

  const registrationDeadline = Date.now() + RUNNER_REGISTRATION_TIMEOUT_MS;
  const prefix = runnerPluginPrefix(plugin);
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
      return { configTab, runner };
    }
    await wait(1000);
  }

  throw new AgentRunnerMarketplaceError('registration-timeout');
}
