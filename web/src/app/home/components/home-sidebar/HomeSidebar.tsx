'use client';

import { useEffect, useState } from 'react';
import { SidebarChildVO } from '@/app/home/components/home-sidebar/HomeSidebarChild';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { sidebarConfigList } from '@/app/home/components/home-sidebar/sidbarConfigList';
import langbotIcon from '@/app/assets/langbot-logo.webp';
import { systemInfo, httpClient } from '@/app/infra/http/HttpClient';
import { getCloudServiceClientSync } from '@/app/infra/http';
import { useTranslation } from 'react-i18next';
import {
  Moon,
  Sun,
  Monitor,
  ChevronsUpDown,
  CircleHelp,
  Lightbulb,
  LogOut,
  KeyRound,
  Settings,
  Ellipsis,
  ArrowUp,
  ExternalLink,
  Trash,
  Bug,
} from 'lucide-react';
import { useTheme } from 'next-themes';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { LanguageSelector } from '@/components/ui/language-selector';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import AccountSettingsDialog from '@/app/home/components/account-settings-dialog/AccountSettingsDialog';
import ApiIntegrationDialog from '@/app/home/components/api-integration-dialog/ApiIntegrationDialog';
import NewVersionDialog from '@/app/home/components/new-version-dialog/NewVersionDialog';
import ModelsDialog from '@/app/home/components/models-dialog/ModelsDialog';
import { GitHubRelease } from '@/app/infra/http/CloudServiceClient';
import { useAsyncTask, AsyncTaskStatus } from '@/hooks/useAsyncTask';
import { toast } from 'sonner';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from '@/components/ui/sidebar';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { ChevronRight, Plus } from 'lucide-react';
import { useSidebarData, SidebarEntityItem } from './SidebarDataContext';

// Compare two version strings, returns true if v1 > v2
function compareVersions(v1: string, v2: string): boolean {
  const clean1 = v1.replace(/^v/, '');
  const clean2 = v2.replace(/^v/, '');

  const parts1 = clean1.split('.').map((p) => parseInt(p, 10) || 0);
  const parts2 = clean2.split('.').map((p) => parseInt(p, 10) || 0);

  const maxLen = Math.max(parts1.length, parts2.length);

  for (let i = 0; i < maxLen; i++) {
    const p1 = parts1[i] || 0;
    const p2 = parts2[i] || 0;
    if (p1 > p2) return true;
    if (p1 < p2) return false;
  }
  return false;
}

// IDs of sidebar entries that have collapsible entity sub-items
const ENTITY_CATEGORY_IDS = [
  'bots',
  'pipelines',
  'knowledge',
  'plugins',
] as const;
type EntityCategoryId = (typeof ENTITY_CATEGORY_IDS)[number];

// Categories that support detail pages via ?id= query param
const DETAIL_PAGE_CATEGORIES: EntityCategoryId[] = [
  'bots',
  'pipelines',
  'knowledge',
  'plugins',
];

// Categories that support creating new entities from the sidebar
const CREATABLE_CATEGORIES: EntityCategoryId[] = [
  'bots',
  'pipelines',
  'knowledge',
];

// Categories where clicking the parent only toggles collapse (no list page)
const COLLAPSIBLE_ONLY_CATEGORIES: EntityCategoryId[] = [
  'bots',
  'pipelines',
  'knowledge',
];

// Map creatable category IDs to their i18n "create" keys
const CREATE_I18N_KEYS: Partial<Record<EntityCategoryId, string>> = {
  bots: 'bots.createBot',
  pipelines: 'pipelines.createPipeline',
  knowledge: 'knowledge.createKnowledgeBase',
};

function isEntityCategory(id: string): id is EntityCategoryId {
  return (ENTITY_CATEGORY_IDS as readonly string[]).includes(id);
}

// Map sidebar config IDs to SidebarDataContext keys
const ENTITY_KEY_MAP: Record<
  EntityCategoryId,
  'bots' | 'pipelines' | 'knowledgeBases' | 'plugins'
> = {
  bots: 'bots',
  pipelines: 'pipelines',
  knowledge: 'knowledgeBases',
  plugins: 'plugins',
};

// Route prefix map for entity detail pages
const ENTITY_ROUTE_MAP: Record<EntityCategoryId, string> = {
  bots: '/home/bots',
  pipelines: '/home/pipelines',
  knowledge: '/home/knowledge',
  plugins: '/home/plugins',
};

