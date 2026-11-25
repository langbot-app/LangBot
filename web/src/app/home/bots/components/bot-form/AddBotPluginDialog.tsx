import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ExternalLink,
  Loader2,
  RefreshCcw,
  Search,
  TerminalSquare,
} from 'lucide-react';
import { toast } from 'sonner';
import type { PluginV4 } from '@/app/infra/entities/plugin';
import { getCloudServiceClientSync, httpClient } from '@/app/infra/http';
import { isNewerVersion } from '@/app/utils/versionCompare';
import { extractI18nObject } from '@/i18n/I18nProvider';
import {
  getErrorMessage,
  installMarketplaceBotPlugin,
  loadBotPluginCatalog,
  marketplacePluginId,
} from '@/app/home/agents/runner-marketplace';
import {
  InstallStage,
  usePluginInstallTasks,
} from '@/app/home/plugins/components/plugin-install-task';
import MarketplaceInstallButton from '@/app/home/components/MarketplaceInstallButton';
import { pluginComponentIconMap } from '@/app/home/plugins/components/plugin-market/PluginComponentIcons';
import { AuthenticatedPluginIcon } from '@/components/AuthenticatedPluginIcon';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const HookIcon = pluginComponentIconMap.EventListener;
const INSTALL_SCOPE = 'bot-plugins';

/** An installed plugin that can still be added to the bot. */
export interface AddablePlugin {
  id: string;
  author: string;
  name: string;
  label: string;
  description: string;
  hasCommands: boolean;
  hasHooks: boolean;
}

type KindFilter = 'all' | 'command' | 'hook';

/** "命令" / "聊天事件钩子" chips, shared by both tabs. */
export function PluginKindBadges({
  commands,
  hooks,
}: {
  commands: boolean;
  hooks: boolean;
}) {
  const { t } = useTranslation();
  return (
    <span className="flex flex-wrap gap-1">
      {commands && (
        <Badge variant="secondary" className="gap-1 text-[11px]">
          <TerminalSquare className="size-3" aria-hidden="true" />
          {t('bots.pluginHooks.kinds.command')}
        </Badge>
      )}
      {hooks && (
        <Badge variant="secondary" className="gap-1 text-[11px]">
          <HookIcon className="size-3" aria-hidden="true" />
          {t('bots.pluginHooks.kinds.hook')}
        </Badge>
      )}
    </span>
  );
}

function matches(
  filter: KindFilter,
  query: string,
  item: { hasCommands: boolean; hasHooks: boolean; text: string },
) {
  if (filter === 'command' && !item.hasCommands) return false;
  if (filter === 'hook' && !item.hasHooks) return false;
  return !query || item.text.toLowerCase().includes(query.toLowerCase());
}

/**
 * Add plugins to a bot: pick installed ones, or install from the Marketplace
 * and add in one step. Only plugins with commands or chat event hooks show.
 */
