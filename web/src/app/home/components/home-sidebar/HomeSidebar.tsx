import { useEffect, useRef, useState } from 'react';
import { SidebarChildVO } from '@/app/home/components/home-sidebar/HomeSidebarChild';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
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
  Star,
  Ellipsis,
  ArrowUp,
  ExternalLink,
  Trash,
  Bug,
  Upload,
  Store,
  Github,
  Zap,
  FilePlus2,
  Sparkles,
  HardDrive,
  Server,
  Puzzle,
  RefreshCcw,
} from 'lucide-react';
import { useTheme } from '@/components/providers/theme-provider';

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
import NewVersionDialog from '@/app/home/components/new-version-dialog/NewVersionDialog';
import SettingsDialog, {
  SettingsSection,
  SETTINGS_ACTION_BY_SECTION,
  SETTINGS_SECTION_BY_ACTION,
} from '@/app/home/components/settings-dialog/SettingsDialog';
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
import { ChevronDown, ChevronRight, Plus } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { cn } from '@/lib/utils';
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

// Discord brand glyph (lucide-react has no Discord icon).
function DiscordIcon({ className }: { className?: string }) {
  return (
    <svg
      role="img"
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z" />
    </svg>
  );
}

// IDs of sidebar entries that have collapsible entity sub-items
const ENTITY_CATEGORY_IDS = [
  'bots',
  'pipelines',
  'knowledge',
  'plugins',
  'mcp',
  'skills',
] as const;
type EntityCategoryId = (typeof ENTITY_CATEGORY_IDS)[number];

// Categories that support detail pages via ?id= query param
const DETAIL_PAGE_CATEGORIES: EntityCategoryId[] = [
  'bots',
  'pipelines',
  'knowledge',
  'plugins',
  'mcp',
  'skills',
];

// Categories that support creating new entities from the sidebar
const CREATABLE_CATEGORIES: EntityCategoryId[] = [
  'bots',
  'pipelines',
  'knowledge',
  'mcp',
  'skills',
];

// Categories where clicking the parent only toggles collapse (no list page)
const COLLAPSIBLE_ONLY_CATEGORIES: EntityCategoryId[] = [
  'bots',
  'pipelines',
  'knowledge',
  'mcp',
  'skills',
];

function isEntityCategory(id: string): id is EntityCategoryId {
  return (ENTITY_CATEGORY_IDS as readonly string[]).includes(id);
}

// Map sidebar config IDs to SidebarDataContext keys
const ENTITY_KEY_MAP: Record<
  EntityCategoryId,
  'bots' | 'pipelines' | 'knowledgeBases' | 'plugins' | 'mcpServers' | 'skills'
> = {
  bots: 'bots',
  pipelines: 'pipelines',
  knowledge: 'knowledgeBases',
  plugins: 'plugins',
  mcp: 'mcpServers',
  skills: 'skills',
};

// Route prefix map for entity detail pages
const ENTITY_ROUTE_MAP: Record<EntityCategoryId, string> = {
  bots: '/home/bots',
  pipelines: '/home/agents',
  knowledge: '/home/knowledge',
  plugins: '/home/extensions',
  mcp: '/home/mcp',
  skills: '/home/skills',
};

// localStorage key for collapsible section open/closed state
const SIDEBAR_SECTIONS_KEY = 'sidebar_sections';
const SIDEBAR_LIST_EXPANSION_KEY = 'sidebar_entity_list_expansion';
const SCROLL_HINT_BOTTOM_THRESHOLD = 40;

type SidebarNavSection = 'home' | 'extensions';
type SidebarListExpansionState = Record<
  SidebarNavSection,
  Partial<Record<EntityCategoryId, boolean>>
>;

function createEmptyListExpansionState(): SidebarListExpansionState {
  return {
    home: {},
    extensions: {},
  };
}

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

function loadListExpansionState(): SidebarListExpansionState {
  if (typeof window === 'undefined') return createEmptyListExpansionState();
  try {
    const stored = localStorage.getItem(SIDEBAR_LIST_EXPANSION_KEY);
    if (!stored) return createEmptyListExpansionState();
    const parsed = JSON.parse(stored) as Partial<SidebarListExpansionState>;
    return {
      home: parsed.home ?? {},
      extensions: parsed.extensions ?? {},
    };
  } catch {
    return createEmptyListExpansionState();
  }
}

