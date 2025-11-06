'use client';

import styles from './HomeSidebar.module.css';
import { useEffect, useState } from 'react';
import {
  SidebarChild,
  SidebarChildVO,
} from '@/app/home/components/home-sidebar/HomeSidebarChild';
import { useRouter, usePathname } from 'next/navigation';
import { sidebarConfigList } from '@/app/home/components/home-sidebar/sidbarConfigList';
import langbotIcon from '@/app/assets/langbot-logo.webp';
import { systemInfo } from '@/app/infra/http/HttpClient';
import { getCloudServiceClientSync } from '@/app/infra/http';
import { useTranslation } from 'react-i18next';
import { Moon, Sun, Monitor } from 'lucide-react';
import { useTheme } from 'next-themes';

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { LanguageSelector } from '@/components/ui/language-selector';
import { Badge } from '@/components/ui/badge';
import PasswordChangeDialog from '@/app/home/components/password-change-dialog/PasswordChangeDialog';

// TODO 侧边导航栏要加动画
export default function HomeSidebar({
  onSelectedChangeAction,
}: {
  onSelectedChangeAction: (sidebarChild: SidebarChildVO) => void;
}) {
  // 路由相关
  const router = useRouter();
  const pathname = usePathname();
  // 路由被动变化时处理
  useEffect(() => {
    handleRouteChange(pathname);
  }, [pathname]);

  const [selectedChild, setSelectedChild] = useState<SidebarChildVO>();
  const { theme, setTheme } = useTheme();
  const { t } = useTranslation();
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [passwordChangeOpen, setPasswordChangeOpen] = useState(false);
  const [languageSelectorOpen, setLanguageSelectorOpen] = useState(false);
  const [starCount, setStarCount] = useState<number | null>(null);

  useEffect(() => {
    initSelect();
    if (!localStorage.getItem('token')) {
      localStorage.setItem('token', 'test-token');
      localStorage.setItem('userEmail', 'test@example.com');
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
    return () => console.log('sidebar.unmounted');
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
    console.log(child);
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
      console.log('find success');
      const routeSelectChild = sidebarConfigList.find(
        (childConfig) => childConfig.route === pathname,
      );
      if (routeSelectChild) {
        setSelectedChild(routeSelectChild);
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
            <div className={`${styles.langbotVersion}`}>
              {systemInfo?.version}
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
                  console.log('click:', config.id);
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
            className="flex justify-center cursor-pointer p-2 rounded-lg hover:bg-accent/30 transition-colors"
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
          onClick={() => {
            // open docs.langbot.app
            const language = localStorage.getItem('langbot_language');
            if (language === 'zh-Hans') {
              window.open(
                'https://docs.langbot.app/zh/insight/guide.html',
                '_blank',
              );
            } else if (language === 'zh-Hant') {
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
          }}
          isSelected={false}
          icon={
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22ZM12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM11 15H13V17H11V15ZM13 13.3551V14H11V12.5C11 11.9477 11.4477 11.5 12 11.5C12.8284 11.5 13.5 10.8284 13.5 10C13.5 9.17157 12.8284 8.5 12 8.5C11.2723 8.5 10.6656 9.01823 10.5288 9.70577L8.56731 9.31346C8.88637 7.70919 10.302 6.5 12 6.5C13.933 6.5 15.5 8.067 15.5 10C15.5 11.5855 14.4457 12.9248 13 13.3551Z"></path>
            </svg>
          }
          name={t('common.helpDocs')}
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
            className="w-auto p-4 flex flex-col gap-4"
          >
            <div className="flex flex-col gap-2 w-full">
              <span className="text-sm font-medium">{t('common.theme')}</span>
              <ToggleGroup
                type="single"
                value={theme}
                onValueChange={(value) => {
                  if (value) setTheme(value);
                }}
                className="justify-start"
              >
                <ToggleGroupItem value="light" size="sm">
                  <Sun className="h-4 w-4" />
                </ToggleGroupItem>
                <ToggleGroupItem value="dark" size="sm">
                  <Moon className="h-4 w-4" />
                </ToggleGroupItem>
                <ToggleGroupItem value="system" size="sm">
                  <Monitor className="h-4 w-4" />
                </ToggleGroupItem>
              </ToggleGroup>
            </div>

            <div className="flex flex-col gap-2 w-full">
              <span className="text-sm font-medium">
                {t('common.language')}
              </span>
              <LanguageSelector
                triggerClassName="w-full"
                onOpenChange={setLanguageSelectorOpen}
              />
            </div>

            <div className="flex flex-col gap-2 w-full">
              <span className="text-sm font-medium">{t('common.account')}</span>
              <Button
                variant="ghost"
                className="w-full justify-start font-normal"
                onClick={() => {
                  setPasswordChangeOpen(true);
                  setPopoverOpen(false);
                }}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  className="w-4 h-4 mr-2"
                >
                  <path d="M6 8V7C6 3.68629 8.68629 1 12 1C15.3137 1 18 3.68629 18 7V8H20C20.5523 8 21 8.44772 21 9V21C21 21.5523 20.5523 22 20 22H4C3.44772 22 3 21.5523 3 21V9C3 8.44772 3.44772 8 4 8H6ZM19 10H5V20H19V10ZM11 15.7324C10.4022 15.3866 10 14.7403 10 14C10 12.8954 10.8954 12 12 12C13.1046 12 14 12.8954 14 14C14 14.7403 13.5978 15.3866 13 15.7324V18H11V15.7324ZM8 8H16V7C16 4.79086 14.2091 3 12 3C9.79086 3 8 4.79086 8 7V8Z"></path>
                </svg>
                {t('common.changePassword')}
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start font-normal"
                onClick={() => {
                  handleLogout();
                }}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  className="w-4 h-4 mr-2"
                >
                  <path d="M4 18H6V20H18V4H6V6H4V3C4 2.44772 4.44772 2 5 2H19C19.5523 2 20 2.44772 20 3V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V18ZM6 11H13V13H6V16L1 12L6 8V11Z"></path>
                </svg>
                {t('common.logout')}
              </Button>
            </div>
          </PopoverContent>
        </Popover>
      </div>
      <PasswordChangeDialog
        open={passwordChangeOpen}
        onOpenChange={setPasswordChangeOpen}
      />
    </div>
  );
}
