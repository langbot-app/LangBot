'use client';

import styles from './layout.module.css';
import HomeSidebar from '@/app/home/components/home-sidebar/HomeSidebar';
import HomeTitleBar from '@/app/home/components/home-titlebar/HomeTitleBar';
import React, { useState } from 'react';
import { SidebarChildVO } from '@/app/home/components/home-sidebar/HomeSidebarChild';
import { I18nLabel } from '@/app/infra/entities/common';

export default function HomeLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [title, setTitle] = useState<string>('');
  const [subtitle, setSubtitle] = useState<string>('');
  const [helpLink, setHelpLink] = useState<I18nLabel>({
    en_US: '',
    zh_Hans: '',
  });
  const onSelectedChangeAction = (child: SidebarChildVO) => {
    setTitle(child.name);
    setSubtitle(child.description);
    setHelpLink(child.helpLink);
  };

  return (
    <div className={styles.homeLayoutContainer}>
      <aside className={styles.sidebar}>
        <HomeSidebar onSelectedChangeAction={onSelectedChangeAction} />
      </aside>

      <div className={styles.main}>
        <HomeTitleBar title={title} subtitle={subtitle} helpLink={helpLink} />

        <main className={styles.mainContent}>{children}</main>
      </div>
    </div>
  );
}
