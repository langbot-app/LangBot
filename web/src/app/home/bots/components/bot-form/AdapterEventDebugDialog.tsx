'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Activity,
  AlertCircle,
  ChevronDown,
  RadioTower,
  Trash2,
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { backendClient } from '@/app/infra/http';
import type { BotLog } from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';
import {
  eventPatternDescription,
  eventPatternLabel,
} from '@/app/home/components/event-patterns/event-pattern-groups';

const POLL_INTERVAL_MS = 1200;
const MAX_VISIBLE_EVENTS = 50;

interface ObservedAdapterEvent {
  seqId: number;
  timestamp: number;
  eventType: string;
  eventData: Record<string, unknown>;
}

type ListenerState = 'preparing' | 'listening' | 'error';

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function observedEventFromLog(log: BotLog): ObservedAdapterEvent | null {
  const metadata = log.metadata;
  if (!isRecord(metadata) || metadata.kind !== 'adapter_event_received') {
    return null;
  }

  const eventType = metadata.event_type;
  if (typeof eventType !== 'string' || !eventType) return null;

  return {
    seqId: log.seq_id,
    timestamp: log.timestamp,
    eventType,
    eventData: isRecord(metadata.event_data) ? metadata.event_data : {},
  };
}

function findEventPreview(value: unknown, depth = 0): string | null {
  if (depth > 4 || value === null || value === undefined) return null;
  if (Array.isArray(value)) {
    for (const item of value) {
      const preview = findEventPreview(item, depth + 1);
      if (preview) return preview;
    }
    return null;
  }
  if (!isRecord(value)) return null;

  for (const key of ['message_text', 'text', 'action']) {
    const candidate = value[key];
    if (typeof candidate === 'string' && candidate.trim()) {
      const trimmed = candidate.trim();
      return trimmed.length > 160 ? `${trimmed.slice(0, 160)}…` : trimmed;
    }
  }
  for (const child of Object.values(value)) {
    const preview = findEventPreview(child, depth + 1);
    if (preview) return preview;
  }
  return null;
}

