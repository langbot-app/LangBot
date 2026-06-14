import { useCallback, useEffect, useRef, useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useTranslation } from 'react-i18next';
import { PluginLogEntry } from '@/app/infra/entities/plugin';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { RefreshCw } from 'lucide-react';

const LEVEL_OPTIONS = ['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR'] as const;

function levelClassName(level: string): string {
  switch (level) {
    case 'ERROR':
    case 'CRITICAL':
      return 'text-red-500';
    case 'WARNING':
      return 'text-amber-500';
    case 'DEBUG':
      return 'text-gray-400 dark:text-gray-500';
    default:
      return 'text-gray-700 dark:text-gray-300';
  }
}

export default function PluginLogs({
  pluginAuthor,
  pluginName,
}: {
  pluginAuthor: string;
  pluginName: string;
}) {
  const { t } = useTranslation();
  const [logs, setLogs] = useState<PluginLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [level, setLevel] = useState<string>('ALL');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const atBottomRef = useRef(true);

  const fetchLogs = useCallback(() => {
    setIsLoading(true);
    httpClient
      .getPluginLogs(
        pluginAuthor,
        pluginName,
        500,
        level === 'ALL' ? undefined : level,
      )
      .then((res) => {
        setLogs(res.logs ?? []);
      })
      .catch(() => {
        setLogs([]);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [pluginAuthor, pluginName, level]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  // Auto-refresh poll loop.
  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(fetchLogs, 3000);
    return () => clearInterval(timer);
  }, [autoRefresh, fetchLogs]);

  // Keep view pinned to bottom when the user is already at the bottom.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && atBottomRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [logs]);

  function handleScroll() {
    const el = scrollRef.current;
    if (!el) return;
    atBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 flex-wrap items-center gap-2 px-6 pb-3">
        <Select value={level} onValueChange={setLevel}>
          <SelectTrigger className="h-8 w-[130px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {LEVEL_OPTIONS.map((opt) => (
              <SelectItem key={opt} value={opt}>
                {opt === 'ALL' ? t('plugins.logsLevelAll') : opt}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8"
          onClick={fetchLogs}
          disabled={isLoading}
        >
          <RefreshCw
            className={`mr-1.5 size-3.5 ${isLoading ? 'animate-spin' : ''}`}
          />
          {t('plugins.logsRefresh')}
        </Button>
        <Button
          type="button"
          variant={autoRefresh ? 'default' : 'outline'}
          size="sm"
          className="h-8"
          onClick={() => setAutoRefresh((v) => !v)}
        >
          {autoRefresh
            ? t('plugins.logsAutoRefreshOn')
            : t('plugins.logsAutoRefreshOff')}
        </Button>
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="min-h-0 flex-1 overflow-auto bg-gray-50 px-6 py-3 font-mono text-xs leading-relaxed dark:bg-gray-900/40"
      >
        {logs.length === 0 ? (
          <div className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
            {t('plugins.logsEmpty')}
          </div>
        ) : (
          logs.map((entry, idx) => (
            <div
              key={`${entry.ts}-${idx}`}
              className={`whitespace-pre-wrap break-all ${levelClassName(
                entry.level,
              )}`}
            >
              {entry.text}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
