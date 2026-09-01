import { useCallback, useEffect, useMemo, useState } from 'react';
import { Bot, Download, ExternalLink, Loader2, Store } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import { getCloudServiceClientSync, httpClient } from '@/app/infra/http';
import type { IDynamicFormItemOption } from '@/app/infra/entities/form/dynamic';
import type { PluginV4 } from '@/app/infra/entities/plugin';
import {
  AgentRunnerMarketplaceError,
  getErrorMessage,
  installMarketplaceAgentRunner,
  loadAgentRunnerCatalog,
  marketplacePluginId,
  runnerPluginPrefix,
  readPendingAgentRunnerInstall,
  subscribePendingAgentRunnerInstall,
  type InstalledAgentRunner,
} from '@/app/home/agents/agent-runner-marketplace';
import { usePluginInstallTasks } from '@/app/home/plugins/components/plugin-install-task';
import { extractI18nObject } from '@/i18n/I18nProvider';
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

const MARKETPLACE_VALUE_PREFIX = '__agent_runner_marketplace__:';

function installErrorMessage(
  error: unknown,
  t: ReturnType<typeof useTranslation>['t'],
) {
  if (error instanceof AgentRunnerMarketplaceError) {
    if (error.code === 'version-unavailable') {
      return t('wizard.aiEngine.versionUnavailable');
    }
    if (error.code === 'install-timeout') {
      return t('wizard.aiEngine.installTimeout');
    }
    return t('wizard.aiEngine.registrationTimeout');
  }
  return getErrorMessage(error) || t('wizard.aiEngine.installFailed');
}

function InstalledRunnerContent({
  option,
}: {
  option: IDynamicFormItemOption;
}) {
  const iconURL = option.name.startsWith('plugin:')
    ? (() => {
        const match = option.name.match(/^plugin:([^/]+)\/([^/]+)(?:\/|$)/);
        return match ? httpClient.getPluginIconURL(match[1], match[2]) : null;
      })()
    : null;

  return (
    <span className="flex min-w-0 items-center gap-2">
      {iconURL ? (
        <img
          src={iconURL}
          alt=""
          className="size-5 shrink-0 rounded object-cover"
        />
      ) : (
        <Bot className="size-4 shrink-0 text-muted-foreground" />
      )}
      <span className="truncate">{extractI18nObject(option.label)}</span>
    </span>
  );
}

function MarketplaceRunnerContent({ plugin }: { plugin: PluginV4 }) {
  const iconURL = getCloudServiceClientSync().resolveMarketplaceIconURL(
    plugin.type,
    plugin.author,
    plugin.name,
    plugin.icon,
  );
  const description =
    extractI18nObject(plugin.description) || `${plugin.author}/${plugin.name}`;

  return (
    <span className="grid min-w-0 flex-1 grid-cols-[1.75rem_minmax(0,1fr)_auto] items-center gap-x-2">
      <img
        src={iconURL}
        alt=""
        className="row-span-2 size-7 shrink-0 rounded-md object-cover"
      />
      <span className="truncate font-medium leading-5">
        {extractI18nObject(plugin.label) || plugin.name}
      </span>
      <Download className="row-span-2 size-3.5 shrink-0 text-muted-foreground" />
      <span
        className="truncate text-xs leading-4 text-muted-foreground"
        title={description}
      >
        {description}
      </span>
    </span>
  );
}

