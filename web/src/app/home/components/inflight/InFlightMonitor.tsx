import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { backendClient, useCurrentWorkspace } from '@/app/infra/http';
import type { InflightSnapshot } from '@/app/infra/entities/api/monitoring-executions';
import { Button } from '@/components/ui/button';
import ExecutionDetailSheet, {
  type ExecutionSelection,
} from '@/app/home/monitoring/components/executions/ExecutionDetailSheet';
import { executionStatusLabel } from '@/app/home/monitoring/components/executions/ExecutionTable';
import styles from './inflight.module.css';
import ExecutionNodes from './ExecutionNodes';
import { useEdgeDock } from './useEdgeDock';
import DockIcon from './DockIcon';

type Row = InflightSnapshot['items'][number] & { settledAt?: number };
const keyOf = (row: Row) => `${row.source}:${row.id}`;
const active = (row: Row) => ['running', 'queued'].includes(row.status_group);

function stage(row: Row): string {
  if (!active(row)) return row.status_group;
  if (row.status_group === 'queued') return 'queued';
  const event = row.progress_event || '';
  if (event.startsWith('interaction.')) return 'waiting';
  if (event.startsWith('tool.') && !event.endsWith('completed')) return 'tool';
  if (event.includes('reasoning')) return 'thinking';
  if (event === 'message.completed') return 'replying';
  if (event.startsWith('message.')) return 'generating';
  return 'running';
}