function saveListExpansionState(state: SidebarListExpansionState) {
  try {
    localStorage.setItem(SIDEBAR_LIST_EXPANSION_KEY, JSON.stringify(state));
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

// MCP status dot color: disabled → gray, error → red, connecting → yellow, connected → green
function mcpStatusColor(item: SidebarEntityItem): string {
  if (item.enabled === false) return 'bg-muted-foreground/40';
  switch (item.runtimeStatus) {
    case 'connected':
      return 'bg-green-500';
    case 'connecting':
      return 'bg-yellow-500';
    case 'error':
      return 'bg-red-500';
    default:
      return 'bg-muted-foreground/40';
  }
}

function MCPStatusIcon({
  item,
  borderClass,
}: {
  item: SidebarEntityItem;
  borderClass: string;
}) {
  return (
    <span className="relative shrink-0">
      <Server className="size-4 !text-blue-500" />
      <span
        className={cn(
          'absolute -bottom-1 -right-1 size-3 rounded-full border-2',
          borderClass,
          mcpStatusColor(item),
        )}
      />
    </span>
  );
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
  section: SidebarNavSection;
  sectionOpenState: Record<string, boolean>;
  onSectionToggle: (id: string, open: boolean) => void;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const pathname = location.pathname;
  const [searchParams] = useSearchParams();
  const sidebarData = useSidebarData();
  const { state: sidebarState, isMobile } = useSidebar();
  const { t } = useTranslation();
  // Track which entity categories have their full list expanded
  const [expandedLists, setExpandedLists] = useState<SidebarListExpansionState>(
    loadListExpansionState,
  );
  // Track popover open state for collapsed sidebar entity categories
  const [popoverOpen, setPopoverOpen] = useState<Record<string, boolean>>({});
  // Spin state for the installed-extensions refresh button
  const [extRefreshing, setExtRefreshing] = useState(false);

  const handleRefreshExtensions = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (extRefreshing) return;
    setExtRefreshing(true);
    try {
      await Promise.all([
        sidebarData.refreshPlugins(),
        sidebarData.refreshMCPServers(),
        sidebarData.refreshSkills(),
      ]);
    } finally {
      setExtRefreshing(false);
    }
  };

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

  function handleListExpansionToggle(id: EntityCategoryId, expanded: boolean) {
    setExpandedLists(() => {
      const latest = loadListExpansionState();
      const next = {
        ...latest,
        [section]: {
          ...latest[section],
          [id]: expanded,
        },
      };
      saveListExpansionState(next);
      return next;
    });
  }

  // Persist open state for sections that become active through navigation,
  // so they remain expanded when the user switches to a different section.
  const sectionOpenRef = useRef(sectionOpenState);
  sectionOpenRef.current = sectionOpenState;
  useEffect(() => {
    sectionItems.forEach((config) => {
      if (!isEntityCategory(config.id)) return;
      const routePrefix = ENTITY_ROUTE_MAP[config.id];
      const active =
        pathname === routePrefix || pathname.startsWith(routePrefix + '/');
      if (active && sectionOpenRef.current[config.id] === undefined) {
        onSectionToggle(config.id, true);
      }
    });
  }, [pathname, sectionItems, onSectionToggle]);

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
                <span className="cursor-pointer select-none">
                  {config.name}
                </span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          );
        }

        // Entity categories: collapsible with sub-items
        const categoryId = config.id;
        const entityKey = ENTITY_KEY_MAP[categoryId];
        const isExtensionsCategory = categoryId === 'plugins';
        const items: SidebarEntityItem[] = isExtensionsCategory
          ? [
              ...sidebarData.plugins.map((p) => ({
                ...p,
                extensionType: 'plugin' as const,
              })),
              ...sidebarData.mcpServers.map((m) => ({
                ...m,
                extensionType: 'mcp' as const,
              })),
              ...sidebarData.skills.map((s) => ({
                ...s,
                extensionType: 'skill' as const,
              })),
            ]
          : sidebarData[entityKey];
        const routePrefix = ENTITY_ROUTE_MAP[categoryId];
        const hasDetailPages = DETAIL_PAGE_CATEGORIES.includes(categoryId);
        const canCreate = CREATABLE_CATEGORIES.includes(categoryId);
        const isCollapseOnly = COLLAPSIBLE_ONLY_CATEGORIES.includes(categoryId);
        const isPlugin = categoryId === 'plugins';
        const isSkill = categoryId === 'skills';
        const isBot = categoryId === 'bots';
        const isMCP = categoryId === 'mcp';

        const resolveItemRoute = (item: SidebarEntityItem): string => {
          if (item.extensionType === 'mcp') {
            return `/home/mcp?id=${encodeURIComponent(item.id)}`;
          }
          if (item.extensionType === 'skill') {
            return `/home/skills?id=${encodeURIComponent(item.id)}`;
          }
          return hasDetailPages
            ? `${routePrefix}?id=${encodeURIComponent(item.id)}`
            : routePrefix;
        };
        const isActive =
          selectedChild?.id === categoryId ||
          pathname === routePrefix ||
          pathname.startsWith(routePrefix + '/');

        // Use stored open state if available, otherwise default to active state
        const isOpen = sectionOpenState[categoryId] ?? isActive;

        // When sidebar is collapsed on desktop and category is collapse-only,
        // show a popover flyout instead of the hidden collapsible sub-items
        const isCollapsed = sidebarState === 'collapsed' && !isMobile;
        const showPopover = isCollapsed && isCollapseOnly;

        // Shared entity list renderer used by both popover and collapsible
        const renderEntityList = (inPopover: boolean) => {
          const sortedItems = isExtensionsCategory
            ? [...items].sort((a, b) =>
                a.name.localeCompare(b.name, undefined, {
                  sensitivity: 'base',
                }),
              )
            : sortByRecent(items);
          const isExpanded = expandedLists[section]?.[categoryId] ?? false;
          const maxItems = inPopover ? 10 : MAX_VISIBLE_ITEMS;
          const visibleItems =
            sortedItems.length > maxItems && !isExpanded
              ? sortedItems.slice(0, maxItems)
              : sortedItems;
          const hiddenCount = sortedItems.length - maxItems;

          if (sortedItems.length === 0) {
            return (
              <div
                className={cn(
                  'text-muted-foreground text-xs',
                  inPopover ? 'px-2 py-3 text-center' : 'px-2 py-1.5',
                )}
              >
                {t('common.noItems')}
              </div>
            );
          }

          const itemActiveCheck = (item: SidebarEntityItem): boolean => {
            if (item.extensionType === 'mcp') {
              return (
                pathname === '/home/mcp' && searchParams.get('id') === item.id
              );
            }
            if (item.extensionType === 'skill') {
              return (
                pathname === '/home/skills' &&
                searchParams.get('id') === item.id
              );
            }
            return (
              hasDetailPages &&
              pathname === routePrefix &&
              searchParams.get('id') === item.id
            );
          };

          const itemIsPlugin = (item: SidebarEntityItem): boolean =>
            isExtensionsCategory ? item.extensionType === 'plugin' : isPlugin;

          const showGroupHeaders =
            isExtensionsCategory &&
            !inPopover &&
            sidebarData.extensionsGroupByType;

          const groupOrder: Array<'plugin' | 'mcp' | 'skill'> = [
            'plugin',
            'mcp',
            'skill',
          ];
          const groupLabelKey: Record<'plugin' | 'mcp' | 'skill', string> = {
            plugin: 'market.typePlugin',
            mcp: 'market.typeMCP',
            skill: 'market.typeSkill',
          };

          const renderItem = (item: SidebarEntityItem) => {
            const itemRoute = resolveItemRoute(item);
            const isItemActive = itemActiveCheck(item);
            const itemIsPluginType = itemIsPlugin(item);
            if (inPopover) {
              return (
                <button
                  key={item.id}
                  type="button"
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-left',
                    'hover:bg-accent hover:text-accent-foreground transition-colors',
                    isItemActive &&
                      'bg-accent text-accent-foreground font-medium',
                  )}
                  onClick={() => {
                    navigate(itemRoute);
                    setPopoverOpen((prev) => ({
                      ...prev,
                      [categoryId]: false,
                    }));
                  }}
                >
                  {item.extensionType === 'mcp' ? (
                    <MCPStatusIcon item={item} borderClass="border-popover" />
                  ) : item.extensionType === 'skill' ? (
                    <Sparkles className="size-4 shrink-0 !text-blue-500" />
                  ) : item.emoji ? (
                    <span className="text-sm shrink-0">{item.emoji}</span>
                  ) : item.iconURL ? (
                    <span className="relative shrink-0">
                      <img
                        src={item.iconURL}
                        alt=""
                        className="size-4 rounded"
                      />
                      {(isBot || isMCP) && (
                        <span
                          className={cn(
                            'absolute -bottom-0.5 -right-0.5 size-2 rounded-full border-2 border-popover',
                            isMCP
                              ? mcpStatusColor(item)
                              : item.enabled === false
                                ? 'bg-muted-foreground/40'
                                : 'bg-green-500',
                          )}
                        />
                      )}
                    </span>
                  ) : item.extensionType === 'plugin' ? (
                    <Puzzle className="size-4 shrink-0 !text-blue-500" />
                  ) : isMCP ? (
                    <span
                      className={cn(
                        'size-2 shrink-0 rounded-full',
                        mcpStatusColor(item),
                      )}
                    />
                  ) : null}
                  <span className="truncate">{item.name}</span>
                </button>
              );
            }

            // Normal sidebar sub-item rendering
            return (
              <SidebarMenuSubItem
                key={item.id}
                className={itemIsPluginType ? 'group/plugin-item relative' : ''}
              >
                <Tooltip delayDuration={500}>
                  <TooltipTrigger asChild>
                    <SidebarMenuSubButton asChild isActive={isItemActive}>
                      <a
                        href={itemRoute}
                        className={cn(
                          itemIsPluginType && !item.debug ? 'pr-6' : '',
                        )}
                        onClick={(e) => {
                          e.preventDefault();
                          navigate(itemRoute);
                        }}
                      >
                        {item.extensionType === 'mcp' ? (
                          <MCPStatusIcon
                            item={item}
                            borderClass="border-sidebar"
                          />
                        ) : item.extensionType === 'skill' ? (
                          <Sparkles className="size-4 shrink-0 !text-blue-500" />
                        ) : item.emoji ? (
                          <span className="text-sm shrink-0">{item.emoji}</span>
                        ) : item.iconURL ? (
                          <span className="relative shrink-0">
                            <img
                              src={item.iconURL}
                              alt=""
                              className="size-4 rounded"
                            />
                            {(isBot || isMCP) && (
                              <span
                                className={cn(
                                  'absolute -bottom-0.5 -right-0.5 size-2 rounded-full border-2 border-sidebar',
                                  isMCP
                                    ? mcpStatusColor(item)
                                    : item.enabled === false
                                      ? 'bg-muted-foreground/40'
                                      : 'bg-green-500',
                                )}
                              />
                            )}
                          </span>
                        ) : item.extensionType === 'plugin' ? (
                          <Puzzle className="size-4 shrink-0 !text-blue-500" />
                        ) : isMCP ? (
                          <span
                            className={cn(
                              'size-2 shrink-0 rounded-full',
                              mcpStatusColor(item),
                            )}
                          />
                        ) : null}
                        <span className="truncate">{item.name}</span>
                        {item.debug && (
                          <Bug className="size-3.5 shrink-0 text-orange-400" />
                        )}
                      </a>
                    </SidebarMenuSubButton>
                  </TooltipTrigger>
                  <TooltipContent
                    side="right"
                    align="center"
                    className="max-w-64"
                  >
                    {/* Full name — so truncated sidebar items are readable on hover */}
                    <div className="break-words font-medium">{item.name}</div>
                    {item.description && (
                      <div className="mt-0.5 break-words text-xs text-muted-foreground">
                        {item.description.length > 80
                          ? item.description.slice(0, 80) + '…'
                          : item.description}
                      </div>
                    )}
                  </TooltipContent>
                </Tooltip>
                {/* Plugin context menu - shown on hover (not for debug plugins) */}
                {itemIsPluginType && !item.debug && (
                  <PluginItemMenu
                    item={item}
                    onUpdate={() => handlePluginUpdate(item)}
                    onDelete={() => handlePluginDelete(item)}
                  />
                )}
              </SidebarMenuSubItem>
            );
          };

          return (
            <>
              {showGroupHeaders
                ? groupOrder.map((type) => {
                    const groupItems = visibleItems.filter(
                      (it) => it.extensionType === type,
                    );
                    if (groupItems.length === 0) return null;
                    return (
                      <div key={type} className="flex flex-col gap-0.5 mt-0.5">
                        <div className="px-2 pt-1 pb-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-muted-foreground">
                          {t(groupLabelKey[type])}
                        </div>
                        {groupItems.map((item) => renderItem(item))}
                      </div>
                    );
                  })
                : visibleItems.map((item) => renderItem(item))}
              {/* Show more / less toggle when items exceed limit */}
              {sortedItems.length > maxItems && !inPopover && (
                <SidebarMenuSubItem>
                  <SidebarMenuSubButton
                    asChild
                    className="text-muted-foreground"
                  >
                    <button
                      type="button"
                      onClick={() =>
                        handleListExpansionToggle(categoryId, !isExpanded)
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
              {hiddenCount > 0 && inPopover && !isExpanded && (
                <button
                  type="button"
                  className="flex w-full items-center justify-center rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-accent transition-colors"
                  onClick={() => handleListExpansionToggle(categoryId, true)}
                >
                  {t('common.more', { count: hiddenCount })}
                </button>
              )}
            </>
          );
        };

        // Popover flyout for collapsed sidebar
        if (showPopover) {
          return (
            <SidebarMenuItem key={config.id}>
              <Popover
                open={popoverOpen[config.id] ?? false}
                onOpenChange={(open) =>
                  setPopoverOpen((prev) => ({ ...prev, [config.id]: open }))
                }
              >
                <PopoverTrigger asChild>
                  <SidebarMenuButton
                    isActive={isActive}
                    tooltip={config.name}
                    className="group/category-header"
                  >
                    {config.icon}
                    <span>{config.name}</span>
                  </SidebarMenuButton>
                </PopoverTrigger>
                <PopoverContent
                  side="right"
                  align="start"
                  sideOffset={8}
                  className="w-56 p-2"
                >
                  <div className="flex items-center justify-between mb-1 px-2">
                    <span className="text-sm font-medium">{config.name}</span>
                    {canCreate &&
                      (isPlugin ? (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button
                              type="button"
                              className="p-1 rounded-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
                            >
                              <Plus className="size-3.5" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            {systemInfo.enable_marketplace && (
                              <DropdownMenuItem
                                onClick={(e) => {
                                  e.stopPropagation();
                                  navigate('/home/add-extension');
                                  setPopoverOpen((prev) => ({
                                    ...prev,
                                    [config.id]: false,
                                  }));
                                }}
                              >
                                <Store className="size-4" />
                                {t('plugins.goToMarketplace')}
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate('/home/add-extension?manual=1');
                                setPopoverOpen((prev) => ({
                                  ...prev,
                                  [config.id]: false,
                                }));
                              }}
                            >
                              <Upload className="size-4" />
                              {t('plugins.uploadLocal')}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate('/home/add-extension?manual=1');
                                setPopoverOpen((prev) => ({
                                  ...prev,
                                  [config.id]: false,
                                }));
                              }}
                            >
                              <Github className="size-4" />
                              {t('plugins.installFromGithub')}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      ) : isSkill ? (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button
                              type="button"
                              className="p-1 rounded-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
                            >
                              <Plus className="size-3.5" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate('/home/skills?action=create');
                                setPopoverOpen((prev) => ({
                                  ...prev,
                                  [config.id]: false,
                                }));
                              }}
                            >
                              <FilePlus2 className="size-4" />
                              {t('skills.createManually')}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate('/home/add-extension?manual=1');
                                setPopoverOpen((prev) => ({
                                  ...prev,
                                  [config.id]: false,
                                }));
                              }}
                            >
                              <Upload className="size-4" />
                              {t('skills.uploadZip')}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate('/home/add-extension?manual=1');
                                setPopoverOpen((prev) => ({
                                  ...prev,
                                  [config.id]: false,
                                }));
                              }}
                            >
                              <Github className="size-4" />
                              {t('skills.importFromGithub')}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      ) : (
                        <button
                          type="button"
                          className="p-1 rounded-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
                          onClick={() => {
                            navigate(`${routePrefix}?id=new`);
                            setPopoverOpen((prev) => ({
                              ...prev,
                              [config.id]: false,
                            }));
                          }}
                        >
                          <Plus className="size-3.5" />
                        </button>
                      ))}
                  </div>
                  <div className="flex flex-col gap-0.5 max-h-80 overflow-y-auto">
                    {renderEntityList(true)}
                  </div>
                </PopoverContent>
              </Popover>
            </SidebarMenuItem>
          );
        }

        // Normal expanded sidebar with collapsible sub-items
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
                asChild
                isActive={false}
                tooltip={config.name}
                className="group/category-header"
              >
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    if (isCollapseOnly) {
                      onSectionToggle(config.id, !isOpen);
                    } else {
                      onChildClick(config);
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      if (isCollapseOnly) {
                        onSectionToggle(config.id, !isOpen);
                      } else {
                        onChildClick(config);
                      }
                    }
                  }}
                >
                  {config.icon}
                  <span className="cursor-pointer select-none">
                    {config.name}
                  </span>
                  <div className="ml-auto flex items-center gap-0.5 -mr-1">
                    {isExtensionsCategory && (
                      <button
                        type="button"
                        title={t('common.refresh', '刷新')}
                        className="p-1 rounded-sm text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground [@media(hover:hover)]:opacity-0 group-hover/category-header:opacity-100 transition-all"
                        onClick={handleRefreshExtensions}
                      >
                        <RefreshCcw
                          className={cn(
                            'size-3.5',
                            extRefreshing && 'animate-spin',
                          )}
                        />
                      </button>
                    )}
                    {canCreate &&
                      (isPlugin ? (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button
                              type="button"
                              className="p-1 rounded-sm text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground [@media(hover:hover)]:opacity-0 group-hover/category-header:opacity-100 transition-all"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <Plus className="size-3.5" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            {systemInfo.enable_marketplace && (
                              <DropdownMenuItem
                                onClick={(e) => {
                                  e.stopPropagation();
                                  navigate('/home/add-extension');
                                }}
                              >
                                <Store className="size-4" />
                                {t('plugins.goToMarketplace')}
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate('/home/add-extension?manual=1');
                              }}
                            >
                              <Upload className="size-4" />
                              {t('plugins.uploadLocal')}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate('/home/add-extension?manual=1');
                              }}
                            >
                              <Github className="size-4" />
                              {t('plugins.installFromGithub')}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      ) : isSkill ? (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button
                              type="button"
                              className="p-1 rounded-sm text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground [@media(hover:hover)]:opacity-0 group-hover/category-header:opacity-100 transition-all"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <Plus className="size-3.5" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate('/home/skills?action=create');
                              }}
                            >
                              <FilePlus2 className="size-4" />
                              {t('skills.createManually')}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate('/home/add-extension?manual=1');
                              }}
                            >
                              <Upload className="size-4" />
                              {t('skills.uploadZip')}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate('/home/add-extension?manual=1');
                              }}
                            >
                              <Github className="size-4" />
                              {t('skills.importFromGithub')}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      ) : (
                        <button
                          type="button"
                          className="p-1 rounded-sm text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground [@media(hover:hover)]:opacity-0 group-hover/category-header:opacity-100 transition-all"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`${routePrefix}?id=new`);
                          }}
                        >
                          <Plus className="size-3.5" />
                        </button>
                      ))}
                    <CollapsibleTrigger asChild>
                      <button
                        type="button"
                        className="p-1 rounded-sm hover:bg-sidebar-accent"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ChevronRight className="size-4 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                      </button>
                    </CollapsibleTrigger>
                  </div>
                </div>
              </SidebarMenuButton>
              <CollapsibleContent>
                <SidebarMenuSub>{renderEntityList(false)}</SidebarMenuSub>
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
                        : (targetPluginItem?.id ?? '');
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

