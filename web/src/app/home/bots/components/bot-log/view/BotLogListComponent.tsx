'use client';

import { BotLogManager } from '@/app/home/bots/components/bot-log/BotLogManager';
import { useCallback, useEffect, useRef, useState } from 'react';
import { BotLog } from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';
import { BotLogCard } from '@/app/home/bots/components/bot-log/view/BotLogCard';
import styles from './botLog.module.css';
import { Switch } from '@/components/ui/switch';
import { debounce } from 'lodash';
import { useTranslation } from 'react-i18next';

export function BotLogListComponent({ botId }: { botId: string }) {
  const { t } = useTranslation();
  const manager = useRef(new BotLogManager(botId)).current;
  const [botLogList, setBotLogList] = useState<BotLog[]>([]);
  const [autoFlush, setAutoFlush] = useState(true);
  const listContainerRef = useRef<HTMLDivElement>(null);
  const botLogListRef = useRef<BotLog[]>(botLogList);

  useEffect(() => {
    initComponent();
    return () => {
      onDestroy();
    };
  }, []);

  useEffect(() => {
    botLogListRef.current = botLogList;
  }, [botLogList]);

  // 观测自动刷新状态
  useEffect(() => {
    if (autoFlush) {
      manager.startListenServerPush();
    } else {
      manager.stopServerPush();
    }
    return () => {
      manager.stopServerPush();
    };
  }, [autoFlush]);

  function initComponent() {
    // 订阅日志推送
    manager.subscribeLogPush(handleBotLogPush);
    // 加载第一页日志
    manager.loadFirstPage().then((response) => {
      setBotLogList(response.reverse());
    });
    // 监听滚动
    listenScroll();
  }

  function onDestroy() {
    manager.dispose();
    removeScrollListener();
  }

  function listenScroll() {
    if (!listContainerRef.current) {
      return;
    }
    const list = listContainerRef.current;
    list.addEventListener('scroll', handleScroll);
  }

  function removeScrollListener() {
    if (!listContainerRef.current) {
      return;
    }
    const list = listContainerRef.current;
    list.removeEventListener('scroll', handleScroll);
  }

  function loadMore() {
    // 加载更多日志
    const list = botLogListRef.current;
    const lastSeq = list[list.length - 1].seq_id;
    if (lastSeq === 0) {
      return;
    }
    manager.loadMore(lastSeq - 1, 10).then((response) => {
      setBotLogList([...list, ...response.reverse()]);
    });
  }

  function handleBotLogPush(response: BotLog[]) {
    setBotLogList(response.reverse());
  }

  const handleScroll = useCallback(
    debounce(() => {
      if (!listContainerRef.current) return;

      const { scrollTop, scrollHeight, clientHeight } =
        listContainerRef.current;
      const isBottom = scrollTop + clientHeight >= scrollHeight - 5;
      const isTop = scrollTop === 0;

      if (isBottom) {
        setAutoFlush(false);
        loadMore();
      }
      if (isTop) {
        setAutoFlush(true);
      }
      if (!isTop && !isBottom) {
        setAutoFlush(false);
      }
    }, 300), // 防抖延迟 300ms
    [botLogList], // 依赖项为空
  );

  return (
    <div className={`${styles.botLogListContainer}`} ref={listContainerRef}>
      <div className={`${styles.listHeader}`}>
        <div className={'mr-2'}>{t('bots.enableAutoRefresh')}</div>
        <Switch checked={autoFlush} onCheckedChange={(e) => setAutoFlush(e)} />
      </div>

      {botLogList.map((botLog) => {
        return <BotLogCard botLog={botLog} key={botLog.seq_id} />;
      })}
    </div>
  );
}
