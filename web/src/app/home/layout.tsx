'use client';

import styles from './layout.module.css';
import HomeSidebar from '@/app/home/components/home-sidebar/HomeSidebar';
import HomeTitleBar from '@/app/home/components/home-titlebar/HomeTitleBar';
import React, { useState, useCallback, useMemo } from 'react';
import { SidebarChildVO } from '@/app/home/components/home-sidebar/HomeSidebarChild';
import { I18nObject } from '@/app/infra/entities/common';

export default function HomeLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [title, setTitle] = useState<string>('');
  const [subtitle, setSubtitle] = useState<string>('');
  const [helpLink, setHelpLink] = useState<I18nObject>({
    en_US: '',
    zh_Hans: '',
  });

  const onSelectedChangeAction = useCallback((child: SidebarChildVO) => {
    setTitle(child.name);
    setSubtitle(child.description);
    setHelpLink(child.helpLink);
  }, []);

  // Memoize the main content area to prevent re-renders when sidebar state changes
  const mainContent = useMemo(() => children, [children]);

  return (
    <div className={styles.homeLayoutContainer}>
      <aside className={styles.sidebar}>
        <HomeSidebar onSelectedChangeAction={onSelectedChangeAction} />
      </aside>

      <div className={styles.main}>
        <HomeTitleBar title={title} subtitle={subtitle} helpLink={helpLink} />

        <main className={styles.mainContent}>{mainContent}</main>
      </div>
    </div>
  );
}
