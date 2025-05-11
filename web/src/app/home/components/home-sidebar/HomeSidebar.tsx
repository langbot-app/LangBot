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
import { httpClient } from '@/app/infra/http/HttpClient';

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

  useEffect(() => {
    console.log('HomeSidebar挂载完成');
    initSelect();
    return () => console.log('HomeSidebar卸载');
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
              {httpClient.systemInfo?.version}
            </div>
          </div>
        </div>
        {/* 菜单列表，后期可升级成配置驱动 */}
        <div>
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
        <SidebarChild
          onClick={() => {}}
          isSelected={false}
          icon={
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M2 11.9998C2 11.1353 2.1097 10.2964 2.31595 9.49631C3.40622 9.55283 4.48848 9.01015 5.0718 7.99982C5.65467 6.99025 5.58406 5.78271 4.99121 4.86701C6.18354 3.69529 7.66832 2.82022 9.32603 2.36133C9.8222 3.33385 10.8333 3.99982 12 3.99982C13.1667 3.99982 14.1778 3.33385 14.674 2.36133C16.3317 2.82022 17.8165 3.69529 19.0088 4.86701C18.4159 5.78271 18.3453 6.99025 18.9282 7.99982C19.5115 9.01015 20.5938 9.55283 21.6841 9.49631C21.8903 10.2964 22 11.1353 22 11.9998C22 12.8643 21.8903 13.7032 21.6841 14.5033C20.5938 14.4468 19.5115 14.9895 18.9282 15.9998C18.3453 17.0094 18.4159 18.2169 19.0088 19.1326C17.8165 20.3043 16.3317 21.1794 14.674 21.6383C14.1778 20.6658 13.1667 19.9998 12 19.9998C10.8333 19.9998 9.8222 20.6658 9.32603 21.6383C7.66832 21.1794 6.18354 20.3043 4.99121 19.1326C5.58406 18.2169 5.65467 17.0094 5.0718 15.9998C4.48848 14.9895 3.40622 14.4468 2.31595 14.5033C2.1097 13.7032 2 12.8643 2 11.9998ZM6.80385 14.9998C7.43395 16.0912 7.61458 17.3459 7.36818 18.5236C7.77597 18.8138 8.21005 19.0652 8.66489 19.2741C9.56176 18.4712 10.7392 17.9998 12 17.9998C13.2608 17.9998 14.4382 18.4712 15.3351 19.2741C15.7899 19.0652 16.224 18.8138 16.6318 18.5236C16.3854 17.3459 16.566 16.0912 17.1962 14.9998C17.8262 13.9085 18.8225 13.1248 19.9655 12.7493C19.9884 12.5015 20 12.2516 20 11.9998C20 11.7481 19.9884 11.4981 19.9655 11.2504C18.8225 10.8749 17.8262 10.0912 17.1962 8.99982C16.566 7.90845 16.3854 6.65378 16.6318 5.47605C16.224 5.18588 15.7899 4.93447 15.3351 4.72552C14.4382 5.52844 13.2608 5.99982 12 5.99982C10.7392 5.99982 9.56176 5.52844 8.66489 4.72552C8.21005 4.93447 7.77597 5.18588 7.36818 5.47605C7.61458 6.65378 7.43395 7.90845 6.80385 8.99982C6.17376 10.0912 5.17754 10.8749 4.03451 11.2504C4.01157 11.4981 4 11.7481 4 11.9998C4 12.2516 4.01157 12.5015 4.03451 12.7493C5.17754 13.1248 6.17376 13.9085 6.80385 14.9998ZM12 14.9998C10.3431 14.9998 9 13.6567 9 11.9998C9 10.343 10.3431 8.99982 12 8.99982C13.6569 8.99982 15 10.343 15 11.9998C15 13.6567 13.6569 14.9998 12 14.9998ZM12 12.9998C12.5523 12.9998 13 12.5521 13 11.9998C13 11.4475 12.5523 10.9998 12 10.9998C11.4477 10.9998 11 11.4475 11 11.9998C11 12.5521 11.4477 12.9998 12 12.9998Z"></path>
            </svg>
          }
          name="系统设置"
        />
        <SidebarChild
          onClick={() => {
            // open docs.langbot.app
            window.open('https://docs.langbot.app', '_blank');
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
          name="帮助文档"
        />
      </div>
    </div>
  );
}
