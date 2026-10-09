'use client';

import { useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import './EventRoutingHelp.css';

const routeColors = [
  'text-sky-700 dark:text-sky-300 [&_.route-node]:border-sky-200 [&_.route-node]:bg-sky-50 dark:[&_.route-node]:border-sky-800 dark:[&_.route-node]:bg-sky-950/40',
  'text-amber-700 dark:text-amber-300 [&_.route-node]:border-amber-200 [&_.route-node]:bg-amber-50 dark:[&_.route-node]:border-amber-800 dark:[&_.route-node]:bg-amber-950/40',
  'text-emerald-700 dark:text-emerald-300 [&_.route-node]:border-emerald-200 [&_.route-node]:bg-emerald-50 dark:[&_.route-node]:border-emerald-800 dark:[&_.route-node]:bg-emerald-950/40',
];

export default function EventRoutingHelp() {
  const { t } = useTranslation();
  const [paused, setPaused] = useState(false);
  const text = (key: string) => t(`bots.routingHelp.${key}`);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" aria-label={text('title')} className="inline-flex size-6 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
            <circle cx="12" cy="12" r="9" /><path d="M12 11v6" /><circle cx="12" cy="7.5" r=".7" fill="currentColor" />
          </svg>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(32rem,calc(100vw-2rem))] max-h-[80vh] overflow-y-auto p-5">
        <h3 className="text-sm font-semibold">{text('title')}</h3>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{text('intro')}</p>
        <div className="my-4 overflow-hidden rounded-xl border bg-muted/20 p-3">
          <div className="mb-3 grid grid-cols-2 text-xs text-muted-foreground">
            <span>{text('events')}</span><span className="text-right">{text('agents')}</span>
          </div>
          <div className={`routing-help space-y-3 ${paused ? 'routing-help-paused' : ''}`}>
            {['message', 'friend', 'group'].map((kind, index) => (
              <div key={kind} className={`grid grid-cols-[minmax(0,1fr)_48px_minmax(0,1fr)] items-center ${routeColors[index]}`} style={{ '--route-delay': `${index * 1.6}s` } as CSSProperties}>
                <div className="route-node rounded-lg border px-2 py-3 text-center text-xs leading-5">{text(kind)}</div>
                <div className="relative h-8" aria-hidden="true">
                  <svg viewBox="0 0 48 32" className="h-full w-full opacity-30"><path d="M0 16H45m-5-4 5 4-5 4" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
                  <span className="routing-help-dot absolute left-0 top-[13px] size-1.5 rounded-full bg-current" />
                </div>
                <div className="route-node routing-help-target rounded-lg border px-2 py-3 text-center text-xs leading-5">{text(`${kind}Action`)}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between gap-3 text-xs text-muted-foreground">
            <span>{text('rules')}</span>
            <button type="button" className="shrink-0 rounded px-1 underline underline-offset-4 focus-visible:ring-2 focus-visible:ring-ring motion-reduce:hidden" onClick={() => setPaused(!paused)}>{text(paused ? 'play' : 'pause')}</button>
          </div>
        </div>
        <p className="text-sm leading-6">{text('instructions')}</p>
        <div className="mt-4 border-t pt-3 text-xs leading-6 text-muted-foreground">
          <p>{text('plugin')}</p>
          <a href="https://langbot.app/docs/zh/plugin/dev/components/runner" target="_blank" rel="noopener noreferrer" className="font-medium text-foreground underline underline-offset-4">{text('docs')} ↗</a>
        </div>
      </PopoverContent>
    </Popover>
  );
}
