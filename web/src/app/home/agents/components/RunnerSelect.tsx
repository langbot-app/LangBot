import { useCallback, useEffect, useMemo, useState } from 'react';
import { Bot, Puzzle, ExternalLink, Loader2, Store } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import { getCloudServiceClientSync } from '@/app/infra/http';
import { useInstalledPluginIcon } from '@/app/infra/hooks/useInstalledPluginIcon';
import type { IDynamicFormItemOption } from '@/app/infra/entities/form/dynamic';
import type { PluginV4 } from '@/app/infra/entities/plugin';
import type { RunnerDescriptor } from '@/app/infra/entities/api';
import {
  RunnerMarketplaceError,
  getErrorMessage,
  installMarketplaceRunner,
  installMarketplaceEventProcessor,
  resumePendingEventProcessorInstall,
  loadRunnerCatalog,
  marketplacePluginId,
  runnerPluginPrefix,
  readPendingRunnerInstall,
  subscribePendingRunnerInstall,
  type RunnerCatalog,
  type InstalledRunner,
} from '@/app/home/agents/runner-marketplace';
import {
  InstallStage,
  usePluginInstallTasks,
} from '@/app/home/plugins/components/plugin-install-task';
import MarketplaceInstallButton from '@/app/home/components/MarketplaceInstallButton';
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

