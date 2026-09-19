import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { BookOpen, ExternalLink, Loader2, Store } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import { AuthenticatedPluginIcon } from '@/components/AuthenticatedPluginIcon';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { KnowledgeEngine } from '@/app/infra/entities/api';
import type { PluginV4 } from '@/app/infra/entities/plugin';
import { getCloudServiceClientSync } from '@/app/infra/http';
import { extractI18nObject } from '@/i18n/I18nProvider';
import {
  InstallStage,
  usePluginInstallTasks,
} from '@/app/home/plugins/components/plugin-install-task';
import MarketplaceInstallButton from '@/app/home/components/MarketplaceInstallButton';
import {
  KnowledgeEngineMarketplaceError,
  getKnowledgeEngineInstallError,
  installMarketplaceKnowledgeEngine,
  knowledgeEnginePluginId,
  loadKnowledgeEngineCatalog,
  readPendingKnowledgeEngineInstall,
  resumePendingKnowledgeEngineInstall,
  subscribePendingKnowledgeEngineInstall,
} from './knowledge-engine-marketplace';

const KNOWLEDGE_ENGINE_MARKETPLACE_URL =
  'https://space.langbot.app/market?type=plugin&component=KnowledgeEngine';

function installErrorMessage(
  error: unknown,
  t: ReturnType<typeof useTranslation>['t'],
) {
  if (error instanceof KnowledgeEngineMarketplaceError) {
    if (error.code === 'version-unavailable') {
      return t('knowledge.engineVersionUnavailable');
    }
    if (error.code === 'install-timeout') {
      return t('knowledge.engineInstallTimeout');
    }
    return t('knowledge.engineRegistrationTimeout');
  }
  return (
    getKnowledgeEngineInstallError(error) || t('knowledge.engineInstallFailed')
  );
}

function InstalledEngineContent({ engine }: { engine: KnowledgeEngine }) {
  const [author, name] = engine.plugin_id.split('/');
  const description = engine.description
    ? extractI18nObject(engine.description)
    : '';

  return (
    <span className="grid w-full min-w-0 grid-cols-[1.5rem_minmax(0,1fr)] items-center gap-x-2">
      {author && name ? (
        <AuthenticatedPluginIcon
          author={author}
          name={name}
          className="row-span-2 size-5 rounded object-cover"
        />
      ) : (
        <BookOpen className="row-span-2 size-4 text-muted-foreground" />
      )}
      <span className="truncate font-medium leading-5">
        {extractI18nObject(engine.name) || engine.plugin_id}
      </span>
      <span
        className="truncate text-xs leading-4 text-muted-foreground"
        title={description || engine.plugin_id}
      >
        {description || engine.plugin_id}
      </span>
    </span>
  );
}

function SelectedEngineContent({ engine }: { engine: KnowledgeEngine }) {
  const [author, name] = engine.plugin_id.split('/');

  return (
    <span className="flex min-w-0 flex-1 items-center gap-2 text-left">
      {author && name ? (
        <AuthenticatedPluginIcon
          author={author}
          name={name}
          className="size-5 shrink-0 rounded object-cover"
        />
      ) : (
        <BookOpen className="size-4 shrink-0 text-muted-foreground" />
      )}
      <span className="truncate font-medium">
        {extractI18nObject(engine.name) || engine.plugin_id}
      </span>
    </span>
  );
}

function MarketplaceEngineContent({
  plugin,
  installing,
  progress,
  installDisabled,
  installLabel,
  onInstall,
}: {
  plugin: PluginV4;
  installing: boolean;
  progress: number;
  installDisabled: boolean;
  installLabel: string;
  onInstall: () => void;
}) {
  const iconURL = getCloudServiceClientSync().resolveMarketplaceIconURL(
    plugin.type,
    plugin.author,
    plugin.name,
    plugin.icon,
  );
  const description =
    extractI18nObject(plugin.description) || `${plugin.author}/${plugin.name}`;

  return (
    <div className="grid w-full min-w-0 grid-cols-[1.75rem_minmax(0,1fr)_4rem] items-center gap-x-2 rounded-sm px-2 py-1.5 hover:bg-accent focus-within:bg-accent">
      <img
        src={iconURL}
        alt=""
        className="row-span-2 size-7 rounded-md object-cover"
      />
      <span className="truncate font-medium leading-5">
        {extractI18nObject(plugin.label) || plugin.name}
      </span>
      <MarketplaceInstallButton
        installing={installing}
        progress={progress}
        disabled={installDisabled}
        label={installLabel}
        onInstall={onInstall}
      />
      <span
        className="truncate text-xs leading-4 text-muted-foreground"
        title={description}
      >
        {description}
      </span>
    </div>
  );
}