function WorkspaceMonitor() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<Row[]>([]);
  const dock = useEdgeDock(true);
  const { collapsed, setCollapsed } = dock;
  const [connected, setConnected] = useState(true);
  const [total, setTotal] = useState(0);
  const [truncated, setTruncated] = useState(false);
  const [selected, setSelected] = useState<ExecutionSelection | null>(null);
  const [now, setNow] = useState(Date.now());
  const known = useRef(new Map<string, Row>());
  const [autoCollapse, setAutoCollapse] = useState(() => {
    try {
      return localStorage.getItem('langbot.inflight.autoCollapse') !== 'false';
    } catch {
      return true;
    }
  });
  // Keep terminal results visible until their exit animation has finished.
  const hasWork = total > 0 || rows.length > 0;
  useEffect(() => {
    try {
      localStorage.setItem(
        'langbot.inflight.autoCollapse',
        String(autoCollapse),
      );
    } catch {
      /* Optional preference. */
    }
  }, [autoCollapse]);
  useEffect(() => {
    if (autoCollapse) setCollapsed(!hasWork);
  }, [autoCollapse, hasWork, setCollapsed]);

  useEffect(() => {
    let disposed = false;
    let first = true;
    let controller: AbortController | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    const seen = new Set<string>();
    const accept = (snapshot: InflightSnapshot) => {
      const time = Date.now();
      const present = new Set(snapshot.items.map(keyOf));
      // A reconnect is a fresh authoritative snapshot. Do not leave vanished
      // executions spinning forever or infer successful completion from absence.
      if (!snapshot.truncated) {
        for (const [key, row] of known.current) {
          if (active(row) && !present.has(key)) known.current.delete(key);
        }
      }
      for (const row of snapshot.items) {
        const key = keyOf(row);
        const previous = known.current.get(key);
        if (active(row) || previous || (!first && !seen.has(key))) {
          known.current.set(key, {
            ...row,
            settledAt: active(row) ? undefined : (previous?.settledAt ?? time),
          });
        }
        seen.add(key);
      }
      // Retain terminal results briefly, including runs completed between frames.
      for (const [key, row] of known.current) {
        if (row.settledAt && time - row.settledAt > 8000)
          known.current.delete(key);
      }
      while (seen.size > 2000) seen.delete(seen.values().next().value!);
      while (known.current.size > 200)
        known.current.delete(known.current.keys().next().value!);
      first = false;
      setRows([...known.current.values()]);
      setTotal(snapshot.active_total);
      setTruncated(snapshot.truncated);
    };
    const connect = async () => {
      if (disposed || document.hidden) return;
      controller = new AbortController();
      const connection = controller;
      try {
        await backendClient.streamInflight((frame) => {
          if (disposed || connection.signal.aborted) return;
          failures = 0;
          if (frame.kind !== 'heartbeat')
            setConnected(frame.kind !== 'unavailable');
          if (frame.kind === 'snapshot') accept(frame.data);
        }, connection.signal);
      } catch {
        if (!disposed && !connection.signal.aborted) {
          setConnected(false);
          failures += 1;
        }
      }
      if (!disposed && !connection.signal.aborted && !document.hidden) {
        retry = setTimeout(
          connect,
          Math.min(30000, 1000 * 2 ** failures) + Math.random() * 500,
        );
      }
    };
    const visibility = () => {
      clearTimeout(retry);
      controller?.abort();
      if (!document.hidden) retry = setTimeout(connect, 100);
    };
    void connect();
    document.addEventListener('visibilitychange', visibility);
    const tick = setInterval(() => {
      const time = Date.now();
      let changed = false;
      for (const [key, row] of known.current) {
        if (row.settledAt && time - row.settledAt > 8000) {
          known.current.delete(key);
          changed = true;
        }
      }
      if (changed) setRows([...known.current.values()]);
      if (known.current.size) setNow(time);
    }, 1000);
    return () => {
      disposed = true;
      controller?.abort();
      clearTimeout(retry);
      clearInterval(tick);
      document.removeEventListener('visibilitychange', visibility);
    };
  }, []);

  const ordered = [...rows].sort(
    (a, b) =>
      Number(active(b)) - Number(active(a)) ||
      (b.created_at_ms ?? 0) - (a.created_at_ms ?? 0),
  );
  return (
    <>
      <aside
        ref={dock.panel}
        style={{ width: collapsed ? 26 : 'min(320px, calc(100vw - 24px))' }}
        className={`fixed top-0 right-0 z-40 max-h-[calc(100dvh-24px)] overflow-y-auto rounded-l-xl border border-r-0 bg-popover text-popover-foreground shadow-lg ${styles.panel}`}
        aria-label={t('inflight.title')}
      >
        <div
          key={collapsed ? 'collapsed' : 'expanded'}
          className={styles.dockContent}
        >
          {collapsed ? (
            <button
              type="button"
              {...dock.handle}
              className="flex h-12 w-full touch-none select-none flex-col items-center justify-center gap-0.5 bg-[#2288ee] text-white hover:bg-[#2277e0] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring active:cursor-grabbing"
              title={`${t('inflight.expand')} · ${t('inflight.move')}`}
              aria-label={`${t('inflight.title')}: ${total}. ${t('inflight.expand')}. ${t('inflight.move')}`}
              aria-expanded={false}
              onClick={(event) => {
                if (event.detail === 0 || !dock.suppressClick.current)
                  setCollapsed(false);
              }}
            >
              <DockIcon kind="activity" />
              <span
                className={`text-[10px] font-mono ${connected ? '' : 'text-amber-100'}`}
              >
                {total}
              </span>
            </button>
          ) : (
            <div className="flex items-center justify-between gap-2 px-3 py-2">
              <button
                type="button"
                {...dock.handle}
                aria-label={t('inflight.move')}
                title={t('inflight.move')}
                className="flex min-w-0 flex-1 touch-none select-none items-center gap-2 rounded py-1 text-xs font-medium cursor-grab active:cursor-grabbing focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className={connected ? 'text-primary' : 'text-amber-600'}>
                  <DockIcon kind="activity" />
                </span>
                {t('inflight.title')}{' '}
                <span className="font-mono text-muted-foreground">{total}</span>
                <span className="ml-auto text-muted-foreground">
                  <DockIcon kind="move" />
                </span>
              </button>
              <Button
                variant="ghost"
                size="sm"
                className={`h-7 shrink-0 gap-1 px-2 text-[10px] ${autoCollapse ? 'bg-primary/10 text-primary hover:bg-primary/15' : 'text-muted-foreground'}`}
                aria-pressed={autoCollapse}
                title={t('inflight.autoCollapse')}
                onClick={() => setAutoCollapse((enabled) => !enabled)}
              >
                {autoCollapse && <DockIcon kind="completed" />}
                {t('inflight.autoCollapse')}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="size-8"
                aria-label={t('inflight.collapse')}
                title={t('inflight.collapse')}
                aria-expanded={true}
                onClick={() => setCollapsed(true)}
              >
                <DockIcon kind="collapse" />
              </Button>
            </div>
          )}
          {!collapsed && (
            <>
              {!connected && (
                <p
                  className="border-t px-4 py-2 text-xs text-amber-600"
                  role="status"
                >
                  {t('inflight.reconnecting')}
                </p>
              )}
              <div className="max-h-[min(420px,55dvh)] overflow-y-auto border-t">
                {rows.length === 0 && connected && (
                  <div
                    className="flex flex-col items-center gap-2 px-4 py-8 text-muted-foreground"
                    role="status"
                  >
                    <DockIcon kind="completed" />
                    <p className="text-xs">{t('inflight.empty')}</p>
                  </div>
                )}
                {ordered.slice(0, 20).map((row) => {
                  const phase = stage(row);
                  const stageKey = `inflight.${phase}`;
                  const label = t(stageKey, {
                    defaultValue: executionStatusLabel(row, t),
                  });
                  const elapsed = Math.max(
                    0,
                    Math.floor(
                      ((row.finished_at_ms ?? row.settledAt ?? now) -
                        (row.started_at_ms ?? row.created_at_ms ?? now)) /
                        1000,
                    ),
                  );
                  const eventKey = `bots.eventNames.${(row.event_type || row.title).replaceAll('.', '_')}`;
                  const processorUrl =
                    row.target_id &&
                    [
                      'pipeline',
                      'agent',
                      'processor',
                      'event_processor',
                    ].includes(row.target_kind)
                      ? `/home/${row.target_kind === 'pipeline' ? 'pipelines' : 'agents'}?id=${encodeURIComponent(row.target_id)}&tab=logs`
                      : null;
                  const leaving =
                    !!row.settledAt && now - row.settledAt >= 7000;
                  return (
                    <div
                      key={keyOf(row)}
                      className={`${styles.task} ${leaving ? styles.leaving : ''} border-b px-3 py-2 last:border-b-0`}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={
                            row.has_error ? 'text-destructive' : 'text-primary'
                          }
                          title={label}
                          role="img"
                          aria-label={label}
                        >
                          <DockIcon kind={active(row) ? 'event' : phase} />
                        </span>
                        <button
                          type="button"
                          onClick={() => setSelected(row)}
                          className="min-w-0 flex-1 truncate rounded py-1 text-left text-xs hover:underline focus-visible:ring-2 focus-visible:ring-ring"
                          title={`${t('inflight.details')}: ${row.input_preview || row.event_type || row.title}`}
                          aria-label={`${t('inflight.details')}: ${row.event_type || row.title}`}
                        >
                          {t(eventKey, {
                            defaultValue: row.event_type || row.title,
                          })}
                        </button>
                        <span className="shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground">
                          {elapsed}s
                        </span>
                      </div>
                      <ExecutionNodes
                        row={row}
                        processorUrl={processorUrl}
                        running={active(row) && connected}
                      />
                      <div
                        className="mt-1.5 h-1 overflow-hidden rounded-full bg-muted"
                        role="progressbar"
                        aria-label={label}
                        {...(!active(row)
                          ? {
                              'aria-valuenow': 100,
                              'aria-valuemin': 0,
                              'aria-valuemax': 100,
                            }
                          : {})}
                      >
                        <div
                          className={`h-full rounded-full ${row.has_error ? 'bg-destructive' : 'bg-primary'} ${active(row) && connected ? styles.active : 'w-full'}`}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
              {(truncated || rows.length > 20) && (
                <p className="border-t px-4 py-2 text-xs text-muted-foreground">
                  {t('inflight.limited')}
                </p>
              )}
            </>
          )}
        </div>
      </aside>
      <ExecutionDetailSheet
        row={selected}
        onSelect={setSelected}
        onClose={() => setSelected(null)}
      />
    </>
  );
}

export default function InFlightMonitor() {
  const workspace = useCurrentWorkspace();
  if (!workspace?.permissions.includes('resource.view')) return null;
  return <WorkspaceMonitor key={workspace.workspace.uuid} />;
}
