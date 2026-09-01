import type { KnowledgeEngine } from '@/app/infra/entities/api';
import type { PluginV4 } from '@/app/infra/entities/plugin';
import { getCloudServiceClient } from '@/app/infra/http';
import { httpClient } from '@/app/infra/http/HttpClient';
import { getActiveWorkspaceUuid } from '@/app/infra/http/workspaceContext';

export const KNOWLEDGE_ENGINE_COMPONENT_FILTER = 'KnowledgeEngine';

const CATALOG_PAGE_SIZE = 100;
const INSTALL_TIMEOUT_MS = 120_000;
const REGISTRATION_TIMEOUT_MS = 60_000;
const INSTALL_INTENT_KEY_PREFIX = 'langbot-knowledge-engine-install';
const INSTALL_INTENT_EVENT = 'langbot-knowledge-engine-install-change';

export type KnowledgeEngineMarketplaceErrorCode =
  | 'version-unavailable'
  | 'install-timeout'
  | 'registration-timeout';

export class KnowledgeEngineMarketplaceError extends Error {
  constructor(public readonly code: KnowledgeEngineMarketplaceErrorCode) {
    super(code);
    this.name = 'KnowledgeEngineMarketplaceError';
  }
}

export interface KnowledgeEngineCatalog {
  marketplaceEngines: PluginV4[];
  installedPluginIds: string[];
}

export interface PendingKnowledgeEngineInstall {
  taskId: number;
  pluginId: string;
  pluginAuthor: string;
  pluginName: string;
  pluginLabel: string;
  scope: string;
  startedAt: number;
}

interface InstallKnowledgeEngineOptions {
  scope: string;
  onTaskCreated?: (taskId: number) => void;
}

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function getKnowledgeEngineInstallError(error: unknown): string {
  if (error && typeof error === 'object') {
    const value = error as { msg?: string; message?: string };
    return value.msg || value.message || '';
  }
  return typeof error === 'string' ? error : '';
}

export function knowledgeEnginePluginId(
  plugin: Pick<PluginV4, 'author' | 'name'>,
) {
  return `${plugin.author}/${plugin.name}`;
}

function installIntentStorageKey(scope: string) {
  return `${INSTALL_INTENT_KEY_PREFIX}:${getActiveWorkspaceUuid() || 'default'}:${scope}`;
}

function emitInstallIntentChange(scope: string) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent(INSTALL_INTENT_EVENT, { detail: { scope } }),
  );
}

export function readPendingKnowledgeEngineInstall(
  scope: string,
): PendingKnowledgeEngineInstall | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(installIntentStorageKey(scope));
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<PendingKnowledgeEngineInstall>;
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
    return value as PendingKnowledgeEngineInstall;
  } catch {
    return null;
  }
}

function writePendingKnowledgeEngineInstall(
  intent: PendingKnowledgeEngineInstall,
) {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(
    installIntentStorageKey(intent.scope),
    JSON.stringify(intent),
  );
  emitInstallIntentChange(intent.scope);
}

export function clearPendingKnowledgeEngineInstall(
  scope: string,
  taskId?: number,
) {
  if (typeof window === 'undefined') return;
  const current = readPendingKnowledgeEngineInstall(scope);
  if (taskId !== undefined && current?.taskId !== taskId) return;
  sessionStorage.removeItem(installIntentStorageKey(scope));
  emitInstallIntentChange(scope);
}

export function subscribePendingKnowledgeEngineInstall(
  scope: string,
  listener: () => void,
) {
  if (typeof window === 'undefined') return () => undefined;
  const handleChange = (event: Event) => {
    const detail = (event as CustomEvent<{ scope?: string }>).detail;
    if (detail?.scope === scope) listener();
  };
  window.addEventListener(INSTALL_INTENT_EVENT, handleChange);
  return () => window.removeEventListener(INSTALL_INTENT_EVENT, handleChange);
}