// localStorage key for collapsible section open/closed state
const SIDEBAR_SECTIONS_KEY = 'sidebar_sections';

function loadSectionState(): Record<string, boolean> {
  if (typeof window === 'undefined') return {};
  try {
    const stored = localStorage.getItem(SIDEBAR_SECTIONS_KEY);
    return stored ? JSON.parse(stored) : {};
  } catch {
    return {};
  }
}

function saveSectionState(state: Record<string, boolean>) {
  try {
    localStorage.setItem(SIDEBAR_SECTIONS_KEY, JSON.stringify(state));
  } catch {
    // Ignore storage errors
  }
}

// Maximum number of entity sub-items visible before "More" toggle
const MAX_VISIBLE_ITEMS = 5;

// Sort entity items by updatedAt descending (most recent first), items without updatedAt go last
function sortByRecent(items: SidebarEntityItem[]): SidebarEntityItem[] {
  return [...items].sort((a, b) => {
    if (!a.updatedAt && !b.updatedAt) return 0;
    if (!a.updatedAt) return 1;
    if (!b.updatedAt) return -1;
    return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
  });
}

// Plugin operation type enum
enum PluginOperationType {
  DELETE = 'DELETE',
  UPDATE = 'UPDATE',
}

// Renders sidebar navigation items with collapsible sub-items for entity categories
function NavItems({
  selectedChild,
  onChildClick,
  section,
  sectionOpenState,
  onSectionToggle,
}: {
  selectedChild: SidebarChildVO | undefined;
  onChildClick: (child: SidebarChildVO) => void;
  section: 'home' | 'extensions';
  sectionOpenState: Record<string, boolean>;
  onSectionToggle: (id: string, open: boolean) => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sidebarData = useSidebarData();
  const { t } = useTranslation();
  // Track which entity categories have their full list expanded
  const [expandedLists, setExpandedLists] = useState<Record<string, boolean>>(
    {},
  );

  // Plugin operation state
  const [showPluginOpModal, setShowPluginOpModal] = useState(false);
  const [pluginOpType, setPluginOpType] = useState<PluginOperationType>(
    PluginOperationType.DELETE,
  );
  const [targetPluginItem, setTargetPluginItem] =
    useState<SidebarEntityItem | null>(null);
  const [deleteData, setDeleteData] = useState(false);

  const asyncTask = useAsyncTask({
    onSuccess: () => {
      const msg =
        pluginOpType === PluginOperationType.DELETE
          ? t('plugins.deleteSuccess')
          : t('plugins.updateSuccess');
      toast.success(msg);
      setShowPluginOpModal(false);
      sidebarData.refreshPlugins();
    },
  });

  function handlePluginDelete(item: SidebarEntityItem) {
    setTargetPluginItem(item);
    setPluginOpType(PluginOperationType.DELETE);
    setDeleteData(false);
    asyncTask.reset();
    setShowPluginOpModal(true);
  }

  function handlePluginUpdate(item: SidebarEntityItem) {
    setTargetPluginItem(item);
    setPluginOpType(PluginOperationType.UPDATE);
    asyncTask.reset();
    setShowPluginOpModal(true);
  }

  function executePluginOperation() {
    if (!targetPluginItem) return;
    const slashIdx = targetPluginItem.id.indexOf('/');
    const author =
      slashIdx >= 0 ? targetPluginItem.id.substring(0, slashIdx) : '';
    const name =
      slashIdx >= 0
        ? targetPluginItem.id.substring(slashIdx + 1)
        : targetPluginItem.id;

    const apiCall =
      pluginOpType === PluginOperationType.DELETE
        ? httpClient.removePlugin(author, name, deleteData)
        : httpClient.upgradePlugin(author, name);

    apiCall
      .then((res) => {
        asyncTask.startTask(res.task_id);
      })
      .catch((error) => {
        const errorMessage =
          pluginOpType === PluginOperationType.DELETE
            ? t('plugins.deleteError') + error.message
            : t('plugins.updateError') + error.message;
        toast.error(errorMessage);
      });
  }

  const sectionItems = sidebarConfigList.filter((c) => c.section === section);

  return (
    <>
      {sectionItems.map((config) => {
        if (!isEntityCategory(config.id)) {
          // Non-entity entries (e.g. monitoring, market, mcp) render as plain links
          return (
            <SidebarMenuItem key={config.id}>
              <SidebarMenuButton
                isActive={selectedChild?.id === config.id}
                onClick={() => onChildClick(config)}
                tooltip={config.name}
              >
                {config.icon}
                <span>{config.name}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          );
        }

        // Entity categories: collapsible with sub-items
        const entityKey = ENTITY_KEY_MAP[config.id];
        const items: SidebarEntityItem[] = sidebarData[entityKey];
        const routePrefix = ENTITY_ROUTE_MAP[config.id];
        const hasDetailPages = DETAIL_PAGE_CATEGORIES.includes(config.id);
        const canCreate = CREATABLE_CATEGORIES.includes(config.id);
        const isCollapseOnly = COLLAPSIBLE_ONLY_CATEGORIES.includes(config.id);
        const isPlugin = config.id === 'plugins';
        const isActive =
          selectedChild?.id === config.id ||
          pathname === routePrefix ||
          pathname.startsWith(routePrefix + '/');

        // Use stored open state if available, otherwise default to active state
        const isOpen = sectionOpenState[config.id] ?? isActive;

        return (
          <Collapsible
            key={config.id}
            asChild
            open={isOpen}
            onOpenChange={(open) => onSectionToggle(config.id, open)}
            className="group/collapsible"
          >
            <SidebarMenuItem>
              <SidebarMenuButton
                isActive={isActive}
                onClick={() => {
                  if (isCollapseOnly) {
                    onSectionToggle(config.id, !isOpen);
                  } else {
                    onChildClick(config);
                  }
                }}
                tooltip={config.name}
              >
                {config.icon}
                <span>{config.name}</span>
                <CollapsibleTrigger asChild>
                  <button
                    type="button"
                    className="ml-auto p-1 -mr-1 rounded-sm hover:bg-sidebar-accent"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ChevronRight className="size-4 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                  </button>
                </CollapsibleTrigger>
              </SidebarMenuButton>
              <CollapsibleContent>
                <SidebarMenuSub>
                  {(() => {
                    const sortedItems = sortByRecent(items);
                    const isExpanded = expandedLists[config.id] ?? false;
                    const visibleItems =
                      sortedItems.length > MAX_VISIBLE_ITEMS && !isExpanded
                        ? sortedItems.slice(0, MAX_VISIBLE_ITEMS)
                        : sortedItems;
                    const hiddenCount = sortedItems.length - MAX_VISIBLE_ITEMS;

                    return (
                      <>
                        {visibleItems.map((item) => {
                          // Plugins navigate to the list page; others use ?id= query param
                          const itemRoute = hasDetailPages
                            ? `${routePrefix}?id=${encodeURIComponent(item.id)}`
                            : routePrefix;
                          const isItemActive =
                            hasDetailPages &&
                            pathname === routePrefix &&
                            searchParams.get('id') === item.id;
                          return (
                            <SidebarMenuSubItem
                              key={item.id}
                              className={
                                isPlugin ? 'group/plugin-item relative' : ''
                              }
                            >
                              <SidebarMenuSubButton
                                asChild
                                isActive={isItemActive}
                              >
                                <a
                                  href={itemRoute}
                                  className={
                                    isPlugin && !item.debug ? 'pr-6' : ''
                                  }
                                  onClick={(e) => {
                                    e.preventDefault();
                                    router.push(itemRoute);
                                  }}
                                >
                                  {item.emoji ? (
                                    <span className="text-sm shrink-0">
                                      {item.emoji}
                                    </span>
                                  ) : item.iconURL ? (
                                    <img
                                      src={item.iconURL}
                                      alt=""
                                      className="size-4 rounded shrink-0"
                                    />
                                  ) : null}
                                  <span className="truncate">{item.name}</span>
                                  {item.debug && (
                                    <Bug className="size-3.5 shrink-0 text-orange-400" />
                                  )}
                                </a>
                              </SidebarMenuSubButton>
                              {/* Plugin context menu - shown on hover (not for debug plugins) */}
                              {isPlugin && !item.debug && (
                                <PluginItemMenu
                                  item={item}
                                  onUpdate={() => handlePluginUpdate(item)}
                                  onDelete={() => handlePluginDelete(item)}
                                />
                              )}
                            </SidebarMenuSubItem>
                          );
                        })}
                        {/* Show more / less toggle when items exceed limit */}
                        {sortedItems.length > MAX_VISIBLE_ITEMS && (
                          <SidebarMenuSubItem>
                            <SidebarMenuSubButton
                              asChild
                              className="text-muted-foreground"
                            >
                              <button
                                type="button"
                                onClick={() =>
                                  setExpandedLists((prev) => ({
                                    ...prev,
                                    [config.id]: !isExpanded,
                                  }))
                                }
                              >
                                <span className="text-xs">
                                  {isExpanded
                                    ? t('common.less')
                                    : t('common.more', { count: hiddenCount })}
                                </span>
                              </button>
                            </SidebarMenuSubButton>
                          </SidebarMenuSubItem>
                        )}
                      </>
                    );
                  })()}
                  {/* Create new entity entry (only for creatable categories) */}
                  {canCreate && (
                    <SidebarMenuSubItem>
                      <SidebarMenuSubButton
                        asChild
                        isActive={
                          pathname === routePrefix &&
                          searchParams.get('id') === 'new'
                        }
                      >
                        <a
                          href={`${routePrefix}?id=new`}
                          onClick={(e) => {
                            e.preventDefault();
                            router.push(`${routePrefix}?id=new`);
                          }}
                        >
                          <Plus className="size-4" />
                          <span>{t(CREATE_I18N_KEYS[config.id] ?? '')}</span>
                        </a>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                  )}
                </SidebarMenuSub>
              </CollapsibleContent>
            </SidebarMenuItem>
          </Collapsible>
        );
      })}

      {/* Plugin operation confirmation dialog */}
      <Dialog
        open={showPluginOpModal}
        onOpenChange={(open) => {
          if (!open) {
            setShowPluginOpModal(false);
            setTargetPluginItem(null);
            asyncTask.reset();
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {pluginOpType === PluginOperationType.DELETE
                ? t('plugins.deleteConfirm')
                : t('plugins.updateConfirm')}
            </DialogTitle>
          </DialogHeader>
          <DialogDescription>
            {asyncTask.status === AsyncTaskStatus.WAIT_INPUT && (
              <div className="flex flex-col gap-4">
                <div>
                  {(() => {
                    const slashIdx = targetPluginItem?.id.indexOf('/') ?? -1;
                    const author =
                      slashIdx >= 0
                        ? targetPluginItem!.id.substring(0, slashIdx)
                        : '';
                    const name =
                      slashIdx >= 0
                        ? targetPluginItem!.id.substring(slashIdx + 1)
                        : targetPluginItem?.id ?? '';
                    return pluginOpType === PluginOperationType.DELETE
                      ? t('plugins.confirmDeletePlugin', { author, name })
                      : t('plugins.confirmUpdatePlugin', { author, name });
                  })()}
                </div>
                {pluginOpType === PluginOperationType.DELETE && (
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="sidebar-delete-data"
                      checked={deleteData}
                      onCheckedChange={(checked) =>
                        setDeleteData(checked === true)
                      }
                    />
                    <label
                      htmlFor="sidebar-delete-data"
                      className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                    >
                      {t('plugins.deleteDataCheckbox')}
                    </label>
                  </div>
                )}
              </div>
            )}
            {asyncTask.status === AsyncTaskStatus.RUNNING && (
              <div>
                {pluginOpType === PluginOperationType.DELETE
                  ? t('plugins.deleting')
                  : t('plugins.updating')}
              </div>
            )}
            {asyncTask.status === AsyncTaskStatus.ERROR && (
              <div>
                {pluginOpType === PluginOperationType.DELETE
                  ? t('plugins.deleteError')
                  : t('plugins.updateError')}
                <div className="text-red-500">{asyncTask.error}</div>
              </div>
            )}
          </DialogDescription>
          <DialogFooter>
            {asyncTask.status === AsyncTaskStatus.WAIT_INPUT && (
              <Button
                variant="outline"
                onClick={() => {
                  setShowPluginOpModal(false);
                  setTargetPluginItem(null);
                  asyncTask.reset();
                }}
              >
                {t('common.cancel')}
              </Button>
            )}
            {asyncTask.status === AsyncTaskStatus.WAIT_INPUT && (
              <Button
                variant={
                  pluginOpType === PluginOperationType.DELETE
                    ? 'destructive'
                    : 'default'
                }
                onClick={executePluginOperation}
              >
                {pluginOpType === PluginOperationType.DELETE
                  ? t('plugins.confirmDelete')
                  : t('plugins.confirmUpdate')}
              </Button>
            )}
            {asyncTask.status === AsyncTaskStatus.RUNNING && (
              <Button
                variant={
                  pluginOpType === PluginOperationType.DELETE
                    ? 'destructive'
                    : 'default'
                }
                disabled
              >
                {pluginOpType === PluginOperationType.DELETE
                  ? t('plugins.deleting')
                  : t('plugins.updating')}
              </Button>
            )}
            {asyncTask.status === AsyncTaskStatus.ERROR && (
              <Button
                variant="default"
                onClick={() => {
                  setShowPluginOpModal(false);
                  asyncTask.reset();
                }}
              >
                {t('plugins.close')}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// Dropdown menu for plugin sidebar sub-items (shown on hover)
function PluginItemMenu({
  item,
  onUpdate,
  onDelete,
}: {
  item: SidebarEntityItem;
  onUpdate: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const isMarketplace = item.installSource === 'marketplace';
  const isGithub = item.installSource === 'github';
  const hasSourceLink = isMarketplace || isGithub;

  function handleViewSource() {
    const slashIdx = item.id.indexOf('/');
    const author = slashIdx >= 0 ? item.id.substring(0, slashIdx) : '';
    const name = slashIdx >= 0 ? item.id.substring(slashIdx + 1) : item.id;

    if (isGithub && item.installInfo?.github_url) {
      window.open(item.installInfo.github_url as string, '_blank');
    } else if (isMarketplace) {
      window.open(
        getCloudServiceClientSync().getPluginMarketplaceURL(
          systemInfo.cloud_service_url,
          author,
          name,
        ),
        '_blank',
      );
    }
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={`absolute right-1 top-1/2 -translate-y-1/2 rounded-sm p-0.5 text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground ${
            open
              ? 'opacity-100'
              : item.hasUpdate
                ? 'opacity-100'
                : 'opacity-0 group-hover/plugin-item:opacity-100'
          } transition-opacity`}
          onClick={(e) => e.stopPropagation()}
        >
          <Ellipsis className="size-4" />
          {item.hasUpdate && !open && (
            <span className="absolute -top-0.5 -right-0.5 size-2 rounded-full bg-red-500" />
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="right" align="start">
        {isMarketplace && (
          <DropdownMenuItem
            className="cursor-pointer"
            onClick={() => {
              onUpdate();
              setOpen(false);
            }}
          >
            <ArrowUp className="size-4" />
            <span>{t('plugins.update')}</span>
            {item.hasUpdate && (
              <Badge className="ml-auto bg-red-500 hover:bg-red-500 text-white text-[0.6rem] px-1.5 py-0 h-4">
                {t('plugins.new')}
              </Badge>
            )}
          </DropdownMenuItem>
        )}
        {hasSourceLink && (
          <DropdownMenuItem
            className="cursor-pointer"
            onClick={() => {
              handleViewSource();
              setOpen(false);
            }}
          >
            <ExternalLink className="size-4" />
            <span>{t('plugins.viewSource')}</span>
          </DropdownMenuItem>
        )}
        <DropdownMenuItem
          className="cursor-pointer text-red-600 focus:text-red-600"
          onClick={() => {
            onDelete();
            setOpen(false);
          }}
        >
          <Trash className="size-4" />
          <span>{t('plugins.delete')}</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default function HomeSidebar({
  onSelectedChangeAction,
}: {
  onSelectedChangeAction: (sidebarChild: SidebarChildVO) => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { isMobile } = useSidebar();

  useEffect(() => {
    handleRouteChange(pathname);
  }, [pathname]);

  useEffect(() => {
    if (searchParams.get('action') === 'showModelSettings') {
      setModelsDialogOpen(true);
    }
    if (searchParams.get('action') === 'showAccountSettings') {
      setAccountSettingsOpen(true);
    }
    if (searchParams.get('action') === 'showApiIntegrationSettings') {
      setApiKeyDialogOpen(true);
    }
  }, [searchParams]);

  const [selectedChild, setSelectedChild] = useState<SidebarChildVO>();
  const [sectionOpenState, setSectionOpenState] =
    useState<Record<string, boolean>>(loadSectionState);
  const { theme, setTheme } = useTheme();
  const { t } = useTranslation();
  const [accountSettingsOpen, setAccountSettingsOpen] = useState(false);
  const [apiKeyDialogOpen, setApiKeyDialogOpen] = useState(false);
  const [latestRelease, setLatestRelease] = useState<GitHubRelease | null>(
    null,
  );
  const [hasNewVersion, setHasNewVersion] = useState(false);
  const [versionDialogOpen, setVersionDialogOpen] = useState(false);
  const [modelsDialogOpen, setModelsDialogOpen] = useState(false);
  const [userEmail, setUserEmail] = useState<string>('');

  function handleModelsDialogChange(open: boolean) {
    setModelsDialogOpen(open);
    if (open) {
      const params = new URLSearchParams(searchParams.toString());
      params.set('action', 'showModelSettings');
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    } else {
      const params = new URLSearchParams(searchParams.toString());
      params.delete('action');
      const newUrl = params.toString()
        ? `${pathname}?${params.toString()}`
        : pathname;
      router.replace(newUrl, { scroll: false });
    }
  }

  function handleAccountSettingsChange(open: boolean) {
    setAccountSettingsOpen(open);
    if (open) {
      const params = new URLSearchParams(searchParams.toString());
      params.set('action', 'showAccountSettings');
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    } else {
      const params = new URLSearchParams(searchParams.toString());
      params.delete('action');
      const newUrl = params.toString()
        ? `${pathname}?${params.toString()}`
        : pathname;
      router.replace(newUrl, { scroll: false });
    }
  }

  useEffect(() => {
    initSelect();
    if (!localStorage.getItem('token')) {
      localStorage.setItem('token', 'test-token');
      localStorage.setItem('userEmail', 'test@example.com');
    }

    const storedEmail = localStorage.getItem('userEmail');
    if (storedEmail) {
      setUserEmail(storedEmail);
    } else {
      httpClient
        .getUserInfo()
        .then((info) => {
          setUserEmail(info.user);
          localStorage.setItem('userEmail', info.user);
        })
        .catch(() => {});
    }

    getCloudServiceClientSync()
      .getLangBotReleases()
      .then((releases) => {
        if (releases && releases.length > 0) {
          const latestStable = releases.find((r) => !r.prerelease && !r.draft);
          const latest = latestStable || releases[0];
          setLatestRelease(latest);

          const currentVersion = systemInfo?.version;
          if (currentVersion && latest.tag_name) {
            const isNewer = compareVersions(latest.tag_name, currentVersion);
            setHasNewVersion(isNewer);
          }
        }
      })
      .catch((error) => {
        console.error('Failed to fetch releases:', error);
      });
  }, []);

  // Update selected state + notify parent without navigating
  function selectChild(child: SidebarChildVO) {
    setSelectedChild(child);
    onSelectedChangeAction(child);
  }

  // Toggle collapsible section open/closed with localStorage persistence
  function handleSectionToggle(id: string, open: boolean) {
    setSectionOpenState((prev) => {
      const next = { ...prev, [id]: open };
      saveSectionState(next);
      return next;
    });
  }

  // User click: update state AND navigate
  function handleChildClick(child: SidebarChildVO) {
    selectChild(child);
    router.push(child.route);
  }

  function initSelect() {
    const currentPath = pathname;
    // Match exact route or sub-routes (e.g., /home/bots/abc-123 matches /home/bots)
    const matchedChild =
      sidebarConfigList.find(
        (childConfig) => childConfig.route === currentPath,
      ) ||
      sidebarConfigList.find((childConfig) =>
        currentPath.startsWith(childConfig.route + '/'),
      );
    if (matchedChild) {
      // Route already matches — just select without navigating (preserves ?id= query params)
      selectChild(matchedChild);
    } else {
      // No match — redirect to default route
      handleChildClick(sidebarConfigList[0]);
    }
  }

  function handleRouteChange(pathname: string) {
    if (!pathname.startsWith('/home')) return;
    // Match exact route or sub-routes (entity detail pages)
    const routeSelectChild =
      sidebarConfigList.find((childConfig) => childConfig.route === pathname) ||
      sidebarConfigList.find((childConfig) =>
        pathname.startsWith(childConfig.route + '/'),
      );
    if (routeSelectChild) {
      setSelectedChild(routeSelectChild);
      onSelectedChangeAction(routeSelectChild);
    }
  }

  function handleLogout() {
    localStorage.removeItem('token');
    localStorage.removeItem('userEmail');
    window.location.href = '/login';
  }

  // Get the initial letter for user avatar
  const userInitial = userEmail ? userEmail.charAt(0).toUpperCase() : 'U';

  return (
    <>
      <Sidebar variant="inset" collapsible="icon">
        {/* Header: Logo using sidebar-07 team-switcher pattern */}
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                size="lg"
                className="cursor-default hover:bg-transparent active:bg-transparent"
                tooltip="LangBot"
              >
                <img
                  src={langbotIcon.src}
                  alt="LangBot"
                  className="size-8 rounded-lg"
                />
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">LangBot</span>
                  <div className="flex items-center gap-1.5">
                    <span className="truncate text-xs text-muted-foreground">
                      {systemInfo?.version}
                    </span>
                    {hasNewVersion && (
                      <Badge
                        onClick={() => setVersionDialogOpen(true)}
                        className="bg-red-500 hover:bg-red-600 text-white text-[0.55rem] px-1 py-0 h-3.5 cursor-pointer"
                      >
                        {t('plugins.new')}
                      </Badge>
                    )}
                  </div>
                </div>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>

        {/* Navigation items grouped by section */}
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>{t('sidebar.home')}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <NavItems
                  selectedChild={selectedChild}
                  onChildClick={handleChildClick}
                  section="home"
                  sectionOpenState={sectionOpenState}
                  onSectionToggle={handleSectionToggle}
                />
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
          <SidebarGroup>
            <SidebarGroupLabel>{t('sidebar.extensions')}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <NavItems
                  selectedChild={selectedChild}
                  onChildClick={handleChildClick}
                  section="extensions"
                  sectionOpenState={sectionOpenState}
                  onSectionToggle={handleSectionToggle}
                />
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>

        {/* Footer */}
        <SidebarFooter>
          {/* Models entry */}
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                onClick={() => handleModelsDialogChange(true)}
                tooltip={t('models.title')}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path d="M10.6144 17.7956C10.277 18.5682 9.20776 18.5682 8.8704 17.7956L7.99275 15.7854C7.21171 13.9966 5.80589 12.5726 4.0523 11.7942L1.63658 10.7219C.868536 10.381.868537 9.26368 1.63658 8.92276L3.97685 7.88394C5.77553 7.08552 7.20657 5.60881 7.97427 3.75892L8.8633 1.61673C9.19319.821767 10.2916.821765 10.6215 1.61673L11.5105 3.75894C12.2782 5.60881 13.7092 7.08552 15.5079 7.88394L17.8482 8.92276C18.6162 9.26368 18.6162 10.381 17.8482 10.7219L15.4325 11.7942C13.6789 12.5726 12.2731 13.9966 11.492 15.7854L10.6144 17.7956ZM4.53956 9.82234C6.8254 10.837 8.68402 12.5048 9.74238 14.7996 10.8008 12.5048 12.6594 10.837 14.9452 9.82234 12.6321 8.79557 10.7676 7.04647 9.74239 4.71088 8.71719 7.04648 6.85267 8.79557 4.53956 9.82234ZM19.4014 22.6899 19.6482 22.1242C20.0882 21.1156 20.8807 20.3125 21.8695 19.8732L22.6299 19.5353C23.0412 19.3526 23.0412 18.7549 22.6299 18.5722L21.9121 18.2532C20.8978 17.8026 20.0911 16.9698 19.6586 15.9269L19.4052 15.3156C19.2285 14.8896 18.6395 14.8896 18.4628 15.3156L18.2094 15.9269C17.777 16.9698 16.9703 17.8026 15.956 18.2532L15.2381 18.5722C14.8269 18.7549 14.8269 19.3526 15.2381 19.5353L15.9985 19.8732C16.9874 20.3125 17.7798 21.1156 18.2198 22.1242L18.4667 22.6899C18.6473 23.104 19.2207 23.104 19.4014 22.6899ZM18.3745 19.0469 18.937 18.4883 19.4878 19.0469 18.937 19.5898 18.3745 19.0469Z" />
                </svg>
                <span>{t('models.title')}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>

          {/* User menu using sidebar-07 nav-user DropdownMenu pattern */}
          <SidebarMenu>
            <SidebarMenuItem>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton
                    size="lg"
                    className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                    tooltip={t('common.accountOptions')}
                  >
                    <Avatar className="h-8 w-8 rounded-lg">
                      <AvatarFallback className="rounded-lg bg-primary text-primary-foreground text-xs">
                        {userInitial}
                      </AvatarFallback>
                    </Avatar>
                    <div className="grid flex-1 text-left text-sm leading-tight">
                      <span className="truncate font-medium">
                        {userEmail || t('common.accountOptions')}
                      </span>
                    </div>
                    <ChevronsUpDown className="ml-auto size-4" />
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
                  side={isMobile ? 'bottom' : 'right'}
                  align="end"
                  sideOffset={4}
                >
                  {/* User info header */}
                  <DropdownMenuLabel className="p-0 font-normal">
                    <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                      <Avatar className="h-8 w-8 rounded-lg">
                        <AvatarFallback className="rounded-lg bg-primary text-primary-foreground text-xs">
                          {userInitial}
                        </AvatarFallback>
                      </Avatar>
                      <div className="grid flex-1 text-left text-sm leading-tight">
                        <span className="truncate font-medium">
                          {userEmail || t('common.accountOptions')}
                        </span>
                      </div>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />

                  {/* Language & Theme row */}
                  <div className="flex items-center gap-2 px-1 py-1">
                    <LanguageSelector triggerClassName="flex-1" />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() =>
                        setTheme(
                          theme === 'light'
                            ? 'dark'
                            : theme === 'dark'
                              ? 'system'
                              : 'light',
                        )
                      }
                      className="h-9 w-9 shrink-0"
                    >
                      {theme === 'light' && (
                        <Sun className="h-[1.2rem] w-[1.2rem]" />
                      )}
                      {theme === 'dark' && (
                        <Moon className="h-[1.2rem] w-[1.2rem]" />
                      )}
                      {theme === 'system' && (
                        <Monitor className="h-[1.2rem] w-[1.2rem]" />
                      )}
                    </Button>
                  </div>
                  <DropdownMenuSeparator />

                  {/* Account actions */}
                  <DropdownMenuGroup>
                    <DropdownMenuItem
                      onClick={() => handleAccountSettingsChange(true)}
                    >
                      <Settings />
                      {t('account.settings')}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setApiKeyDialogOpen(true)}>
                      <KeyRound />
                      {t('common.apiIntegration')}
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                  <DropdownMenuSeparator />

                  {/* External links */}
                  <DropdownMenuGroup>
                    <DropdownMenuItem
                      onClick={() => {
                        const language =
                          localStorage.getItem('langbot_language');
                        if (language === 'zh-Hans' || language === 'zh-Hant') {
                          window.open(
                            'https://docs.langbot.app/zh/insight/guide',
                            '_blank',
                          );
                        } else {
                          window.open(
                            'https://docs.langbot.app/en/insight/guide',
                            '_blank',
                          );
                        }
                      }}
                    >
                      <CircleHelp />
                      {t('common.helpDocs')}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        window.open(
                          'https://github.com/langbot-app/LangBot/issues',
                          '_blank',
                        );
                      }}
                    >
                      <Lightbulb />
                      {t('common.featureRequest')}
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                  <DropdownMenuSeparator />

                  {/* Logout */}
                  <DropdownMenuItem onClick={() => handleLogout()}>
                    <LogOut />
                    {t('common.logout')}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>

      <AccountSettingsDialog
        open={accountSettingsOpen}
        onOpenChange={handleAccountSettingsChange}
      />
      <ApiIntegrationDialog
        open={apiKeyDialogOpen}
        onOpenChange={setApiKeyDialogOpen}
      />
      <NewVersionDialog
        open={versionDialogOpen}
        onOpenChange={setVersionDialogOpen}
        release={latestRelease}
      />
      <ModelsDialog
        open={modelsDialogOpen}
        onOpenChange={handleModelsDialogChange}
      />
    </>
  );
}
