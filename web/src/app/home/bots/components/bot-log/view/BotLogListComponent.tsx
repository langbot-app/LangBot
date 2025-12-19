'use client';

import { BotLogManager } from '@/app/home/bots/components/bot-log/BotLogManager';
import { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { BotLog } from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';
import { BotLogCard } from '@/app/home/bots/components/bot-log/view/BotLogCard';
import styles from './botLog.module.css';
import { Switch } from '@/components/ui/switch';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { ChevronDownIcon } from 'lucide-react';
import { debounce } from 'lodash';
import { useTranslation } from 'react-i18next';

export function BotLogListComponent({ botId }: { botId: string }) {
  const { t } = useTranslation();
  const manager = useRef(new BotLogManager(botId)).current;
  const [botLogList, setBotLogList] = useState<BotLog[]>([]);
  const [autoFlush, setAutoFlush] = useState(true);
  const [selectedLevels, setSelectedLevels] = useState<string[]>([
    'info',
    'warning',
    'error',
  ]);
  const listContainerRef = useRef<HTMLDivElement>(null);
  const botLogListRef = useRef<BotLog[]>(botLogList);

  const logLevels = [
    { value: 'error', label: 'ERROR' },
    { value: 'warning', label: 'WARNING' },
    { value: 'info', label: 'INFO' },
    { value: 'debug', label: 'DEBUG' },
  ];

  useEffect(() => {
    initComponent();
    return () => {
      onDestroy();
    };
  }, []);

  useEffect(() => {
    botLogListRef.current = botLogList;
  }, [botLogList]);

  // 根据级别过滤日志
  const filteredLogs = useMemo(() => {
    if (selectedLevels.length === 0) {
      return botLogList;
    }
    return botLogList.filter((log) => selectedLevels.includes(log.level));
  }, [botLogList, selectedLevels]);

  const handleLevelToggle = (levelValue: string) => {
    setSelectedLevels((prev) => {
      if (prev.includes(levelValue)) {
        return prev.filter((l) => l !== levelValue);
      } else {
        return [...prev, levelValue];
      }
    });
  };

  const getDisplayText = () => {
    if (selectedLevels.length === 0) {
      return t('bots.selectLevel');
    }
    if (selectedLevels.length === logLevels.length) {
      return t('bots.allLevels');
    }
    // 如果选中3个或以上，显示数量
    if (selectedLevels.length >= 3) {
      return `${selectedLevels.length} ${t('bots.levelsSelected')}`;
    }
    // 显示选中级别的标签（大写形式）
    return logLevels
      .filter((level) => selectedLevels.includes(level.value))
      .map((level) => level.label)
      .join(', ');
  };

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
        <div className={'ml-4 mr-2'}>{t('bots.logLevel')}</div>
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="w-[180px] flex items-center justify-between"
            >
              <span className="text-sm truncate flex-1 text-left">
                {getDisplayText()}
              </span>
              <ChevronDownIcon className="ml-2 h-4 w-4 flex-shrink-0" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[180px] p-2">
            <div className="flex flex-col gap-2">
              {logLevels.map((level) => (
                <div key={level.value} className="flex items-center space-x-2">
                  <Checkbox
                    id={level.value}
                    checked={selectedLevels.includes(level.value)}
                    onCheckedChange={() => handleLevelToggle(level.value)}
                  />
                  <label
                    htmlFor={level.value}
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                  >
                    {level.label}
                  </label>
                </div>
              ))}
            </div>
          </PopoverContent>
        </Popover>
      </div>

      {filteredLogs.map((botLog) => {
        return <BotLogCard botLog={botLog} key={botLog.seq_id} />;
      })}
    </div>
  );
}