export async function loadKnowledgeEngineCatalog(): Promise<KnowledgeEngineCatalog> {
  const cloudClient = await getCloudServiceClient();
  const [firstResult, installedResult] = await Promise.all([
    cloudClient.searchMarketplaceExtensions({
      query: '',
      page: 1,
      page_size: CATALOG_PAGE_SIZE,
      type_filter: 'plugin',
      component_filter: KNOWLEDGE_ENGINE_COMPONENT_FILTER,
    }),
    httpClient.getPlugins().catch(() => ({ plugins: [] })),
  ]);

  const remainingPageCount = Math.max(
    0,
    Math.ceil((firstResult.total || 0) / CATALOG_PAGE_SIZE) - 1,
  );
  const remainingResults = await Promise.all(
    Array.from({ length: remainingPageCount }, (_, index) =>
      cloudClient.searchMarketplaceExtensions({
        query: '',
        page: index + 2,
        page_size: CATALOG_PAGE_SIZE,
        type_filter: 'plugin',
        component_filter: KNOWLEDGE_ENGINE_COMPONENT_FILTER,
      }),
    ),
  );

  const marketplaceEngines = [
    ...(firstResult.plugins || []),
    ...remainingResults.flatMap((result) => result.plugins || []),
  ]
    .filter((plugin) => plugin.components?.[KNOWLEDGE_ENGINE_COMPONENT_FILTER])
    .sort((left, right) => right.install_count - left.install_count);

  return {
    marketplaceEngines,
    installedPluginIds: installedResult.plugins.map((plugin) => {
      const metadata = plugin.manifest.manifest.metadata;
      return `${metadata.author ?? ''}/${metadata.name}`;
    }),
  };
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

export async function installMarketplaceKnowledgeEngine(
  plugin: PluginV4,
  options: InstallKnowledgeEngineOptions,
): Promise<KnowledgeEngine> {
  if (!plugin.latest_version) {
    throw new KnowledgeEngineMarketplaceError('version-unavailable');
  }

  const { task_id: taskId } = await httpClient.installPluginFromMarketplace(
    plugin.author,
    plugin.name,
    plugin.latest_version,
  );
  const pending: PendingKnowledgeEngineInstall = {
    taskId,
    pluginId: knowledgeEnginePluginId(plugin),
    pluginAuthor: plugin.author,
    pluginName: plugin.name,
    pluginLabel: extractPluginLabel(plugin),
    scope: options.scope,
    startedAt: Date.now(),
  };
  writePendingKnowledgeEngineInstall(pending);
  options.onTaskCreated?.(taskId);
  return finishKnowledgeEngineInstall(pending);
}

async function finishKnowledgeEngineInstall(
  pending: PendingKnowledgeEngineInstall,
): Promise<KnowledgeEngine> {
  const installDeadline = Date.now() + INSTALL_TIMEOUT_MS;
  let installCompleted = false;
  while (true) {
    const task = await httpClient.getAsyncTask(pending.taskId);
    if (task.runtime.done) {
      if (task.runtime.exception) {
        clearPendingKnowledgeEngineInstall(pending.scope, pending.taskId);
        throw new Error(task.runtime.exception);
      }
      installCompleted = true;
      break;
    }
    if (Date.now() >= installDeadline) break;
    await wait(1000);
  }
  if (!installCompleted) {
    throw new KnowledgeEngineMarketplaceError('install-timeout');
  }

  const registrationDeadline = Date.now() + REGISTRATION_TIMEOUT_MS;
  while (Date.now() < registrationDeadline) {
    const result = await httpClient.getKnowledgeEngines();
    const engine = result.engines.find(
      (candidate) => candidate.plugin_id === pending.pluginId,
    );
    if (engine) {
      clearPendingKnowledgeEngineInstall(pending.scope, pending.taskId);
      return engine;
    }
    await wait(1000);
  }

  clearPendingKnowledgeEngineInstall(pending.scope, pending.taskId);
  throw new KnowledgeEngineMarketplaceError('registration-timeout');
}

export async function resumePendingKnowledgeEngineInstall(
  scope: string,
): Promise<KnowledgeEngine | null> {
  const pending = readPendingKnowledgeEngineInstall(scope);
  if (!pending) return null;
  return finishKnowledgeEngineInstall(pending);
}
