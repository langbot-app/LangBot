import LoadErrorState from '@/components/LoadErrorState';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { backendClient, useCurrentWorkspace } from '@/app/infra/http';
import type {
  ExecutionDetail,
  ExecutionDetailItem,
  ExecutionRow,
  ExecutionSection,
} from '@/app/infra/entities/api/monitoring-executions';
import { ExecutionValue as Value, hasExecutionValue } from './ExecutionValue';
import { formatRunDuration } from '@/app/home/agents/components/processor-run-timing';
import { formatDateTime } from '../../utils/dateUtils';
import {
  executionKindLabel,
  ExecutionKindBadge,
  executionProcessorLabel,
  executionStatusLabel,
} from './ExecutionTable';

export type ExecutionSelection = Pick<ExecutionRow, 'id'> & {
  source: ExecutionRow['source'] | 'auto';
};

const mainSections: ExecutionSection[] = ['inputs', 'outputs', 'deliveries'];

// Keep transport metadata in the payload disclosure, not in the message body.
function messageBody(value: unknown): unknown {
  if (typeof value === 'string') {
    if (/^\s*[\[{]/.test(value)) {
      try { return messageBody(JSON.parse(value)); } catch { /* Plain text. */ }
    }
    return value;
  }
  if (Array.isArray(value)) return value.map(messageBody).filter((item) => item != null && item !== '');
  if (!value || typeof value !== 'object') return null;
  const data = value as Record<string, unknown>;
  if (['Image', 'File', 'Voice', 'At', 'AtAll', 'Quote'].includes(String(data.type))) return value;
  for (const key of ['text', 'content', 'message_chain', 'message', 'root']) {
    if (data[key] != null) return messageBody(data[key]);
  }
  return null;
}
const secondarySections: ExecutionSection[] = [
  'related',
  'conversation',
  'llm_calls',
  'tool_calls',
  'errors',
  'events',
];

export default function ExecutionDetailSheet({
  row,
  onClose,
  onSelect,
}: {
  row: ExecutionSelection | null;
  onClose: () => void;
  onSelect: (row: ExecutionSelection) => void;
}) {
  const { t } = useTranslation();
  const workspace = useCurrentWorkspace()?.workspace.uuid;
  const [detail, setDetail] = useState<ExecutionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [sectionError, setSectionError] = useState<ExecutionSection | null>(
    null,
  );
  const [busy, setBusy] = useState<ExecutionSection | null>(null);
  const [refresh, setRefresh] = useState(0);
  const request = useRef(0);
  const identity = `${workspace}:${row?.source}:${row?.id}`;
  const requestedIdentity = useRef('');
  const [loadedIdentity, setLoadedIdentity] = useState('');
  const visible = loadedIdentity === identity ? detail : null;
  const id = row?.id;
  const source = row?.source;
  useEffect(() => {
    const version = ++request.current;
    // Refresh the current trace in place so its scroll position and expanded
    // disclosures survive polling. Only a different selection starts empty.
    if (requestedIdentity.current !== identity) {
      setDetail(null);
      requestedIdentity.current = identity;
    }
    setError(false);
    setSectionError(null);
    setBusy(null);
    if (!id || !source) {
      setLoading(false);
      return;
    }
    setLoading(true);
    backendClient
      .getExecutionDetail(source, id)
      .then((result) => {
        if (version !== request.current) return;
        setDetail(result);
        setLoadedIdentity(identity);
      })
      .catch(() => {
        if (version === request.current) setError(true);
      })
      .finally(() => {
        if (version === request.current) setLoading(false);
      });
    return () => {
      request.current += 1;
    };
  }, [id, source, workspace, identity, refresh]);
  const status = visible?.row.status_group;
  useEffect(() => {
    if (!['running', 'queued'].includes(status ?? '')) return;
    // Do not discard paged history with a background refresh.
    if (
      Object.values(visible?.pages ?? {}).some((page) => page.next_offset > 100)
    )
      return;
    const timer = setInterval(() => setRefresh((value) => value + 1), 5000);
    return () => clearInterval(timer);
  }, [status, visible]);
  const loadMore = async (section: ExecutionSection) => {
    if (!visible || !row || busy) return;
    const version = request.current;
    setBusy(section);
    setSectionError(null);
    try {
      const result = await backendClient.getExecutionDetail(
        row.source,
        row.id,
        { section, offset: visible.pages[section]?.next_offset ?? 0 },
      );
      if (version !== request.current) return;
      const next = result.pages[section];
      if (next)
        setDetail(
          (previous) =>
            previous && {
              ...previous,
              pages: {
                ...previous.pages,
                [section]: {
                  ...next,
                  items: [
                    ...(previous.pages[section]?.items ?? []),
                    ...next.items,
                  ],
                },
              },
            },
        );
    } catch {
      if (version === request.current) setSectionError(section);
    } finally {
      if (version === request.current) setBusy(null);
    }
  };
  const renderItem = (section: ExecutionSection, item: ExecutionDetailItem) => {
    if (section === 'related') {
      const related = item as unknown as ExecutionRow;
      return (
        <Button
          variant="outline"
          className="h-auto w-full justify-between whitespace-normal py-3 text-left"
          onClick={() => onSelect(related)}
        >
          <span>
            {executionProcessorLabel(related)} ·{' '}
            {executionKindLabel(related, t)}
          </span>
          <Badge status={related.status_group}>
            {executionStatusLabel(related, t)}
          </Badge>
        </Button>
      );
    }
    const content = [
      'inputs',
      'outputs',
      'deliveries',
      'conversation',
    ].includes(section);
    const body = messageBody(item.content);
    const title = content
      ? [
          item.actor_name || item.actor_id,
          item.event_type,
          item.role &&
            t(`monitoring.unified.roles.${item.role}`, {
              defaultValue: item.role,
            }),
        ]
          .filter(Boolean)
          .join(' · ')
      : String(
          item.model_name ||
            item.tool_name ||
            item.error_type ||
            item.type ||
            item.id,
        );
    return (
      <div className="min-w-0 space-y-3 rounded-lg border bg-background p-4">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <span className="break-all">{title}</span>
          <span>
            {item.timestamp_ms
              ? formatDateTime(new Date(item.timestamp_ms))
              : typeof item.timestamp === 'string'
                ? item.timestamp
                : ''}
          </span>
          {item.status && (
            <Badge
              status={item.status}
            >
              {t(`monitoring.execution.status.${['success', 'delivered'].includes(item.status) ? 'completed' : item.status}`, { defaultValue: item.status })}
            </Badge>
          )}
        </div>
        {content ? (
          <>
            <div className="text-sm leading-7">
              {hasExecutionValue(body) ? <Value value={body} /> : <p className="text-muted-foreground">{t('monitoring.unified.noRecords')}</p>}
            </div>
            <Value value={item.attachments} />
            {item.origin === 'generated' && section === 'conversation' && (
              <Badge variant="outline">{t('monitoring.unified.outputs')}</Badge>
            )}
            {item.delivery?.delivery_error ? (
              <p className="text-sm text-destructive">
                {String(item.delivery.delivery_error)}
              </p>
            ) : null}
            <details className="border-t pt-2">
              <summary className="cursor-pointer text-xs text-muted-foreground">{t('monitoring.unified.payload')}</summary>
              <div className="mt-3 max-h-80 overflow-auto rounded-md bg-muted/40 p-3">
                <Value value={item} />
              </div>
            </details>
          </>
        ) : (
          <>
            <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
              {typeof item.duration === 'number' && (
                <span>{formatRunDuration(item.duration)}</span>
              )}
              {typeof item.total_tokens === 'number' && (
                <span>{item.total_tokens.toLocaleString()} Token</span>
              )}
            </div>
            <Value value={item.error_message} />
            <details>
              <summary className="cursor-pointer text-xs text-muted-foreground">
                {t('monitoring.unified.payload')}
              </summary>
              <div className="mt-2">
                <Value value={section === 'events' ? item.data : item} />
              </div>
            </details>
          </>
        )}
      </div>
    );
  };
  const renderSection = (section: ExecutionSection, primary = false) => {
    const page = visible?.pages[section];
    if (
      !page ||
      (!primary && page.items.length === 0 && section !== 'conversation')
    )
      return null;
    const body = (
      <div className="mt-3 space-y-3">
        {section === 'conversation' && (
          <p className="text-xs text-muted-foreground">
            {t('monitoring.unified.contextHint')}
          </p>
        )}
        {page.items.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {t('monitoring.unified.noRecords')}
          </p>
        )}
        {page.items.map((item, i) => (
          <div key={`${item.id}-${i}`}>{renderItem(section, item)}</div>
        ))}
        {sectionError === section && (
          <LoadErrorState compact title={t('monitoring.execution.detail.loadError')} onRetry={() => loadMore(section)} />
        )}
        {page.has_more && (
          <Button
            variant="outline"
            size="sm"
            disabled={busy !== null}
            onClick={() => loadMore(section)}
          >
            {t('monitoring.unified.loadMore')}
          </Button>
        )}
      </div>
    );
    const title = `${t(`monitoring.unified.${section}`)} (${page.items.length}${page.has_more ? '+' : ''})`;
    return primary ? (
      <section key={section} className="space-y-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <span className="flex size-6 items-center justify-center rounded-full bg-muted text-xs text-muted-foreground">{mainSections.indexOf(section) + 1}</span>
          {title}
        </h3>
        {body}
      </section>
    ) : (
      <details key={section} open={section === 'errors' ? true : undefined} className={`rounded-lg border p-3 ${section === 'errors' ? 'border-red-500/25 bg-red-500/5' : ''}`}>
        <summary className="cursor-pointer text-sm font-medium">
          {title}
        </summary>
        {body}
      </details>
    );
  };
  const record = visible?.row;
  const href = record?.target_id
    ? record.target_kind === 'pipeline'
      ? `/home/pipelines?id=${encodeURIComponent(record.target_id)}`
      : ['agent', 'event_processor', 'processor'].includes(record.target_kind)
        ? `/home/agents?id=${encodeURIComponent(record.target_id)}`
        : null
    : null;
  return (
    <Sheet
      open={row !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent side="right" className="w-full p-0 sm:max-w-3xl">
        <SheetHeader className="sr-only">
          <SheetTitle>{t('monitoring.execution.detail.title')}</SheetTitle>
          <SheetDescription>
            {t('monitoring.execution.detail.a11yDescription')}
          </SheetDescription>
        </SheetHeader>
        <ScrollArea className="h-full">
          <div className="space-y-5 p-5 sm:p-6">
            <div className="flex items-start justify-between gap-3 pr-8">
              <h2 className="text-lg font-semibold">
                {record
                  ? record.source === 'event'
                    ? t('monitoring.unified.unhandled')
                    : executionProcessorLabel(record)
                  : t('monitoring.execution.detail.title')}
              </h2>
              <Button
                variant="ghost"
                size="icon"
                disabled={loading}
                aria-label={t('monitoring.refreshData')}
                title={error ? t('monitoring.execution.detail.loadError') : t('monitoring.refreshData')}
                onClick={() => setRefresh((value) => value + 1)}
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''} ${error ? 'text-destructive' : ''}`} />
              </Button>
            </div>
            {loading && !visible && <Skeleton className="h-36 w-full" />}
            {error && !visible && (
              <LoadErrorState title={t('monitoring.execution.detail.loadError')} onRetry={() => setRefresh((value) => value + 1)} />
            )}
            {record && (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge status={record.status_group}>
                    {executionStatusLabel(record, t)}
                  </Badge>
                  <ExecutionKindBadge row={record} />
                  {record.debug && (
                    <Badge status="debug">
                      {t('monitoring.execution.debug')}
                    </Badge>
                  )}
                  {href && (
                    <Button asChild variant="outline" size="sm">
                      <Link to={href}>
                        {t('monitoring.execution.detail.openObject')}
                      </Link>
                    </Button>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">
                  {[
                    record.bot_name,
                    record.platform,
                    record.user_name || record.user_id,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
                <div className="grid grid-cols-3 divide-x rounded-lg border bg-muted/20">
                  <div className="space-y-1 p-3">
                    <p className="text-xs text-muted-foreground">{t('monitoring.execution.detail.duration')}</p>
                    <p className="text-sm font-semibold tabular-nums">{record.duration_ms != null ? formatRunDuration(record.duration_ms) : '—'}</p>
                  </div>
                  <div className="space-y-1 p-3">
                    <p className="text-xs text-muted-foreground">{t('monitoring.llmCalls.totalTokens')}</p>
                    <p className="text-sm font-semibold tabular-nums">{record.usage?.total_tokens?.toLocaleString() ?? '—'}</p>
                  </div>
                  <div className="space-y-1 p-3">
                    <p className="text-xs text-muted-foreground">{t('monitoring.unified.deliveries')}</p>
                    <p className="text-sm font-semibold tabular-nums">{visible?.pages.deliveries?.items.length ?? 0}{visible?.pages.deliveries?.has_more ? '+' : ''}</p>
                  </div>
                </div>
                {record.status_reason && !['stop', 'completed', 'success'].includes(record.status_reason) && (
                  <p className="rounded-md bg-muted p-3 text-sm">
                    {record.status_reason.split('; ').map((reason) =>
                      reason === 'failure_reason_not_recorded'
                        ? t('common.failureReasonNotRecorded') : reason,
                    ).join('; ')}
                  </p>
                )}
                {mainSections.map((section) => renderSection(section, true))}
                {secondarySections.map((section) => renderSection(section))}
                <details className="rounded-lg border p-3">
                  <summary className="cursor-pointer text-sm">
                    {t('monitoring.unified.metadata')}
                  </summary>
                  <dl className="mt-3 space-y-2 text-xs">
                    {[
                      [t('monitoring.execution.detail.executionId'), record.id],
                      [
                        t('monitoring.execution.detail.eventId'),
                        record.event_id,
                      ],
                      [
                        t('monitoring.unified.conversation'),
                        record.conversation_id || record.session_id,
                      ],
                      [
                        t('monitoring.execution.detail.runner'),
                        record.runner_id,
                      ],
                      [
                        t('monitoring.execution.detail.created'),
                        record.created_at_ms
                          ? formatDateTime(new Date(record.created_at_ms))
                          : null,
                      ],
                      [
                        t('monitoring.execution.detail.duration'),
                        record.duration_ms != null
                          ? formatRunDuration(record.duration_ms)
                          : null,
                      ],
                    ]
                      .filter(([, value]) => value)
                      .map(([label, value]) => (
                        <div key={label}>
                          <dt className="text-muted-foreground">{label}</dt>
                          <dd className="break-all">{value}</dd>
                        </div>
                      ))}
                  </dl>
                </details>
              </>
            )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
