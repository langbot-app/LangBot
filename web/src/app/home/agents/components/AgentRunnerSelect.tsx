import { useCallback, useEffect, useMemo, useState } from 'react';
import { Bot, Download, Loader2, Store } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import { getCloudServiceClientSync, httpClient } from '@/app/infra/http';
import type { IDynamicFormItemOption } from '@/app/infra/entities/form/dynamic';
import type { PipelineConfigTab } from '@/app/infra/entities/pipeline';
import type { PluginV4 } from '@/app/infra/entities/plugin';
import {
  AgentRunnerMarketplaceError,
  getErrorMessage,
  installMarketplaceAgentRunner,
  loadAgentRunnerCatalog,
  marketplacePluginId,
  runnerPluginPrefix,
} from '@/app/home/agents/agent-runner-marketplace';
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
  onMetadataRefresh,
}: {
  options: IDynamicFormItemOption[];
  label: string;
  value: string;
  onValueChange: (value: string) => void;
  onMetadataRefresh: (configTab: PipelineConfigTab) => void;
}) {
  const { t } = useTranslation();
  const [marketplaceRunners, setMarketplaceRunners] = useState<PluginV4[]>([]);
  const [installedPluginIds, setInstalledPluginIds] = useState<string[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState(false);
  const [installingPlugin, setInstallingPlugin] = useState<PluginV4 | null>(
    null,
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
      if (!plugin || installingPlugin) return;

      setInstallingPlugin(plugin);
      setInstallError(null);
      try {
        const installed = await installMarketplaceAgentRunner(plugin);
        onMetadataRefresh(installed.configTab);
        onValueChange(installed.runner.name);
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
        setInstallingPlugin(null);
      }
    },
    [
      installingPlugin,
      loadCatalog,
      marketplaceRunners,
      onMetadataRefresh,
      onValueChange,
      t,
    ],
  );

  return (
    <div className="w-full max-w-[22rem] space-y-2">
      <Select
        value={value}
        disabled={installingPlugin !== null}
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
            <SelectLabel className="px-2 py-1 text-[11px] font-medium">
              <span className="inline-flex items-center gap-1.5">
                <Store className="size-3.5" />
                {t('agents.marketplaceRunners')}
              </span>
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