export default function AdapterEventDebugDialog({
  botId,
  adapterLabel,
}: {
  botId?: string;
  adapterLabel: string;
}) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [listenerState, setListenerState] =
    useState<ListenerState>('preparing');
  const [events, setEvents] = useState<ObservedAdapterEvent[]>([]);
  const baselineSeqRef = useRef<number | null>(null);
  const pollInFlightRef = useRef(false);

  const platformName = adapterLabel || t('bots.adapterEventCurrentPlatform');

  const pollLogs = useCallback(async () => {
    if (!botId || pollInFlightRef.current) return;
    pollInFlightRef.current = true;
    try {
      const response = await backendClient.getBotLogs(botId, {
        from_index: -1,
        max_count: 100,
      });
      const latestSeq = response.logs.reduce(
        (maximum, log) => Math.max(maximum, log.seq_id),
        -1,
      );

      if (baselineSeqRef.current === null) {
        baselineSeqRef.current = latestSeq;
        setListenerState('listening');
        return;
      }

      const baseline = baselineSeqRef.current;
      const newlyObserved = response.logs
        .filter((log) => log.seq_id > baseline)
        .map(observedEventFromLog)
        .filter((event): event is ObservedAdapterEvent => event !== null);

      if (newlyObserved.length > 0) {
        setEvents((current) => {
          const bySeqId = new Map(
            [...newlyObserved, ...current].map((event) => [event.seqId, event]),
          );
          return Array.from(bySeqId.values())
            .sort((left, right) => right.seqId - left.seqId)
            .slice(0, MAX_VISIBLE_EVENTS);
        });
      }
      baselineSeqRef.current = Math.max(baseline, latestSeq);
      setListenerState('listening');
    } catch {
      setListenerState('error');
    } finally {
      pollInFlightRef.current = false;
    }
  }, [botId]);

  useEffect(() => {
    if (!open || !botId) return;

    baselineSeqRef.current = null;
    pollInFlightRef.current = false;
    setEvents([]);
    setListenerState('preparing');
    void pollLogs();
    const interval = window.setInterval(
      () => void pollLogs(),
      POLL_INTERVAL_MS,
    );
    return () => window.clearInterval(interval);
  }, [botId, open, pollLogs]);

  const status = useMemo(() => {
    if (listenerState === 'error') {
      return {
        text: t('bots.adapterEventListenerUnavailable'),
        dot: 'bg-destructive',
      };
    }
    if (listenerState === 'listening') {
      return {
        text: t('bots.adapterEventListening'),
        dot: 'bg-emerald-500',
      };
    }
    return {
      text: t('bots.adapterEventPreparing'),
      dot: 'bg-amber-500',
    };
  }, [listenerState, t]);

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={!botId}
        onClick={() => setOpen(true)}
        title={!botId ? t('bots.adapterEventNeedsSavedBot') : undefined}
      >
        <RadioTower className="mr-1 h-4 w-4" />
        {t('bots.adapterEventDebugAction')}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <div className="flex flex-wrap items-center gap-2 pr-8">
              <DialogTitle>{t('bots.adapterEventDebugTitle')}</DialogTitle>
              <Badge variant="outline" className="gap-1.5 font-normal">
                <span className={`size-2 rounded-full ${status.dot}`} />
                {status.text}
              </Badge>
            </div>
            <DialogDescription>
              {t('bots.adapterEventDebugDescription', {
                platform: platformName,
              })}
            </DialogDescription>
          </DialogHeader>

          <Alert className="bg-muted/30">
            <Activity className="h-4 w-4" />
            <AlertDescription>
              {t('bots.adapterEventObserveOnly')}
            </AlertDescription>
          </Alert>

          {listenerState === 'error' && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {t('bots.adapterEventLoadFailed')}
              </AlertDescription>
            </Alert>
          )}

          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-medium">
              {t('bots.adapterEventReceivedCount', { count: events.length })}
            </p>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={events.length === 0}
              onClick={() => setEvents([])}
            >
              <Trash2 className="mr-1 h-4 w-4" />
              {t('bots.adapterEventClear')}
            </Button>
          </div>

          <ScrollArea className="h-[min(52vh,420px)] rounded-lg border">
            {events.length === 0 ? (
              <div className="flex h-full min-h-64 flex-col items-center justify-center px-6 text-center">
                <RadioTower className="mb-3 h-8 w-8 text-muted-foreground" />
                <p className="font-medium">
                  {t('bots.adapterEventEmptyTitle')}
                </p>
                <p className="mt-1 max-w-md text-sm text-muted-foreground">
                  {t('bots.adapterEventEmptyDescription', {
                    platform: platformName,
                  })}
                </p>
              </div>
            ) : (
              <div className="space-y-3 p-3">
                {events.map((event) => {
                  const preview = findEventPreview(event.eventData);
                  return (
                    <Card key={event.seqId} className="gap-0 py-0">
                      <CardContent className="p-4">
                        <div className="flex min-w-0 items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="font-medium">
                              {eventPatternLabel(event.eventType, t)}
                            </p>
                            <code className="mt-1 block truncate text-xs text-muted-foreground">
                              {event.eventType}
                            </code>
                          </div>
                          <time className="shrink-0 text-xs text-muted-foreground">
                            {new Date(
                              event.timestamp * 1000,
                            ).toLocaleTimeString(i18n.language, {
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit',
                            })}
                          </time>
                        </div>
                        <p className="mt-2 text-sm text-muted-foreground">
                          {preview ||
                            eventPatternDescription(event.eventType, t)}
                        </p>
                        <Collapsible className="mt-3">
                          <CollapsibleTrigger asChild>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-8 px-2 text-xs text-muted-foreground"
                            >
                              {t('bots.adapterEventData')}
                              <ChevronDown className="ml-1 h-3.5 w-3.5" />
                            </Button>
                          </CollapsibleTrigger>
                          <CollapsibleContent>
                            <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs leading-relaxed">
                              {JSON.stringify(event.eventData, null, 2)}
                            </pre>
                          </CollapsibleContent>
                        </Collapsible>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </ScrollArea>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              {t('common.close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
