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
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { LanguageSelector } from '@/components/ui/language-selector';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import AccountSettingsDialog from '@/app/home/components/account-settings-dialog/AccountSettingsDialog';
import ApiIntegrationDialog from '@/app/home/components/api-integration-dialog/ApiIntegrationDialog';
import NewVersionDialog from '@/app/home/components/new-version-dialog/NewVersionDialog';
import ModelsDialog from '@/app/home/components/models-dialog/ModelsDialog';
import { GitHubRelease } from '@/app/infra/http/CloudServiceClient';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  SidebarSeparator,
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

// Categories that support detail pages (plugins do not — they use inline dialog)
const DETAIL_PAGE_CATEGORIES: EntityCategoryId[] = [
  'bots',
  'pipelines',
  'knowledge',
];

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

// Renders sidebar navigation items with collapsible sub-items for entity categories
function NavItems({
  selectedChild,
  onChildClick,
}: {
  selectedChild: SidebarChildVO | undefined;
  onChildClick: (child: SidebarChildVO) => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sidebarData = useSidebarData();

  return (
    <>
      {sidebarConfigList.map((config) => {
        if (!isEntityCategory(config.id)) {
          // Non-entity entries (e.g. monitoring) render as plain links
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
        const isActive =
          selectedChild?.id === config.id ||
          pathname === routePrefix ||
          pathname.startsWith(routePrefix + '/');

        return (
          <Collapsible
            key={config.id}
            asChild
            defaultOpen={isActive}
            className="group/collapsible"
          >
            <SidebarMenuItem>
              <CollapsibleTrigger asChild>
                <SidebarMenuButton
                  isActive={isActive}
                  onClick={() => onChildClick(config)}
                  tooltip={config.name}
                >
                  {config.icon}
                  <span>{config.name}</span>
                  <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                </SidebarMenuButton>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <SidebarMenuSub>
                  {items.map((item) => {
                    // Plugins navigate to the list page; others use ?id= query param
                    const itemRoute = hasDetailPages
                      ? `${routePrefix}?id=${encodeURIComponent(item.id)}`
                      : routePrefix;
                    const isItemActive =
                      hasDetailPages &&
                      pathname === routePrefix &&
                      searchParams.get('id') === item.id;
                    return (
                      <SidebarMenuSubItem key={item.id}>
                        <SidebarMenuSubButton asChild isActive={isItemActive}>
                          <a
                            href={itemRoute}
                            onClick={(e) => {
                              e.preventDefault();
                              router.push(itemRoute);
                            }}
                          >
                            {item.emoji ? (
                              <span className="text-sm">{item.emoji}</span>
                            ) : item.iconURL ? (
                              <img
                                src={item.iconURL}
                                alt=""
                                className="size-4 rounded shrink-0"
                              />
                            ) : null}
                            <span>{item.name}</span>
                          </a>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                    );
                  })}
                  {/* Create new entity entry (only for categories with detail pages) */}
                  {hasDetailPages && (
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
                          <span>{config.name}</span>
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
    </>
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
  const { theme, setTheme } = useTheme();
  const { t } = useTranslation();
  const [accountSettingsOpen, setAccountSettingsOpen] = useState(false);
  const [apiKeyDialogOpen, setApiKeyDialogOpen] = useState(false);
  const [starCount, setStarCount] = useState<number | null>(null);
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
      .get('/api/v1/dist/info/repo')
      .then((response) => {
        const data = response as { repo: { stargazers_count: number } };
        setStarCount(data.repo.stargazers_count);
      })
      .catch((error) => {
        console.error('Failed to fetch GitHub star count:', error);
      });

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

  function handleChildClick(child: SidebarChildVO) {
    setSelectedChild(child);
    handleRoute(child);
    onSelectedChangeAction(child);
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
      handleChildClick(matchedChild);
    } else {
      handleChildClick(sidebarConfigList[0]);
    }
  }

  function handleRoute(child: SidebarChildVO) {
    router.push(`${child.route}`);
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
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <img
                    src={langbotIcon.src}
                    alt="LangBot"
                    className="size-6 rounded"
                  />
                </div>
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

        {/* Navigation items with collapsible entity sub-items */}
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                <NavItems
                  selectedChild={selectedChild}
                  onChildClick={handleChildClick}
                />
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>

        {/* Footer */}
        <SidebarFooter>
          {/* GitHub star badge - hidden when collapsed */}
          {starCount !== null && (
            <div className="flex justify-center px-2 group-data-[collapsible=icon]:hidden">
              <Badge
                variant="outline"
                className="hover:bg-secondary/50 px-3 py-1.5 text-sm font-medium transition-colors border-border relative overflow-hidden group cursor-pointer"
                onClick={() => {
                  window.open(
                    'https://github.com/langbot-app/LangBot',
                    '_blank',
                  );
                }}
              >
                <svg
                  className="w-4 h-4 mr-2"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
                </svg>
                <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent group-hover:translate-x-full transition-transform duration-1000 ease-out" />
                {starCount.toLocaleString()}
              </Badge>
            </div>
          )}

          <SidebarSeparator className="group-data-[collapsible=icon]:hidden" />

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

          <SidebarSeparator className="group-data-[collapsible=icon]:hidden" />

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

        <SidebarRail />
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
