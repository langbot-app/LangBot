'use client';

import styles from './HomeSidebar.module.css';
import { useEffect, useState } from 'react';
import {
  SidebarChild,
  SidebarChildVO,
} from '@/app/home/components/home-sidebar/HomeSidebarChild';
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
  CircleHelp,
  Lightbulb,
  LogOut,
  KeyRound,
} from 'lucide-react';
import { useTheme } from 'next-themes';

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { LanguageSelector } from '@/components/ui/language-selector';
import { Badge } from '@/components/ui/badge';
import AccountSettingsDialog from '@/app/home/components/account-settings-dialog/AccountSettingsDialog';
import ApiIntegrationDialog from '@/app/home/components/api-integration-dialog/ApiIntegrationDialog';
import NewVersionDialog from '@/app/home/components/new-version-dialog/NewVersionDialog';
import ModelsDialog from '@/app/home/components/models-dialog/ModelsDialog';
import { GitHubRelease } from '@/app/infra/http/CloudServiceClient';

// Compare two version strings, returns true if v1 > v2
function compareVersions(v1: string, v2: string): boolean {
  // Remove 'v' prefix if present
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

// TODO 侧边导航栏要加动画
export default function HomeSidebar({
  onSelectedChangeAction,
}: {
  onSelectedChangeAction: (sidebarChild: SidebarChildVO) => void;
}) {
  // 路由相关
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  // 路由被动变化时处理
  useEffect(() => {
    handleRouteChange(pathname);
  }, [pathname]);

  // 检查 URL 参数，自动打开模型对话框
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
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [accountSettingsOpen, setAccountSettingsOpen] = useState(false);
  const [apiKeyDialogOpen, setApiKeyDialogOpen] = useState(false);
  const [languageSelectorOpen, setLanguageSelectorOpen] = useState(false);
  const [starCount, setStarCount] = useState<number | null>(null);
  const [latestRelease, setLatestRelease] = useState<GitHubRelease | null>(
    null,
  );
  const [hasNewVersion, setHasNewVersion] = useState(false);
  const [versionDialogOpen, setVersionDialogOpen] = useState(false);
  const [modelsDialogOpen, setModelsDialogOpen] = useState(false);
  const [userEmail, setUserEmail] = useState<string>('');

  // 处理模型对话框的打开和关闭，同时更新 URL
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

  // 处理账户设置对话框的打开和关闭，同时更新 URL
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

    // Load user email
    const storedEmail = localStorage.getItem('userEmail');
    if (storedEmail) {
      setUserEmail(storedEmail);
    } else {
      // Fetch from API if not in localStorage
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

    // Fetch releases to check for new version
    getCloudServiceClientSync()
      .getLangBotReleases()
      .then((releases) => {
        if (releases && releases.length > 0) {
          // Find the latest non-prerelease, non-draft release
          const latestStable = releases.find((r) => !r.prerelease && !r.draft);
          const latest = latestStable || releases[0];
          setLatestRelease(latest);

          // Compare versions
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
    // 根据当前路径选择对应的菜单项
    const currentPath = pathname;
    const matchedChild = sidebarConfigList.find(
      (childConfig) => childConfig.route === currentPath,
    );
    if (matchedChild) {
      handleChildClick(matchedChild);
    } else {
      // 如果没有匹配的路径，则默认选择第一个
      handleChildClick(sidebarConfigList[0]);
    }
  }

  function handleRoute(child: SidebarChildVO) {
    router.push(`${child.route}`);
  }

  function handleRouteChange(pathname: string) {
    // TODO 这段逻辑并不好，未来router封装好后改掉
    // 判断在home下，并且路由更改的是自己的路由子组件则更新UI
    const routeList = pathname.split('/');
    if (
      routeList[1] === 'home' &&
      sidebarConfigList.find((childConfig) => childConfig.route === pathname)
    ) {
      const routeSelectChild = sidebarConfigList.find(
        (childConfig) => childConfig.route === pathname,
      );
      if (routeSelectChild) {
        setSelectedChild(routeSelectChild);
        onSelectedChangeAction(routeSelectChild);
      }
    }
  }

  function handleLogout() {
    localStorage.removeItem('token');
    localStorage.removeItem('userEmail');
    window.location.href = '/login';
  }

  return (
    <div className={`${styles.sidebarContainer}`}>
      <div className={`${styles.sidebarTopContainer}`}>
        {/* LangBot、ICON区域 */}
        <div className={`${styles.langbotIconContainer}`}>
          {/* icon */}
          <img
            className={`${styles.langbotIcon}`}
            src={langbotIcon.src}
            alt="langbot-icon"
          />
          {/* 文字 */}
          <div className={`${styles.langbotTextContainer}`}>
            <div className={`${styles.langbotText}`}>LangBot</div>
            <div className="flex items-center gap-1.5">
              <div className={`${styles.langbotVersion}`}>
                {systemInfo?.version}
              </div>
              {hasNewVersion && (
                <Badge
                  onClick={() => setVersionDialogOpen(true)}
                  className="bg-red-500 hover:bg-red-600 text-white text-[0.6rem] px-1.5 py-0 h-4 cursor-pointer"
                >
                  {t('plugins.new')}
                </Badge>
              )}
            </div>
          </div>
        </div>
        {/* 菜单列表，后期可升级成配置驱动 */}
        <div className={styles.sidebarItemsContainer}>
          {sidebarConfigList.map((config) => {
            return (
              <div
                key={config.id}
                onClick={() => {
                  handleChildClick(config);
                }}
              >
                <SidebarChild
                  onClick={() => {}}
                  isSelected={
                    selectedChild !== undefined &&
                    selectedChild.id === config.id
                  }
                  icon={config.icon}
                  name={config.name}
                />
              </div>
            );
          })}
        </div>
      </div>

      <div className={`${styles.sidebarBottomContainer}`}>
        {starCount !== null && (
          <div
            onClick={() => {
              window.open('https://github.com/langbot-app/LangBot', '_blank');
            }}
            className="flex justify-center cursor-pointer p-2 rounded-lg transition-colors"
          >
            <Badge
              variant="outline"
              className="hover:bg-secondary/50 px-3 py-1.5 text-sm font-medium transition-colors border-border relative overflow-hidden group"
            >
              <svg
                className="w-4 h-4 mr-2"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
              </svg>
              <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent group-hover:translate-x-full transition-transform duration-1000 ease-out"></div>
              {starCount.toLocaleString()}
            </Badge>
          </div>
        )}

        <SidebarChild
          onClick={() => handleModelsDialogChange(true)}
          isSelected={false}
          icon={
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M10.6144 17.7956C10.277 18.5682 9.20776 18.5682 8.8704 17.7956L7.99275 15.7854C7.21171 13.9966 5.80589 12.5726 4.0523 11.7942L1.63658 10.7219C.868536 10.381.868537 9.26368 1.63658 8.92276L3.97685 7.88394C5.77553 7.08552 7.20657 5.60881 7.97427 3.75892L8.8633 1.61673C9.19319.821767 10.2916.821765 10.6215 1.61673L11.5105 3.75894C12.2782 5.60881 13.7092 7.08552 15.5079 7.88394L17.8482 8.92276C18.6162 9.26368 18.6162 10.381 17.8482 10.7219L15.4325 11.7942C13.6789 12.5726 12.2731 13.9966 11.492 15.7854L10.6144 17.7956ZM4.53956 9.82234C6.8254 10.837 8.68402 12.5048 9.74238 14.7996 10.8008 12.5048 12.6594 10.837 14.9452 9.82234 12.6321 8.79557 10.7676 7.04647 9.74239 4.71088 8.71719 7.04648 6.85267 8.79557 4.53956 9.82234ZM19.4014 22.6899 19.6482 22.1242C20.0882 21.1156 20.8807 20.3125 21.8695 19.8732L22.6299 19.5353C23.0412 19.3526 23.0412 18.7549 22.6299 18.5722L21.9121 18.2532C20.8978 17.8026 20.0911 16.9698 19.6586 15.9269L19.4052 15.3156C19.2285 14.8896 18.6395 14.8896 18.4628 15.3156L18.2094 15.9269C17.777 16.9698 16.9703 17.8026 15.956 18.2532L15.2381 18.5722C14.8269 18.7549 14.8269 19.3526 15.2381 19.5353L15.9985 19.8732C16.9874 20.3125 17.7798 21.1156 18.2198 22.1242L18.4667 22.6899C18.6473 23.104 19.2207 23.104 19.4014 22.6899ZM18.3745 19.0469 18.937 18.4883 19.4878 19.0469 18.937 19.5898 18.3745 19.0469Z"></path>
            </svg>
          }
          name={t('models.title')}
        />

        <Popover
          open={popoverOpen}
          onOpenChange={(open) => {
            // 防止语言选择器打开时关闭popover
            if (!open && languageSelectorOpen) return;
            setPopoverOpen(open);
          }}
        >
          <PopoverTrigger>
            <SidebarChild
              onClick={() => {}}
              isSelected={false}
              icon={
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M12 3C10.9 3 10 3.9 10 5C10 6.1 10.9 7 12 7C13.1 7 14 6.1 14 5C14 3.9 13.1 3 12 3ZM12 17C10.9 17 10 17.9 10 19C10 20.1 10.9 21 12 21C13.1 21 14 20.1 14 19C14 17.9 13.1 17 12 17ZM12 10C10.9 10 10 10.9 10 12C10 13.1 10.9 14 12 14C13.1 14 14 13.1 14 12C14 10.9 13.1 10 12 10Z"></path>
                </svg>
              }
              name={t('common.accountOptions')}
            />
          </PopoverTrigger>
          <PopoverContent
            side="right"
            align="end"
            className="w-auto p-2 flex flex-col gap-2"
          >
            <div
              className="flex items-center gap-3 p-2 rounded-lg hover:bg-accent cursor-pointer"
              onClick={() => {
                handleAccountSettingsChange(true);
                setPopoverOpen(false);
              }}
            >
              <div className="w-10 h-10 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-medium">
                {userEmail ? userEmail.charAt(0).toUpperCase() : 'U'}
              </div>
              <span className="text-sm truncate max-w-[180px]">
                {userEmail || t('account.settings')}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <LanguageSelector
                triggerClassName="flex-1"
                onOpenChange={setLanguageSelectorOpen}
              />
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
                {theme === 'light' && <Sun className="h-[1.2rem] w-[1.2rem]" />}
                {theme === 'dark' && <Moon className="h-[1.2rem] w-[1.2rem]" />}
                {theme === 'system' && (
                  <Monitor className="h-[1.2rem] w-[1.2rem]" />
                )}
              </Button>
            </div>

            <div className="flex flex-col gap-1">
              <Button
                variant="ghost"
                className="w-full justify-start font-normal"
                onClick={() => {
                  setApiKeyDialogOpen(true);
                  setPopoverOpen(false);
                }}
              >
                <KeyRound className="w-4 h-4 mr-2" />
                {t('common.apiIntegration')}
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start font-normal"
                onClick={() => {
                  const language = localStorage.getItem('langbot_language');
                  if (language === 'zh-Hans' || language === 'zh-Hant') {
                    window.open(
                      'https://docs.langbot.app/zh/insight/guide.html',
                      '_blank',
                    );
                  } else {
                    window.open(
                      'https://docs.langbot.app/en/insight/guide.html',
                      '_blank',
                    );
                  }
                  setPopoverOpen(false);
                }}
              >
                <CircleHelp className="w-4 h-4 mr-2" />
                {t('common.helpDocs')}
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start font-normal"
                onClick={() => {
                  window.open(
                    'https://github.com/langbot-app/LangBot/issues',
                    '_blank',
                  );
                  setPopoverOpen(false);
                }}
              >
                <Lightbulb className="w-4 h-4 mr-2" />
                {t('common.featureRequest')}
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start font-normal"
                onClick={() => handleLogout()}
              >
                <LogOut className="w-4 h-4 mr-2" />
                {t('common.logout')}
              </Button>
            </div>
          </PopoverContent>
        </Popover>
      </div>
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
    </div>
  );
}