export default function KnowledgeEngineSelect({
  engines,
  value,
  disabled = false,
  loading = false,
  installScope,
  onValueChange,
  onInstalled,
}: {
  engines: KnowledgeEngine[];
  value: string;
  disabled?: boolean;
  loading?: boolean;
  installScope: string;
  onValueChange: (value: string) => void;
  onInstalled: (engine: KnowledgeEngine) => void;
}) {
  const { t } = useTranslation();
  const { addTask, tasks } = usePluginInstallTasks();
  const [marketplaceEngines, setMarketplaceEngines] = useState<PluginV4[]>([]);
  const [installedPluginIds, setInstalledPluginIds] = useState<string[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState(false);
  const [pendingInstall, setPendingInstall] = useState(() =>
    readPendingKnowledgeEngineInstall(installScope),
  );
  const [installError, setInstallError] = useState<string | null>(null);
  const [installingPluginId, setInstallingPluginId] = useState<string | null>(
    null,
  );
  const activeInstallRef = useRef(false);
  const resumedTaskRef = useRef<number | null>(null);
  const mountedRef = useRef(true);

  const loadCatalog = useCallback(async () => {
    setCatalogLoading(true);
    setCatalogError(false);
    try {
      const catalog = await loadKnowledgeEngineCatalog();
      if (!mountedRef.current) return;
      setMarketplaceEngines(catalog.marketplaceEngines);
      setInstalledPluginIds(catalog.installedPluginIds);
    } catch (error) {
      console.error('Failed to load KnowledgeEngine catalog', error);
      if (mountedRef.current) setCatalogError(true);
    } finally {
      if (mountedRef.current) setCatalogLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  useEffect(() => {
    const syncPendingInstall = () =>
      setPendingInstall(readPendingKnowledgeEngineInstall(installScope));
    syncPendingInstall();
    return subscribePendingKnowledgeEngineInstall(
      installScope,
      syncPendingInstall,
    );
  }, [installScope]);

  useEffect(() => {
    if (
      !pendingInstall ||
      activeInstallRef.current ||
      resumedTaskRef.current === pendingInstall.taskId
    ) {
      return;
    }

    resumedTaskRef.current = pendingInstall.taskId;
    void resumePendingKnowledgeEngineInstall(installScope)
      .then(async (engine) => {
        if (!engine || !mountedRef.current) return;
        onInstalled(engine);
        await loadCatalog();
        toast.success(
          t('knowledge.engineInstallSuccess', {
            engine: pendingInstall.pluginLabel,
          }),
        );
      })
      .catch((error) => {
        if (!mountedRef.current) return;
        const message = installErrorMessage(error, t);
        setInstallError(message);
        toast.error(message);
      })
      .finally(() => {
        if (!mountedRef.current) return;
        const current = readPendingKnowledgeEngineInstall(installScope);
        if (!current) resumedTaskRef.current = null;
        setPendingInstall(current);
      });
  }, [installScope, loadCatalog, onInstalled, pendingInstall, t]);

  const marketplaceOptions = useMemo(
    () =>
      marketplaceEngines.filter((plugin) => {
        const pluginId = knowledgeEnginePluginId(plugin);
        if (installedPluginIds.includes(pluginId)) return false;
        return !engines.some((engine) => engine.plugin_id === pluginId);
      }),
    [engines, installedPluginIds, marketplaceEngines],
  );

  const selectedEngine = engines.find((engine) => engine.plugin_id === value);
  const activePluginId = pendingInstall?.pluginId ?? installingPluginId;
  const activeTask = pendingInstall
    ? tasks.find((task) => task.taskId === pendingInstall.taskId)
    : undefined;
  const installProgress = activePluginId
    ? activeTask
      ? activeTask.stage === InstallStage.DONE
        ? 95
        : Math.max(5, activeTask.overallProgress)
      : 5
    : 0;

  const handleValueChange = useCallback(
    (nextValue: string) => {
      setInstallError(null);
      onValueChange(nextValue);
    },
    [onValueChange],
  );

  const handleInstall = useCallback(
    async (plugin: PluginV4) => {
      const pluginId = knowledgeEnginePluginId(plugin);
      if (pendingInstall || installingPluginId) return;

      activeInstallRef.current = true;
      setInstallingPluginId(pluginId);
      setInstallError(null);
      try {
        const installed = await installMarketplaceKnowledgeEngine(plugin, {
          scope: installScope,
          onTaskCreated: (taskId) =>
            addTask({
              taskId,
              pluginName: knowledgeEnginePluginId(plugin),
              source: 'marketplace',
              extensionType: 'plugin',
            }),
        });
        onInstalled(installed);
        await loadCatalog();
        toast.success(
          t('knowledge.engineInstallSuccess', {
            engine: extractI18nObject(plugin.label) || plugin.name,
          }),
        );
      } catch (error) {
        const message = installErrorMessage(error, t);
        setInstallError(message);
        toast.error(message);
        const current = readPendingKnowledgeEngineInstall(installScope);
        if (current) resumedTaskRef.current = current.taskId;
      } finally {
        activeInstallRef.current = false;
        const current = readPendingKnowledgeEngineInstall(installScope);
        setPendingInstall(current);
        if (!current) setInstallingPluginId(null);
      }
    },
    [
      addTask,
      installScope,
      installingPluginId,
      loadCatalog,
      onInstalled,
      pendingInstall,
      t,
    ],
  );

  return (
    <div className="w-full max-w-[28rem] space-y-2">
      <Select
        value={value}
        disabled={disabled}
        onValueChange={handleValueChange}
        onOpenChange={(open) => {
          if (open && catalogError && !catalogLoading) void loadCatalog();
        }}
      >
        <SelectTrigger
          aria-label={t('knowledge.knowledgeEngine')}
          className="w-full bg-[#ffffff] text-left dark:bg-[#2a2a2e]"
        >
          {selectedEngine ? (
            <SelectedEngineContent engine={selectedEngine} />
          ) : value ? (
            <span className="flex min-w-0 items-center gap-2">
              <BookOpen className="size-4 shrink-0 text-muted-foreground" />
              <span className="truncate">{value}</span>
            </span>
          ) : loading ? (
            <span className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              {t('common.loading')}
            </span>
          ) : (
            <SelectValue placeholder={t('knowledge.selectKnowledgeEngine')} />
          )}
        </SelectTrigger>
        <SelectContent className="max-h-80 w-[var(--radix-select-trigger-width)] max-w-[calc(100vw-2rem)]">
          <SelectGroup>
            <SelectLabel className="px-2 py-1 text-[11px] font-medium">
              <span className="inline-flex items-center gap-1.5">
                <BookOpen className="size-3.5" />
                {t('knowledge.installedEngines')}
              </span>
            </SelectLabel>
            {engines.length > 0 ? (
              engines.map((engine) => (
                <SelectItem
                  key={engine.plugin_id}
                  value={engine.plugin_id}
                  className="py-1.5 [&>span:last-child]:min-w-0 [&>span:last-child]:flex-1"
                >
                  <InstalledEngineContent engine={engine} />
                </SelectItem>
              ))
            ) : (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">
                {loading
                  ? t('common.loading')
                  : t('knowledge.noInstalledEngines')}
              </div>
            )}
          </SelectGroup>

          <SelectSeparator />

          <SelectGroup>
            <SelectLabel className="flex items-center justify-between gap-2 px-2 py-1 text-[11px] font-medium">
              <span className="inline-flex min-w-0 items-center gap-1.5">
                <Store className="size-3.5" />
                {t('knowledge.marketplaceEngines')}
              </span>
              <a
                href={KNOWLEDGE_ENGINE_MARKETPLACE_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium text-foreground hover:bg-accent"
                onPointerDown={(event) => event.stopPropagation()}
                onClick={(event) => event.stopPropagation()}
              >
                {t('knowledge.viewMarketplace')}
                <ExternalLink className="size-3" />
              </a>
            </SelectLabel>
            {catalogLoading && marketplaceOptions.length === 0 ? (
              <div className="flex items-center gap-2 px-2 py-1.5 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" />
                {t('knowledge.loadingEngineCatalog')}
              </div>
            ) : catalogError ? (
              <div className="px-2 py-1.5 text-xs text-destructive">
                {t('knowledge.engineCatalogUnavailable')}
              </div>
            ) : marketplaceOptions.length > 0 ? (
              marketplaceOptions.map((plugin) => {
                const pluginId = knowledgeEnginePluginId(plugin);
                const pluginLabel =
                  extractI18nObject(plugin.label) || plugin.name;
                return (
                  <MarketplaceEngineContent
                    key={pluginId}
                    plugin={plugin}
                    installing={activePluginId === pluginId}
                    progress={installProgress}
                    installDisabled={
                      activePluginId !== null && activePluginId !== pluginId
                    }
                    installLabel={`${t('plugins.install')} ${pluginLabel}`}
                    onInstall={() => void handleInstall(plugin)}
                  />
                );
              })
            ) : (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">
                {t('knowledge.noMarketplaceEngines')}
              </div>
            )}
          </SelectGroup>
        </SelectContent>
      </Select>

      {installError && (
        <p role="alert" className="text-sm text-destructive">
          {installError}
        </p>
      )}
    </div>
  );
}