export default function AgentRunnerSelect({
  options,
  label,
  value,
  onValueChange,
  installScope,
  onInstalled,
}: {
  options: IDynamicFormItemOption[];
  label: string;
  value: string;
  onValueChange: (value: string) => void;
  installScope: string;
  onInstalled: (installed: InstalledAgentRunner) => void;
}) {
  const { t } = useTranslation();
  const { addTask } = usePluginInstallTasks();
  const [marketplaceRunners, setMarketplaceRunners] = useState<PluginV4[]>([]);
  const [installedPluginIds, setInstalledPluginIds] = useState<string[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState(false);
  const [pendingInstall, setPendingInstall] = useState(() =>
    readPendingAgentRunnerInstall(installScope),
  );
  const [installError, setInstallError] = useState<string | null>(null);

  const loadCatalog = useCallback(async () => {
    setCatalogLoading(true);
    setCatalogError(false);
    try {
      const catalog = await loadAgentRunnerCatalog();
      setMarketplaceRunners(catalog.marketplaceRunners);
      setInstalledPluginIds(catalog.installedPluginIds);
    } catch (error) {
      console.error('Failed to load AgentRunner catalog', error);
      setCatalogError(true);
    } finally {
      setCatalogLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  useEffect(() => {
    const syncPendingInstall = () =>
      setPendingInstall(readPendingAgentRunnerInstall(installScope));
    syncPendingInstall();
    return subscribePendingAgentRunnerInstall(installScope, syncPendingInstall);
  }, [installScope]);

  const marketplaceOptions = useMemo(
    () =>
      marketplaceRunners.filter((plugin) => {
        const pluginId = marketplacePluginId(plugin);
        if (installedPluginIds.includes(pluginId)) return false;
        return !options.some((option) =>
          option.name.startsWith(runnerPluginPrefix(plugin)),
        );
      }),
    [installedPluginIds, marketplaceRunners, options],
  );

  const selectedOption = options.find((option) => option.name === value);
  const installingPlugin = pendingInstall
    ? (marketplaceRunners.find(
        (plugin) => marketplacePluginId(plugin) === pendingInstall.pluginId,
      ) ?? null)
    : null;

  const handleValueChange = useCallback(
    async (nextValue: string) => {
      if (!nextValue.startsWith(MARKETPLACE_VALUE_PREFIX)) {
        setInstallError(null);
        onValueChange(nextValue);
        return;
      }

      const pluginId = nextValue.slice(MARKETPLACE_VALUE_PREFIX.length);
      const plugin = marketplaceRunners.find(
        (candidate) => marketplacePluginId(candidate) === pluginId,
      );
      if (!plugin || pendingInstall) return;

      setInstallError(null);
      try {
        const installed = await installMarketplaceAgentRunner(plugin, {
          scope: installScope,
          onTaskCreated: (taskId) =>
            addTask({
              taskId,
              pluginName: marketplacePluginId(plugin),
              source: 'marketplace',
              extensionType: 'plugin',
            }),
        });
        onInstalled(installed);
        await loadCatalog();
        toast.success(
          t('wizard.aiEngine.installSuccess', {
            runner: extractI18nObject(plugin.label) || plugin.name,
          }),
        );
      } catch (error) {
        const message = installErrorMessage(error, t);
        setInstallError(message);
        toast.error(message);
      } finally {
        setPendingInstall(readPendingAgentRunnerInstall(installScope));
      }
    },
    [
      addTask,
      installScope,
      loadCatalog,
      marketplaceRunners,
      onInstalled,
      onValueChange,
      pendingInstall,
      t,
    ],
  );

  return (
    <div className="w-full max-w-[22rem] space-y-2">
      <Select
        value={value}
        disabled={pendingInstall !== null}
        onValueChange={(nextValue) => void handleValueChange(nextValue)}
        onOpenChange={(open) => {
          if (open && catalogError && !catalogLoading) void loadCatalog();
        }}
      >
        <SelectTrigger
          aria-label={label}
          className="w-full bg-[#ffffff] dark:bg-[#2a2a2e]"
        >
          {installingPlugin ? (
            <div className="flex min-w-0 items-center gap-2">
              <Loader2 className="size-4 shrink-0 animate-spin" />
              <span className="truncate">
                {t('agents.installingRunner', {
                  runner:
                    extractI18nObject(installingPlugin.label) ||
                    installingPlugin.name,
                })}
              </span>
            </div>
          ) : selectedOption ? (
            <InstalledRunnerContent option={selectedOption} />
          ) : (
            <SelectValue placeholder={t('common.select')} />
          )}
        </SelectTrigger>
        <SelectContent className="max-h-72 w-[var(--radix-select-trigger-width)] max-w-[calc(100vw-2rem)]">
          <SelectGroup>
            <SelectLabel className="px-2 py-1 text-[11px] font-medium">
              <span className="inline-flex items-center gap-1.5">
                <Bot className="size-3.5" />
                {t('agents.installedRunners')}
              </span>
            </SelectLabel>
            {options.length > 0 ? (
              options.map((option) => (
                <SelectItem
                  key={option.name}
                  value={option.name}
                  description={option.name}
                  className="py-1.5"
                >
                  <InstalledRunnerContent option={option} />
                </SelectItem>
              ))
            ) : (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">
                {t('agents.noInstalledRunners')}
              </div>
            )}
          </SelectGroup>

          <SelectSeparator />

          <SelectGroup>
            <SelectLabel className="flex items-center justify-between gap-2 px-2 py-1 text-[11px] font-medium">
              <span className="inline-flex min-w-0 items-center gap-1.5">
                <Store className="size-3.5" />
                {t('agents.marketplaceRunners')}
              </span>
              <a
                href="https://space.langbot.app/market?type=plugin&component=AgentRunner"
                target="_blank"
                rel="noreferrer"
                className="inline-flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium text-foreground hover:bg-accent"
                onPointerDown={(event) => event.stopPropagation()}
                onClick={(event) => event.stopPropagation()}
              >
                {t('agents.viewMarketplace')}
                <ExternalLink className="size-3" />
              </a>
            </SelectLabel>
            {catalogLoading && marketplaceOptions.length === 0 ? (
              <div className="flex items-center gap-2 px-2 py-1.5 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" />
                {t('wizard.aiEngine.loadingCatalog')}
              </div>
            ) : catalogError ? (
              <div className="px-2 py-1.5 text-xs text-destructive">
                {t('wizard.aiEngine.catalogUnavailable')}
              </div>
            ) : marketplaceOptions.length > 0 ? (
              marketplaceOptions.map((plugin) => (
                <SelectItem
                  key={marketplacePluginId(plugin)}
                  value={`${MARKETPLACE_VALUE_PREFIX}${marketplacePluginId(plugin)}`}
                  className="py-1.5 pr-8"
                >
                  <MarketplaceRunnerContent plugin={plugin} />
                </SelectItem>
              ))
            ) : (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">
                {t('wizard.aiEngine.noMarketplaceRunners')}
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
