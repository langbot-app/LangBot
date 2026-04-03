

import { useState } from 'react';
import { BotLog } from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';
import { httpClient } from '@/app/infra/http/HttpClient';
import { PhotoProvider } from 'react-photo-view';
import { useTranslation } from 'react-i18next';
import { Check, ChevronDown, ChevronRight, Copy } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const LEVEL_STYLES: Record<string, string> = {
  error: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  warning:
    'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  info: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  debug: 'bg-muted text-muted-foreground',
};

const SHORT_TEXT_LIMIT = 120;

export function BotLogCard({
  botLog,
  defaultExpanded = false,
}: {
  botLog: BotLog;
  defaultExpanded?: boolean;
}) {
  const { t } = useTranslation();
  const baseURL = httpClient.getBaseUrl();
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(defaultExpanded);

  function copySessionId() {
    const text = botLog.message_session_id;
    if (navigator.clipboard?.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
          toast.success(t('common.copySuccess'));
        })
        .catch(() => fallbackCopy(text));
    } else {
      fallbackCopy(text);
    }
  }

  function fallbackCopy(text: string) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
      document.execCommand('copy');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast.success(t('common.copySuccess'));
    } catch {
      toast.error(t('common.copyFailed'));
    }
    document.body.removeChild(ta);
  }

  function formatTime(timestamp: number) {
    const now = new Date();
    const date = new Date(timestamp * 1000);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');

    const isToday = now.toDateString() === date.toDateString();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const isYesterday = yesterday.toDateString() === date.toDateString();
    const isThisYear = now.getFullYear() === date.getFullYear();

    if (isToday) return `${hours}:${minutes}`;
    if (isYesterday) return `${t('bots.yesterday')} ${hours}:${minutes}`;
    if (isThisYear)
      return t('bots.dateFormat', {
        month: date.getMonth() + 1,
        day: date.getDate(),
      });
    return t('bots.earlier');
  }

  const needsExpand =
    botLog.text.length > SHORT_TEXT_LIMIT || botLog.images.length > 0;
  const levelStyle =
    LEVEL_STYLES[botLog.level.toLowerCase()] ?? LEVEL_STYLES.debug;

  return (
    <div className="rounded-lg border bg-card px-3.5 py-3 transition-colors hover:border-border/80">
      {/* Header: level badge, session id, expand toggle, timestamp */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {/* Level badge */}
          <span
            className={cn(
              'inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase leading-none',
              levelStyle,
            )}
          >
            {botLog.level}
          </span>

          {/* Session ID */}
          {botLog.message_session_id && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                copySessionId();
              }}
              title={t('common.clickToCopy')}
              className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-[11px] font-mono text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors truncate max-w-48 cursor-pointer"
            >
              {copied ? (
                <Check className="size-3 shrink-0 text-green-600" />
              ) : (
                <Copy className="size-3 shrink-0" />
              )}
              <span className="truncate">{botLog.message_session_id}</span>
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {needsExpand && (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-0.5 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
            >
              {expanded ? (
                <>
                  <ChevronDown className="size-3" />
                  {t('bots.collapse')}
                </>
              ) : (
                <>
                  <ChevronRight className="size-3" />
                  {t('bots.viewDetails')}
                </>
              )}
            </button>
          )}
          <span className="text-[11px] text-muted-foreground tabular-nums">
            {formatTime(botLog.timestamp)}
          </span>
        </div>
      </div>

      {/* Log text */}
      <div className="mt-2 text-sm leading-relaxed text-foreground whitespace-pre-wrap break-words overflow-wrap-anywhere">
        {expanded
          ? botLog.text
          : botLog.text.length > SHORT_TEXT_LIMIT
            ? botLog.text.slice(0, SHORT_TEXT_LIMIT) + '...'
            : botLog.text}
      </div>

      {/* Images (expanded) */}
      {expanded && botLog.images.length > 0 && (
        <PhotoProvider>
          <div className="flex flex-wrap gap-2 mt-2.5">
            {botLog.images.map((item) => (
              <img
                key={item}
                src={`${baseURL}/api/v1/files/image/${item}`}
                alt=""
                className="max-w-xs rounded-md cursor-pointer hover:opacity-90 transition-opacity"
              />
            ))}
          </div>
        </PhotoProvider>
      )}

      {/* Image count hint (collapsed) */}
      {!expanded && botLog.images.length > 0 && (
        <div className="mt-1.5 text-[11px] text-muted-foreground">
          {botLog.images.length} {t('bots.imagesAttached')}
        </div>
      )}
    </div>
  );
}