// Plugin pages navigation section — grouped by plugin
function PluginPagesNav() {
  const { pluginPages } = useSidebarData();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();

  if (pluginPages.length === 0) return null;

  const pathname = location.pathname;
  const currentId =
    pathname === '/home/plugin-pages' ? searchParams.get('id') : null;

  // Group pages by plugin (author/name)
  const grouped = new Map<
    string,
    { label: string; iconURL: string; pages: typeof pluginPages }
  >();
  for (const page of pluginPages) {
    const key = `${page.pluginAuthor}/${page.pluginName}`;
    if (!grouped.has(key)) {
      grouped.set(key, {
        label: page.pluginLabel,
        iconURL: page.pluginIconURL,
        pages: [],
      });
    }
    grouped.get(key)!.pages.push(page);
  }

  return (
    <SidebarGroup>
      <SidebarGroupLabel title={t('sidebar.pluginPagesTooltip')}>
        {t('sidebar.pluginPages')}
      </SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {Array.from(grouped.entries()).map(
            ([pluginKey, { label, iconURL, pages }]) => {
              const hasActivePage = pages.some((p) => p.id === currentId);

              const pluginIcon = (
                <img
                  src={iconURL}
                  alt=""
                  className="size-4 rounded-sm object-cover shrink-0"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              );

              // Single page — render directly without nesting
              if (pages.length === 1) {
                const page = pages[0];
                const isActive = currentId === page.id;
                const route = `/home/plugin-pages?id=${encodeURIComponent(page.id)}`;
                return (
                  <SidebarMenuItem key={page.id}>
                    <SidebarMenuButton
                      isActive={isActive}
                      tooltip={page.name}
                      onClick={() => navigate(route)}
                      className="select-none"
                    >
                      {pluginIcon}
                      <span className="cursor-pointer">{page.name}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              }

              // Multiple pages — collapsible group
              return (
                <Collapsible
                  key={pluginKey}
                  defaultOpen={hasActivePage}
                  className="group/collapsible"
                >
                  <SidebarMenuItem>
                    <CollapsibleTrigger asChild>
                      <SidebarMenuButton
                        tooltip={label}
                        className="select-none"
                      >
                        {pluginIcon}
                        <span className="cursor-pointer">{label}</span>
                        <ChevronRight className="ml-auto size-4 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                      </SidebarMenuButton>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <SidebarMenuSub>
                        {pages.map((page) => {
                          const isActive = currentId === page.id;
                          const route = `/home/plugin-pages?id=${encodeURIComponent(page.id)}`;
                          return (
                            <SidebarMenuSubItem key={page.id}>
                              <SidebarMenuSubButton
                                isActive={isActive}
                                onClick={() => navigate(route)}
                                className="select-none"
                              >
                                <span className="cursor-pointer">
                                  {page.name}
                                </span>
                              </SidebarMenuSubButton>
                            </SidebarMenuSubItem>
                          );
                        })}
                      </SidebarMenuSub>
                    </CollapsibleContent>
                  </SidebarMenuItem>
                </Collapsible>
              );
            },
          )}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}

function findSidebarChildForPath(pathname: string): SidebarChildVO | undefined {
  const matchedChild =
    sidebarConfigList.find((childConfig) => childConfig.route === pathname) ||
    sidebarConfigList.find((childConfig) =>
      pathname.startsWith(childConfig.route + '/'),
    );
  if (matchedChild) return matchedChild;

  if (
    pathname === '/home/mcp' ||
    pathname === '/home/skills' ||
    pathname === '/home/plugin-pages' ||
    pathname.startsWith('/home/mcp/') ||
    pathname.startsWith('/home/skills/') ||
    pathname.startsWith('/home/plugin-pages/')
  ) {
    return sidebarConfigList.find(
      (childConfig) => childConfig.id === 'plugins',
    );
  }

  if (
    pathname === '/home/add-extension' ||
    pathname.startsWith('/home/add-extension/')
  ) {
    return sidebarConfigList.find(
      (childConfig) => childConfig.id === 'add-extension',
    );
  }

  return undefined;
}

export default function HomeSidebar({
  onSelectedChangeAction,
}: {
  onSelectedChangeAction: (sidebarChild: SidebarChildVO) => void;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const pathname = location.pathname;
  const [searchParams] = useSearchParams();
  const { isMobile } = useSidebar();

  useEffect(() => {
    handleRouteChange(pathname);
  }, [pathname]);

  useEffect(() => {
    const action = searchParams.get('action');
    if (action && SETTINGS_SECTION_BY_ACTION[action]) {
      setSettingsSection(SETTINGS_SECTION_BY_ACTION[action]);
      setSettingsOpen(true);
    }
  }, [searchParams]);

  const [selectedChild, setSelectedChild] = useState<SidebarChildVO>();
  const [sectionOpenState, setSectionOpenState] =
    useState<Record<string, boolean>>(loadSectionState);
  const { theme, setTheme } = useTheme();
  const { t } = useTranslation();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsSection, setSettingsSection] =
    useState<SettingsSection>('models');
  const [latestRelease, setLatestRelease] = useState<GitHubRelease | null>(
    null,
  );
  const [hasNewVersion, setHasNewVersion] = useState(false);
  const [versionDialogOpen, setVersionDialogOpen] = useState(false);
  const [userEmail, setUserEmail] = useState<string>('');
  const [starCount, setStarCount] = useState<number | null>(null);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const navigationContentRef = useRef<HTMLDivElement | null>(null);
  const [showScrollHint, setShowScrollHint] = useState(false);

  function scrollNavigationToBottom() {
    const contentEl = navigationContentRef.current;
    if (!contentEl) return;

    const maxScrollTop = contentEl.scrollHeight - contentEl.clientHeight;
    contentEl.scrollTo({
      top: maxScrollTop,
      behavior: 'smooth',
    });
    setShowScrollHint(false);

    window.setTimeout(() => {
      if (contentEl.scrollTop < maxScrollTop - 2) {
        contentEl.scrollTop = maxScrollTop;
      }
      setShowScrollHint(false);
    }, 250);
  }
  function openSettings(section: SettingsSection) {
    setSettingsSection(section);
    setSettingsOpen(true);
    const params = new URLSearchParams(searchParams.toString());
    params.set('action', SETTINGS_ACTION_BY_SECTION[section]);
    navigate(`${pathname}?${params.toString()}`, {
      preventScrollReset: true,
    });
  }

  function handleSettingsSectionChange(section: SettingsSection) {
    setSettingsSection(section);
    const params = new URLSearchParams(searchParams.toString());
    params.set('action', SETTINGS_ACTION_BY_SECTION[section]);
    navigate(`${pathname}?${params.toString()}`, {
      preventScrollReset: true,
    });
  }

  function handleSettingsOpenChange(open: boolean) {
    setSettingsOpen(open);
    if (!open) {
      const params = new URLSearchParams(searchParams.toString());
      params.delete('action');
      const newUrl = params.toString()
        ? `${pathname}?${params.toString()}`
        : pathname;
      navigate(newUrl, { preventScrollReset: true });
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

    // Cloud edition is updated centrally by the operator, so end users should
    // not see a "new version available" prompt in the sidebar. Skip the GitHub
    // release check entirely for edition=cloud.
    if (systemInfo?.edition !== 'cloud') {
      getCloudServiceClientSync()
        .getLangBotReleases()
        .then((releases) => {
          if (releases && releases.length > 0) {
            const latestStable = releases.find(
              (r) => !r.prerelease && !r.draft,
            );
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
    }

    getCloudServiceClientSync()
      .getGitHubRepoInfo()
      .then((info) => {
        if (info?.repo?.stargazers_count != null) {
          setStarCount(info.repo.stargazers_count);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const contentEl = navigationContentRef.current;
    if (!contentEl) return;

    let animationFrame = 0;
    const updateScrollHint = () => {
      cancelAnimationFrame(animationFrame);
      animationFrame = requestAnimationFrame(() => {
        const hasHiddenContent =
          contentEl.scrollTop + contentEl.clientHeight <
          contentEl.scrollHeight - SCROLL_HINT_BOTTOM_THRESHOLD;
        setShowScrollHint(hasHiddenContent);
      });
    };

    updateScrollHint();
    contentEl.addEventListener('scroll', updateScrollHint, { passive: true });

    const resizeObserver = new ResizeObserver(updateScrollHint);
    resizeObserver.observe(contentEl);
    if (contentEl.firstElementChild) {
      resizeObserver.observe(contentEl.firstElementChild);
    }

    const mutationObserver = new MutationObserver(updateScrollHint);
    mutationObserver.observe(contentEl, {
      childList: true,
      subtree: true,
      attributes: true,
    });

    window.addEventListener('resize', updateScrollHint);

    return () => {
      cancelAnimationFrame(animationFrame);
      contentEl.removeEventListener('scroll', updateScrollHint);
      resizeObserver.disconnect();
      mutationObserver.disconnect();
      window.removeEventListener('resize', updateScrollHint);
    };
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
    navigate(child.route);
  }

  function initSelect() {
    const currentPath = pathname;
    const matchedChild = findSidebarChildForPath(currentPath);
    if (matchedChild) {
      // Route already matches — just select without navigating (preserves ?id= query params)
      selectChild(matchedChild);
    } else {
      // No match — redirect to the first route under /home
      const defaultChild =
        sidebarConfigList.find((c) => c.route.startsWith('/home')) ??
        sidebarConfigList[0];
      handleChildClick(defaultChild);
    }
  }

  function handleRouteChange(pathname: string) {
    if (!pathname.startsWith('/home')) return;
    const routeSelectChild = findSidebarChildForPath(pathname);
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
                  src={langbotIcon}
                  alt="LangBot"
                  className="size-8 rounded-lg"
                />
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <div className="flex items-center gap-1.5">
                    <span className="truncate font-semibold">LangBot</span>
                    <Badge
                      variant="secondary"
                      className={`shrink-0 px-1 py-0 h-3.5 text-[0.55rem] font-medium ${
                        systemInfo?.edition === 'cloud'
                          ? 'border-transparent bg-blue-500 text-white'
                          : ''
                      }`}
                    >
                      {systemInfo?.edition === 'cloud'
                        ? t('sidebar.editionCloud')
                        : t('sidebar.editionCommunity')}
                    </Badge>
                  </div>
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
        <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
          <SidebarContent ref={navigationContentRef} className="min-h-0 pb-8">
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
            <PluginPagesNav />
          </SidebarContent>
          <button
            type="button"
            onClick={scrollNavigationToBottom}
            disabled={!showScrollHint}
            aria-label={t('sidebar.scrollToBottom')}
            aria-hidden={!showScrollHint}
            tabIndex={showScrollHint ? 0 : -1}
            className={cn(
              'absolute inset-x-0 bottom-2 z-10 mx-auto flex w-fit justify-center rounded-full transition-opacity duration-200 group-data-[collapsible=icon]:hidden',
              showScrollHint
                ? 'pointer-events-auto opacity-100'
                : 'pointer-events-none opacity-0',
            )}
          >
            <span className="flex size-7 items-center justify-center rounded-full border border-sidebar-border bg-sidebar/95 text-sidebar-foreground/70 shadow-sm backdrop-blur transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground">
              <ChevronDown className="size-4" />
            </span>
          </button>
        </div>

        {/* Footer */}
        <SidebarFooter>
          {/* Models entry */}
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                onClick={() => openSettings('models')}
                tooltip={t('models.title')}
              >
                <Sparkles className="text-blue-500" />
                <span>{t('models.title')}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>

          {/* API Integration entry */}
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                onClick={() => openSettings('apiIntegration')}
                tooltip={t('common.apiIntegration')}
              >
                <KeyRound className="size-4 text-blue-500" />
                <span>{t('common.apiIntegration')}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>

          {/* User menu using sidebar-07 nav-user DropdownMenu pattern */}
          <SidebarMenu>
            <SidebarMenuItem>
              <DropdownMenu open={userMenuOpen} onOpenChange={setUserMenuOpen}>
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
                      onClick={() => {
                        setUserMenuOpen(false);
                        openSettings('account');
                      }}
                    >
                      <Settings />
                      {t('account.settings')}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        setUserMenuOpen(false);
                        openSettings('storageAnalysis');
                      }}
                    >
                      <HardDrive />
                      {t('storageAnalysis.title')}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        setUserMenuOpen(false);
                        navigate('/wizard');
                      }}
                    >
                      <Zap className="text-blue-500" />
                      {t('sidebar.quickStart')}
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
                            'https://link.langbot.app/zh/docs/guide',
                            '_blank',
                          );
                        } else {
                          window.open(
                            'https://link.langbot.app/en/docs/guide',
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
                    <DropdownMenuItem
                      onClick={() => {
                        window.open(
                          'https://github.com/langbot-app/LangBot',
                          '_blank',
                        );
                      }}
                    >
                      <Star
                        className={cn(
                          'text-yellow-500',
                          userMenuOpen && 'animate-twinkle',
                        )}
                      />
                      <span className="flex-1">{t('common.starOnGitHub')}</span>
                      {starCount != null && (
                        <Badge variant="secondary" className="ml-auto text-xs">
                          {starCount >= 1000
                            ? `${(starCount / 1000).toFixed(1)}k`
                            : starCount}
                        </Badge>
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        window.open('https://discord.gg/wdNEHETs87', '_blank');
                      }}
                    >
                      <DiscordIcon className="text-[#5865F2]" />
                      {t('common.joinDiscord')}
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

      <SettingsDialog
        open={settingsOpen}
        onOpenChange={handleSettingsOpenChange}
        section={settingsSection}
        onSectionChange={handleSettingsSectionChange}
      />
      <NewVersionDialog
        open={versionDialogOpen}
        onOpenChange={setVersionDialogOpen}
        release={latestRelease}
      />
    </>
  );
}
