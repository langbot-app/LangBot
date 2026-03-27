'use client';

import { BotLogManager } from '@/app/home/bots/components/bot-log/BotLogManager';
import { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { BotLog } from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';
import { BotLogCard } from '@/app/home/bots/components/bot-log/view/BotLogCard';
import { Switch } from '@/components/ui/switch';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { ChevronDownIcon, ExternalLink } from 'lucide-react';
import { debounce } from 'lodash';
import { useTranslation } from 'react-i18next';
import { useRouter } from 'next/navigation';

export function BotLogListComponent({
  botId,
  autoExpandImages = false,
  hideDetailedLogsLink = false,
}: {
  botId: string;
  /** When true, log entries with images are rendered expanded by default */
  autoExpandImages?: boolean;
  /** When true, hides the "View Detailed Logs" navigation button */
  hideDetailedLogsLink?: boolean;
}) {
  const { t } = useTranslation();
  const router = useRouter();
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
    if (selectedLevels.length >= 3) {
      return `${selectedLevels.length} ${t('bots.levelsSelected')}`;
    }
    return logLevels
      .filter((level) => selectedLevels.includes(level.value))
      .map((level) => level.label)
      .join(', ');
  };

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
    manager.subscribeLogPush(handleBotLogPush);
    manager.loadFirstPage().then((response) => {
      setBotLogList(response.reverse());
    });
    listenScroll();
  }

  function onDestroy() {
    manager.dispose();
    removeScrollListener();
  }

  function listenScroll() {
    if (!listContainerRef.current) return;
    listContainerRef.current.addEventListener('scroll', handleScroll);
  }

  function removeScrollListener() {
    if (!listContainerRef.current) return;
    listContainerRef.current.removeEventListener('scroll', handleScroll);
  }

  function loadMore() {
    const list = botLogListRef.current;
    const lastSeq = list[list.length - 1].seq_id;
    if (lastSeq === 0) return;
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
    }, 300),
    [botLogList],
  );

  return (
    <div
      className="flex flex-col h-full min-h-0 overflow-y-auto"
      ref={listContainerRef}
    >
      {/* Toolbar */}
      <div className="flex items-center gap-3 pb-3 shrink-0 flex-wrap">
        {/* Auto-refresh toggle */}
        <div className="flex items-center gap-1.5">
          <span className="text-sm text-muted-foreground">
            {t('bots.enableAutoRefresh')}
          </span>
          <Switch
            checked={autoFlush}
            onCheckedChange={(v) => setAutoFlush(v)}
          />
        </div>

        {/* Level filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-sm text-muted-foreground">
            {t('bots.logLevel')}
          </span>
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="w-[160px] justify-between"
              >
                <span className="text-sm truncate">{getDisplayText()}</span>
                <ChevronDownIcon className="size-3.5 shrink-0 opacity-50" />
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-[160px] p-2">
              <div className="flex flex-col gap-2">
                {logLevels.map((level) => (
                  <div
                    key={level.value}
                    className="flex items-center space-x-2"
                  >
                    <Checkbox
                      id={level.value}
                      checked={selectedLevels.includes(level.value)}
                      onCheckedChange={() => handleLevelToggle(level.value)}
                    />
                    <label
                      htmlFor={level.value}
                      className="text-sm font-medium leading-none cursor-pointer"
                    >
                      {level.label}
                    </label>
                  </div>
                ))}
              </div>
            </PopoverContent>
          </Popover>
        </div>

        {/* Link to detailed logs */}
        {!hideDetailedLogsLink && (
          <Button
            variant="outline"
            size="sm"
            className="gap-1"
            onClick={() => router.push(`/home/monitoring?botId=${botId}`)}
          >
            <ExternalLink className="size-3.5" />
            <span className="text-sm">{t('bots.viewDetailedLogs')}</span>
          </Button>
        )}
      </div>

      {/* Log cards */}
      <div className="flex flex-col gap-2">
        {filteredLogs.map((botLog) => (
          <BotLogCard
            botLog={botLog}
            key={botLog.seq_id}
            defaultExpanded={autoExpandImages && botLog.images.length > 0}
          />
        ))}
      </div>
    </div>
  );
}