function installErrorMessage(
  error: unknown,
  t: ReturnType<typeof useTranslation>['t'],
) {
  if (error instanceof RunnerMarketplaceError) {
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

function pluginOptionParts(option: IDynamicFormItemOption): {
  author: string;
  name: string;
} | null {
  if (!option.name.startsWith('plugin:')) return null;
  const match = option.name.match(/^plugin:([^/]+)\/([^/]+)(?:\/|$)/);
  return match ? { author: match[1], name: match[2] } : null;
}

function InstalledRunnerContent({
  option,
  eventProcessor = false,
}: {
  option: IDynamicFormItemOption;
  eventProcessor?: boolean;
}) {
  const Icon = eventProcessor ? Puzzle : Bot;
  const parts = pluginOptionParts(option);
  const iconURL = useInstalledPluginIcon(parts?.author, parts?.name);

  return (
    <span className="flex min-w-0 items-center gap-2">
      {iconURL ? (
        <img
          src={iconURL}
          alt=""
          className="size-5 shrink-0 rounded object-cover"
        />
      ) : (
        <Icon className="size-4 shrink-0 text-muted-foreground" />
      )}
      <span className="truncate">{extractI18nObject(option.label)}</span>
    </span>
  );
}

function InstalledRunnerOptionContent({
  option,
  description,
  eventProcessor = false,
}: {
  option: IDynamicFormItemOption;
  description: string;
  eventProcessor?: boolean;
}) {
  const Icon = eventProcessor ? Puzzle : Bot;
  const parts = pluginOptionParts(option);
  const iconURL = useInstalledPluginIcon(parts?.author, parts?.name);

  return (
    <span className="grid w-full min-w-0 grid-cols-[1.75rem_minmax(0,1fr)] items-center gap-x-2 text-left">
      {iconURL ? (
        <img
          src={iconURL}
          alt=""
          className="row-span-2 size-7 shrink-0 rounded-md object-cover"
        />
      ) : (
        <Icon className="row-span-2 size-5 justify-self-center text-muted-foreground" />
      )}
      <span className="truncate font-medium leading-5">
        {extractI18nObject(option.label)}
      </span>
      <span
        className="truncate text-xs leading-4 text-muted-foreground"
        title={description}
      >
        {description}
      </span>
    </span>
  );
}

function runnerPluginId(optionName: string) {
  return optionName.match(/^plugin:([^/]+\/[^/]+)(?:\/|$)/)?.[1] ?? null;
}

function installedRunnerDescription(
  option: IDynamicFormItemOption,
  marketplaceRunners: PluginV4[],
  installedPluginDescriptions: RunnerCatalog['installedPluginDescriptions'],
) {
  const pluginId = runnerPluginId(option.name);
  if (!pluginId) return option.name;
  const marketplacePlugin = marketplaceRunners.find(
    (plugin) => marketplacePluginId(plugin) === pluginId,
  );
  return (
    (marketplacePlugin?.description
      ? extractI18nObject(marketplacePlugin.description)
      : '') ||
    (installedPluginDescriptions[pluginId]
      ? extractI18nObject(installedPluginDescriptions[pluginId])
      : '') ||
    option.name
  );
}

function MarketplaceRunnerContent({
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
        className="row-span-2 size-7 shrink-0 rounded-md object-cover"
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

export default function RunnerSelect({
  options,
  label,
  value,
  onValueChange,
  installScope,
  onInstalled,
  usage = 'agent',
  disabled = false,
  onEventProcessorInstalled,
}: {
  options: IDynamicFormItemOption[];
  label: string;
  value: string;
  onValueChange: (value: string) => void;
  installScope: string;
  onInstalled?: (installed: InstalledRunner) => void;
  usage?: 'agent' | 'event';
  disabled?: boolean;
  onEventProcessorInstalled?: (component: RunnerDescriptor) => void;
}) {
  const { t } = useTranslation();
  const { addTask, tasks } = usePluginInstallTasks();
  const [marketplaceRunners, setMarketplaceRunners] = useState<PluginV4[]>([]);
  const [installedPluginIds, setInstalledPluginIds] = useState<string[]>([]);
  const [installedPluginDescriptions, setInstalledPluginDescriptions] =
    useState<RunnerCatalog['installedPluginDescriptions']>({});
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState(false);
  const [pendingInstall, setPendingInstall] = useState(() =>
    readPendingRunnerInstall(installScope),
  );
  const [installError, setInstallError] = useState<string | null>(null);
  const [installingPluginId, setInstallingPluginId] = useState<string | null>(
    null,
  );

  const loadCatalog = useCallback(async () => {
    setCatalogLoading(true);
    setCatalogError(false);
    try {
      const catalog = await loadRunnerCatalog(usage);
      setMarketplaceRunners(catalog.marketplaceRunners);
      setInstalledPluginIds(catalog.installedPluginIds);
      setInstalledPluginDescriptions(catalog.installedPluginDescriptions);
    } catch (error) {
      console.error('Failed to load Runner catalog', error);
      setCatalogError(true);
    } finally {
      setCatalogLoading(false);
    }
  }, [usage]);

  useEffect(() => {
    if (
      usage !== 'event' ||
      disabled ||
      !readPendingRunnerInstall(installScope)
    )
      return;
    let cancelled = false;
    void resumePendingEventProcessorInstall(installScope)
      .then((component) => {
        if (!cancelled && component) {
          onEventProcessorInstalled?.(component);
          void loadCatalog();
        }
      })
      .catch((error) => {
        if (!cancelled) setInstallError(installErrorMessage(error, t));
      });
    return () => {
      cancelled = true;
    };
  }, [
    installScope,
    usage,
    disabled,
    onEventProcessorInstalled,
    loadCatalog,
    t,
  ]);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  useEffect(() => {
    const syncPendingInstall = () =>
      setPendingInstall(readPendingRunnerInstall(installScope));
    syncPendingInstall();
    return subscribePendingRunnerInstall(installScope, syncPendingInstall);
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
      const pluginId = marketplacePluginId(plugin);
      if (disabled || pendingInstall || installingPluginId) return;

      setInstallingPluginId(pluginId);
      setInstallError(null);
      try {
        const installOptions = {
          scope: installScope,
          onTaskCreated: (taskId: number) =>
            addTask({
              taskId,
              pluginName: marketplacePluginId(plugin),
              source: 'marketplace',
              extensionType: 'plugin',
            }),
        };
        if (usage === 'event') {
          onEventProcessorInstalled?.(
            await installMarketplaceEventProcessor(plugin, installOptions),
          );
        } else {
          onInstalled?.(await installMarketplaceRunner(plugin, installOptions));
        }
        await loadCatalog();
        toast.success(
          t('agents.runnerInstallSuccess', {
            runner: extractI18nObject(plugin.label) || plugin.name,
          }),
        );
      } catch (error) {
        const message = installErrorMessage(error, t);
        setInstallError(message);
        toast.error(message);
      } finally {
        const current = readPendingRunnerInstall(installScope);
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
      usage,
      disabled,
      onEventProcessorInstalled,
    ],
  );

  return (
    <div className="w-full max-w-[22rem] space-y-2">
      <Select
        disabled={disabled}
        value={value}
        onValueChange={handleValueChange}
        onOpenChange={(open) => {
          if (open && catalogError && !catalogLoading) void loadCatalog();
        }}
      >
        <SelectTrigger
          aria-label={label}
          className="w-full bg-[#ffffff] dark:bg-[#2a2a2e]"
        >
          {selectedOption ? (
            <InstalledRunnerContent
              option={selectedOption}
              eventProcessor={usage === 'event'}
            />
          ) : (
            <SelectValue
              placeholder={t(
                usage === 'event'
                  ? 'agents.eventProcessor.selectComponent'
                  : 'common.select',
              )}
            />
          )}
        </SelectTrigger>
        <SelectContent className="z-[70] max-h-72 w-[var(--radix-select-trigger-width)] max-w-[calc(100vw-2rem)]">
          <SelectGroup>
            <SelectLabel className="px-2 py-1 text-[11px] font-medium">
              <span className="inline-flex items-center gap-1.5">
                {usage === 'event' ? (
                  <Puzzle className="size-3.5" />
                ) : (
                  <Bot className="size-3.5" />
                )}
                {t(
                  usage === 'event'
                    ? 'plugins.installed'
                    : 'agents.installedRunners',
                )}
              </span>
            </SelectLabel>
            {options.length > 0 ? (
              options.map((option) => {
                const description = installedRunnerDescription(
                  option,
                  marketplaceRunners,
                  installedPluginDescriptions,
                );
                return (
                  <SelectItem
                    key={option.name}
                    value={option.name}
                    className="py-1.5 [&>span:last-child]:min-w-0 [&>span:last-child]:flex-1"
                  >
                    <InstalledRunnerOptionContent
                      option={option}
                      eventProcessor={usage === 'event'}
                      description={description}
                    />
                  </SelectItem>
                );
              })
            ) : (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">
                {t(
                  usage === 'event'
                    ? 'agents.eventProcessor.noComponents'
                    : 'agents.noInstalledRunners',
                )}
              </div>
            )}
          </SelectGroup>

          <SelectSeparator />

          <SelectGroup>
            <SelectLabel className="flex items-center justify-between gap-2 px-2 py-1 text-[11px] font-medium">
              <span className="inline-flex min-w-0 items-center gap-1.5">
                <Store className="size-3.5" />
                {t(
                  usage === 'event'
                    ? 'plugins.marketplace'
                    : 'agents.marketplaceRunners',
                )}
              </span>
              <a
                href={`https://space.langbot.app/market?type=plugin&component=Runner&runner_usage=${usage}`}
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
              marketplaceOptions.map((plugin) => {
                const pluginId = marketplacePluginId(plugin);
                const pluginLabel =
                  extractI18nObject(plugin.label) || plugin.name;
                return (
                  <MarketplaceRunnerContent
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
                {t('wizard.aiEngine.noMarketplaceRunners')}
              </div>
            )}
          </SelectGroup>
          <SelectSeparator />
          <a
            href="https://langbot.app/docs/zh/plugin/dev/components/runner"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-sm px-2 py-2 text-xs text-muted-foreground hover:bg-accent hover:text-foreground"
            onPointerDown={(event) => event.stopPropagation()}
            onClick={(event) => event.stopPropagation()}
          >
            {t(
              usage === 'event'
                ? 'bots.routingHelp.docs'
                : 'bots.routingHelp.runnerDocs',
            )}
            <ExternalLink className="size-3" />
          </a>
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