export default function AddBotPluginDialog({
  open,
  onOpenChange,
  addable,
  installed,
  onAdd,
  onInstalled,
  marketplaceOnly = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  addable: AddablePlugin[];
  /** Installed plugins: version and install source, keyed by `author/name`. */
  installed: Map<string, { version: string; source: string }>;
  onAdd: (ids: string[]) => void;
  onInstalled: (id: string) => Promise<void>;
  /** With "enable all" on there is nothing to add; only install new plugins. */
  marketplaceOnly?: boolean;
}) {
  const { t } = useTranslation();
  const { addTask, tasks } = usePluginInstallTasks();
  const [tab, setTab] = useState('installed');
  const [selected, setSelected] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<KindFilter>('all');
  const [catalog, setCatalog] = useState<PluginV4[] | null>(null);
  const [catalogError, setCatalogError] = useState(false);
  const [installing, setInstalling] = useState<{
    id: string;
    taskId?: number;
  } | null>(null);

  const [upgrading, setUpgrading] = useState<{
    id: string;
    label: string;
    taskId: number;
  } | null>(null);
  const busy = Boolean(installing || upgrading);

  const loadCatalog = useCallback(async () => {
    setCatalogError(false);
    try {
      setCatalog(await loadBotPluginCatalog());
    } catch {
      setCatalogError(true);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    setSelected([]);
    setQuery('');
    setFilter('all');
    setTab(!marketplaceOnly && addable.length ? 'installed' : 'marketplace');
    if (catalog === null) void loadCatalog();
    // Only reset when the dialog opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  /** Marketplace shows plugins not installed yet, or installed with an update. */
  function hasUpdate(plugin: PluginV4) {
    const current = installed.get(marketplacePluginId(plugin));
    return Boolean(
      current &&
      current.source === 'marketplace' &&
      isNewerVersion(plugin.latest_version, current.version),
    );
  }
  function isOffered(plugin: PluginV4) {
    return !installed.has(marketplacePluginId(plugin)) || hasUpdate(plugin);
  }

  async function upgrade(plugin: PluginV4) {
    if (busy) return;
    const id = marketplacePluginId(plugin);
    const label = extractI18nObject(plugin.label) || plugin.name;
    try {
      const { task_id: taskId } = await httpClient.upgradePlugin(
        plugin.author,
        plugin.name,
      );
      addTask({
        taskId,
        pluginName: id,
        source: 'marketplace',
        extensionType: 'plugin',
        operation: 'upgrade',
      });
      setUpgrading({ id, label, taskId });
    } catch (error) {
      toast.error(
        getErrorMessage(error) || t('bots.pluginHooks.add.updateFailed'),
      );
    }
  }

  const upgradeTask = upgrading
    ? tasks.find((item) => item.taskId === upgrading.taskId)
    : undefined;
  useEffect(() => {
    if (!upgrading || !upgradeTask) return;
    if (upgradeTask.stage === InstallStage.ERROR) {
      toast.error(upgradeTask.error || t('bots.pluginHooks.add.updateFailed'));
      setUpgrading(null);
    } else if (upgradeTask.stage === InstallStage.DONE) {
      const { id, label } = upgrading;
      void onInstalled(id).finally(() => {
        toast.success(t('bots.pluginHooks.add.updated', { plugin: label }));
        setUpgrading(null);
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [upgradeTask?.stage]);

  const installedRows = useMemo(
    () =>
      addable.filter((item) =>
        matches(filter, query, {
          hasCommands: item.hasCommands,
          hasHooks: item.hasHooks,
          text: `${item.label} ${item.id} ${item.description}`,
        }),
      ),
    [addable, filter, query],
  );
  const marketRows = useMemo(
    () =>
      (catalog ?? []).filter(
        (plugin) =>
          isOffered(plugin) &&
          matches(filter, query, {
            hasCommands: Boolean(plugin.components?.Command),
            hasHooks: Boolean(plugin.components?.EventListener),
            text: `${extractI18nObject(plugin.label)} ${marketplacePluginId(plugin)} ${extractI18nObject(plugin.description)}`,
          }),
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [catalog, filter, query, installed],
  );

  const task = installing?.taskId
    ? tasks.find((item) => item.taskId === installing.taskId)
    : undefined;
  const progress = installing
    ? task
      ? task.stage === InstallStage.DONE
        ? 95
        : Math.max(5, task.overallProgress)
      : 5
    : 0;

  async function install(plugin: PluginV4) {
    if (busy) return;
    const id = marketplacePluginId(plugin);
    const label = extractI18nObject(plugin.label) || plugin.name;
    setInstalling({ id });
    try {
      // Like inline Runner installs, whoever adds the plugin here also
      // confirms its declared permissions.
      await installMarketplaceBotPlugin(plugin, {
        scope: INSTALL_SCOPE,
        autoConfirmPermissions: true,
        onTaskCreated: (taskId) => {
          setInstalling({ id, taskId });
          addTask({
            taskId,
            pluginName: id,
            source: 'marketplace',
            extensionType: 'plugin',
          });
        },
      });
      await onInstalled(id);
      toast.success(
        t('bots.pluginHooks.add.installedAdded', { plugin: label }),
      );
    } catch (error) {
      toast.error(
        getErrorMessage(error) || t('bots.pluginHooks.add.installFailed'),
      );
    } finally {
      setInstalling(null);
    }
  }

  const filters = (
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative min-w-40 flex-1">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t('bots.pluginHooks.add.search')}
          className="h-8 pl-8"
        />
      </div>
      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        value={filter}
        onValueChange={(value) => value && setFilter(value as KindFilter)}
      >
        <ToggleGroupItem value="all" className="px-3">
          {t('bots.pluginHooks.add.all')}
        </ToggleGroupItem>
        <ToggleGroupItem value="command" className="gap-1 px-3">
          <TerminalSquare className="size-3.5" />
          {t('bots.pluginHooks.kinds.command')}
        </ToggleGroupItem>
        <ToggleGroupItem value="hook" className="gap-1 px-3">
          <HookIcon className="size-3.5" />
          {t('bots.pluginHooks.kinds.hook')}
        </ToggleGroupItem>
      </ToggleGroup>
    </div>
  );

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!busy) onOpenChange(next);
      }}
    >
      <DialogContent
        className="flex max-h-[80vh] flex-col overflow-hidden sm:max-w-2xl"
        data-testid="add-bot-plugin-dialog"
      >
        <DialogHeader>
          <DialogTitle>
            {t(
              marketplaceOnly
                ? 'bots.pluginHooks.add.installNew'
                : 'bots.pluginHooks.add.title',
            )}
          </DialogTitle>
          <DialogDescription>
            {t('bots.pluginHooks.add.description')}
          </DialogDescription>
        </DialogHeader>
        <Tabs
          value={tab}
          onValueChange={setTab}
          className="flex min-h-0 flex-1 flex-col gap-3"
        >
          <TabsList className={marketplaceOnly ? 'hidden' : 'w-full'}>
            <TabsTrigger value="installed">
              {t('bots.pluginHooks.add.installed')}
            </TabsTrigger>
            <TabsTrigger value="marketplace">
              {t('bots.pluginHooks.add.marketplace')}
            </TabsTrigger>
          </TabsList>
          {filters}
          <TabsContent
            value="installed"
            className="min-h-0 space-y-2 overflow-y-auto"
          >
            {installedRows.map((item) => (
              <label
                key={item.id}
                data-addable-plugin={item.id}
                className="flex cursor-pointer items-center gap-3 rounded-lg border p-3 hover:bg-accent"
              >
                <Checkbox
                  checked={selected.includes(item.id)}
                  onCheckedChange={(checked) =>
                    setSelected((current) =>
                      checked
                        ? [...current, item.id]
                        : current.filter((id) => id !== item.id),
                    )
                  }
                />
                <AuthenticatedPluginIcon
                  author={item.author}
                  name={item.name}
                  alt=""
                  className="size-10 shrink-0 rounded-lg border bg-muted object-cover"
                />
                <span className="min-w-0 flex-1 space-y-1">
                  <span className="block truncate font-medium">
                    {item.label}
                  </span>
                  {item.description && (
                    <span className="line-clamp-2 text-xs text-muted-foreground">
                      {item.description}
                    </span>
                  )}
                  <PluginKindBadges
                    commands={item.hasCommands}
                    hooks={item.hasHooks}
                  />
                </span>
              </label>
            ))}
            {installedRows.length === 0 && (
              <p className="py-4 text-center text-sm text-muted-foreground">
                {t('bots.pluginHooks.add.noInstalled')}
              </p>
            )}
          </TabsContent>
          <TabsContent
            value="marketplace"
            className="min-h-0 space-y-2 overflow-y-auto"
          >
            {catalogError ? (
              <button
                type="button"
                className="w-full py-4 text-center text-sm text-destructive"
                onClick={() => void loadCatalog()}
              >
                {t('bots.pluginHooks.add.unavailable')}
              </button>
            ) : catalog === null ? (
              <p className="flex items-center justify-center gap-2 py-4 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                {t('bots.pluginHooks.add.loading')}
              </p>
            ) : marketRows.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">
                {t('bots.pluginHooks.add.noMarketplace')}
              </p>
            ) : (
              marketRows.map((plugin) => {
                const id = marketplacePluginId(plugin);
                const label = extractI18nObject(plugin.label) || plugin.name;
                const description = extractI18nObject(plugin.description);
                const updatable = hasUpdate(plugin);
                const current = installed.get(id);
                return (
                  <div
                    key={id}
                    data-market-plugin={id}
                    className="flex items-center gap-3 rounded-lg border p-3"
                  >
                    <img
                      src={getCloudServiceClientSync().resolveMarketplaceIconURL(
                        plugin.type,
                        plugin.author,
                        plugin.name,
                        plugin.icon,
                      )}
                      alt=""
                      className="size-10 shrink-0 rounded-lg border bg-muted object-cover"
                    />
                    <span className="min-w-0 flex-1 space-y-1">
                      <span className="flex min-w-0 items-baseline gap-2">
                        <span className="truncate font-medium">{label}</span>
                        <span className="truncate text-xs text-muted-foreground">
                          {id}
                        </span>
                        {updatable && (
                          <Badge
                            variant="outline"
                            className="shrink-0 text-[11px] text-primary"
                          >
                            {t('bots.pluginHooks.add.updateAvailable', {
                              from: current?.version,
                              to: plugin.latest_version,
                            })}
                          </Badge>
                        )}
                      </span>
                      {description && (
                        <span className="line-clamp-2 text-xs text-muted-foreground">
                          {description}
                        </span>
                      )}
                      <PluginKindBadges
                        commands={Boolean(plugin.components?.Command)}
                        hooks={Boolean(plugin.components?.EventListener)}
                      />
                    </span>
                    {updatable ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="shrink-0 gap-1"
                        disabled={busy}
                        title={`${current?.version} → ${plugin.latest_version}`}
                        onClick={() => void upgrade(plugin)}
                      >
                        {upgrading?.id === id ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <RefreshCcw className="size-3.5" />
                        )}
                        {upgrading?.id === id && upgradeTask
                          ? `${Math.max(5, upgradeTask.overallProgress)}%`
                          : t('bots.pluginHooks.add.update')}
                      </Button>
                    ) : (
                      <MarketplaceInstallButton
                        installing={installing?.id === id}
                        progress={progress}
                        disabled={busy && installing?.id !== id}
                        label={t('bots.pluginHooks.add.installAndAdd', {
                          plugin: label,
                        })}
                        onInstall={() => void install(plugin)}
                      />
                    )}
                  </div>
                );
              })
            )}
            <a
              href="https://space.langbot.app/market?type=plugin"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-1 py-1 text-xs text-muted-foreground hover:text-foreground"
            >
              {t('bots.pluginHooks.add.viewMarketplace')}
              <ExternalLink className="size-3" />
            </a>
          </TabsContent>
        </Tabs>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => onOpenChange(false)}
          >
            {t('common.cancel')}
          </Button>
          {tab === 'installed' && (
            <Button
              type="button"
              disabled={!selected.length}
              onClick={() => {
                onAdd(selected);
                onOpenChange(false);
              }}
            >
              {t('bots.pluginHooks.add.confirm', { count: selected.length })}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
