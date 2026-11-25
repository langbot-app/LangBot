import LoadErrorState from '@/components/LoadErrorState';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import {
  ArrowUpRight,
  ChevronRight,
  Copy,
  MessageSquare,
  RefreshCw,
  User,
  Users,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import CopyableId from '@/components/CopyableId';
import { copyToClipboard } from '@/app/utils/clipboard';
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
  PluginHandledBadge,
} from './ExecutionTable';

export type ExecutionSelection = Pick<ExecutionRow, 'id'> & {
  source: ExecutionRow['source'] | 'auto';
};

// Keep transport metadata in the payload disclosure, not in the message body.
function messageBody(value: unknown): unknown {
  if (typeof value === 'string') {
    if (/^\s*[\[{]/.test(value)) {
      try {
        return messageBody(JSON.parse(value));
      } catch {
        /* Plain text. */
      }
    }
    return value;
  }
  if (Array.isArray(value))
    return value.map(messageBody).filter((item) => item != null && item !== '');
  if (!value || typeof value !== 'object') return null;
  const data = value as Record<string, unknown>;
  if (
    ['Image', 'File', 'Voice', 'At', 'AtAll', 'Quote'].includes(
      String(data.type),
    )
  )
    return value;
  for (const key of ['text', 'content', 'message_chain', 'message', 'root']) {
    if (data[key] != null) return messageBody(data[key]);
  }
  return null;
}
// Diagnostics share one tab strip. A tab never disappears when it is empty:
// it says so, instead of collapsing under the pointer.
const diagnosticSections: ExecutionSection[] = [
  'llm_calls',
  'tool_calls',
  'events',
  'related',
  'conversation',
];

function RawData({
  value,
  defaultOpen = false,
}: {
  value: unknown;
  defaultOpen?: boolean;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(defaultOpen);
  const text = useMemo(() => {
    if (!open) return '';
    try {
      return JSON.stringify(value, null, 2) ?? '';
    } catch {
      return String(value);
    }
  }, [open, value]);
  if (value == null) return null;
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="flex items-center gap-2">
        <CollapsibleTrigger className="group flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
          <ChevronRight className="size-3.5 transition-transform group-data-[state=open]:rotate-90" />
          {t('monitoring.unified.payload')}
        </CollapsibleTrigger>
        {open && (
          <button
            type="button"
            className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            onClick={() =>
              copyToClipboard(text)
                .then(() => toast.success(t('common.copySuccess')))
                .catch(() => toast.error(t('common.copyFailed')))
            }
          >
            <Copy className="size-3" />
            {t('monitoring.unified.copyJson')}
          </button>
        )}
      </div>
      <CollapsibleContent>
        <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-all rounded-md bg-muted/50 p-2 font-mono text-[11px] leading-4">
          {text}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  );
}

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
  const [sectionError, setSectionError] = useState<
    Partial<Record<ExecutionSection, boolean>>
  >({});
  const [busy, setBusy] = useState<Partial<Record<ExecutionSection, boolean>>>(
    {},
  );
  const pendingSections = useRef(new Set<ExecutionSection>());
  const expandedSections = useRef(new Set<ExecutionSection>());
  const [refresh, setRefresh] = useState(0);
  const [diagnostic, setDiagnostic] = useState<ExecutionSection | null>(null);
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
      expandedSections.current.clear();
      setDiagnostic(null);
    }
    setError(false);
    setSectionError({});
    setBusy({});
    pendingSections.current.clear();
    if (!id || !source) {
      setLoading(false);
      return;
    }
    setLoading(true);
    const expanded = [...expandedSections.current].filter(
      (section) => section !== 'errors',
    );
    Promise.all([
      backendClient.getExecutionDetail(source, id, { section: 'overview' }),
      ...expanded.map((section) =>
        backendClient
          .getExecutionDetail(source, id, { section })
          .catch(() => null),
      ),
    ])
      .then(([result, ...sections]) => {
        if (version !== request.current) return;
        if (!result) return;
        const pages = { ...result.pages };
        const failures: Partial<Record<ExecutionSection, boolean>> = {};
        sections.forEach((loaded, index) => {
          const section = expanded[index];
          if (loaded) Object.assign(pages, loaded.pages);
          else failures[section] = true;
        });
        setDetail((previous) => ({
          ...result,
          pages: { ...previous?.pages, ...pages },
        }));
        setSectionError((previous) => ({ ...previous, ...failures }));
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
    if (!visible || !row || pendingSections.current.has(section)) return;
    const version = request.current;
    pendingSections.current.add(section);
    setBusy((previous) => ({ ...previous, [section]: true }));
    setSectionError((previous) => ({ ...previous, [section]: false }));
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
      if (version === request.current)
        setSectionError((previous) => ({ ...previous, [section]: true }));
    } finally {
      if (version === request.current) {
        pendingSections.current.delete(section);
        setBusy((previous) => ({ ...previous, [section]: false }));
      }
    }
  };
  const itemTime = (item: ExecutionDetailItem) =>
    item.timestamp_ms
      ? formatDateTime(new Date(item.timestamp_ms))
      : typeof item.timestamp === 'string'
        ? item.timestamp
        : '';
  const itemStatus = (item: ExecutionDetailItem) =>
    item.status ? (
      <Badge status={item.status}>
        {t(
          `monitoring.execution.status.${['success', 'delivered'].includes(item.status) ? 'completed' : item.status}`,
          { defaultValue: item.status },
        )}
      </Badge>
    ) : null;
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
          item.role &&
            t(`monitoring.unified.roles.${item.role}`, {
              defaultValue: item.role,
            }),
          item.event_type,
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
      <div className="min-w-0 space-y-2 rounded-lg border bg-background p-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="min-w-0 flex-1 break-all font-medium text-foreground/80">
            {title}
          </span>
          {itemStatus(item)}
          <PluginHandledBadge
            handledBy={
              typeof item.handled_by === 'string' ? item.handled_by : null
            }
          />
          <span className="tabular-nums">{itemTime(item)}</span>
        </div>
        {content ? (
          <>
            <div className="text-sm leading-6">
              {hasExecutionValue(body) ? (
                <Value value={body} />
              ) : (
                <p className="text-muted-foreground">
                  {t('monitoring.unified.noRecords')}
                </p>
              )}
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
          </>
        )}
        <RawData value={section === 'events' ? item.data : item} />
      </div>
    );
  };
  const pageTitle = (section: ExecutionSection) => {
    const page = visible?.pages[section];
    const count = page
      ? `${page.items.length}${page.has_more ? '+' : ''}`
      : visible?.counts?.[section] != null
        ? String(visible.counts[section])
        : null;
    return { label: t(`monitoring.unified.${section}`), count };
  };
  const renderList = (section: ExecutionSection) => {
    const page = visible?.pages[section];
    return (
      <div className="space-y-2">
        {section === 'conversation' && (
          <p className="text-xs text-muted-foreground">
            {t('monitoring.unified.contextHint')}
          </p>
        )}
        {!page && !sectionError[section] && (
          <Skeleton className="h-16 w-full" />
        )}
        {page?.items.length === 0 && (
          <p className="rounded-lg border border-dashed px-3 py-4 text-center text-sm text-muted-foreground">
            {t('monitoring.unified.noRecords')}
          </p>
        )}
        {page?.items.map((item, i) => (
          <div key={`${item.id}-${i}`}>{renderItem(section, item)}</div>
        ))}
        {sectionError[section] && (
          <LoadErrorState
            compact
            title={t('monitoring.execution.detail.loadError')}
            onRetry={() => loadMore(section)}
          />
        )}
        {page?.has_more && (
          <Button
            variant="outline"
            size="sm"
            disabled={!!busy[section]}
            onClick={() => loadMore(section)}
          >
            {t('monitoring.unified.loadMore')}
          </Button>
        )}
      </div>
    );
  };
  const sectionHeading = (section: ExecutionSection, index: number) => {
    const { label, count } = pageTitle(section);
    return (
      <h3 className="flex items-center gap-2 text-sm font-semibold">
        <span className="flex size-5 items-center justify-center rounded-full bg-muted text-[11px] text-muted-foreground">
          {index}
        </span>
        {label}
        {count != null && (
          <span className="font-normal text-muted-foreground tabular-nums">
            {count}
          </span>
        )}
      </h3>
    );
  };
  // One inbound event is usually journaled several times (platform ingress,
  // pipeline query, legacy summary). Show the richest copy as the trigger and
  // keep every raw record one click away instead of repeating the message.
  const renderTrigger = () => {
    const page = visible?.pages.inputs;
    if (!page) return null;
    const items = page.items;
    const primary =
      items.find(
        (item) =>
          item.role === 'user' && hasExecutionValue(messageBody(item.content)),
      ) ??
      items.find((item) => hasExecutionValue(messageBody(item.content))) ??
      items[0];
    const body = primary ? messageBody(primary.content) : null;
    const chat = visible?.chat;
    const sender =
      primary?.actor_name ||
      chat?.sender_name ||
      primary?.actor_id ||
      chat?.sender_id;
    return (
      <section className="space-y-2">
        {sectionHeading('inputs', 1)}
        {!primary ? (
          <p className="rounded-lg border border-dashed px-3 py-4 text-center text-sm text-muted-foreground">
            {t('monitoring.unified.noRecords')}
          </p>
        ) : (
          <div className="min-w-0 space-y-2 rounded-lg border bg-background p-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="min-w-0 flex-1 break-all font-medium text-foreground/80">
                {sender || t('monitoring.unified.roles.user')}
              </span>
              {itemStatus(primary)}
              <span className="tabular-nums">{itemTime(primary)}</span>
            </div>
            <div className="text-sm leading-6">
              {hasExecutionValue(body) ? (
                <Value value={body} />
              ) : (
                <p className="text-muted-foreground">
                  {t('monitoring.unified.noRecords')}
                </p>
              )}
            </div>
            <Value value={primary.attachments} />
          </div>
        )}
        {items.length > 0 && (
          <Collapsible>
            <CollapsibleTrigger className="group flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
              <ChevronRight className="size-3.5 transition-transform group-data-[state=open]:rotate-90" />
              {t('monitoring.unified.rawEvents', {
                count: items.length,
                more: page.has_more ? '+' : '',
              })}
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-2 space-y-2">
              {items.map((item, i) => (
                <div
                  key={`${item.id}-${i}`}
                  className="space-y-1 rounded-md border bg-muted/20 p-2"
                >
                  <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                    <span className="font-medium text-foreground/80">
                      {item.event_type ||
                        t(`monitoring.unified.roles.${item.role ?? 'user'}`, {
                          defaultValue: item.role,
                        })}
                    </span>
                    {item.actor_id && (
                      <span className="break-all">{item.actor_id}</span>
                    )}
                    <span className="ml-auto tabular-nums">
                      {itemTime(item)}
                    </span>
                  </div>
                  <RawData value={item} />
                </div>
              ))}
              {page.has_more && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!!busy.inputs}
                  onClick={() => loadMore('inputs')}
                >
                  {t('monitoring.unified.loadMore')}
                </Button>
              )}
            </CollapsibleContent>
          </Collapsible>
        )}
      </section>
    );
  };
  const selectDiagnostic = (section: ExecutionSection) => {
    setDiagnostic(section);
    // Polling re-reads only the open diagnostic, never every visited one.
    expandedSections.current.clear();
    expandedSections.current.add(section);
    if (!visible?.pages[section]) void loadMore(section);
  };
  const activeDiagnostic =
    diagnostic ??
    diagnosticSections.find(
      (section) => (visible?.counts?.[section] ?? 0) > 0,
    ) ??
    null;
  useEffect(() => {
    // Auto-open the first non-empty diagnostic once its count is known.
    if (diagnostic || !activeDiagnostic || !visible) return;
    if (!visible.pages[activeDiagnostic]) selectDiagnostic(activeDiagnostic);
    else setDiagnostic(activeDiagnostic);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeDiagnostic, diagnostic, visible]);
  const record = visible?.row;
  const href = record?.target_id
    ? record.target_kind === 'pipeline'
      ? `/home/pipelines?id=${encodeURIComponent(record.target_id)}`
      : ['agent', 'event_processor', 'processor'].includes(record.target_kind)
        ? `/home/agents?id=${encodeURIComponent(record.target_id)}`
        : null
    : null;
  // Where the event came from: bot, chat (with the exact ID routing rules
  // match) and sender. Group chats lead with the group, not the sender.
  const renderChat = () => {
    if (!record) return null;
    const chat = visible?.chat;
    const isGroup = chat?.type === 'group';
    const senderName = chat?.sender_name || record.user_name;
    const senderId = chat?.sender_id || record.user_id;
    const routeTarget =
      record.pipeline_id ||
      (['pipeline', 'agent'].includes(record.target_kind)
        ? record.target_id
        : null);
    const routeHref =
      chat?.id && chat.type && record.bot_id
        ? `/home/bots?id=${encodeURIComponent(record.bot_id)}&tab=config&routeChat=${encodeURIComponent(`${chat.type}:${chat.id}`)}${routeTarget ? `&routeTarget=${encodeURIComponent(routeTarget)}` : ''}`
        : null;
    const rows: [string, React.ReactNode][] = [];
    if (record.bot_name || record.platform)
      rows.push([
        t('monitoring.unified.chat.bot'),
        <span className="break-all">
          {[record.bot_name, record.platform].filter(Boolean).join(' · ')}
        </span>,
      ]);
    if (chat?.id)
      rows.push([
        isGroup
          ? t('monitoring.unified.chat.groupId')
          : t('monitoring.unified.chat.privateChat'),
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          {isGroup && chat.name && (
            <span className="font-medium">{chat.name}</span>
          )}
          <CopyableId
            value={chat.id}
            label={t('monitoring.unified.chat.groupId')}
          />
          {routeHref && (
            <Link
              to={routeHref}
              onClick={onClose}
              className="inline-flex items-center gap-0.5 text-xs text-primary hover:underline"
            >
              {isGroup
                ? t('monitoring.unified.chat.routeGroup')
                : t('monitoring.unified.chat.routePerson')}
              <ArrowUpRight className="size-3" />
            </Link>
          )}
        </div>,
      ]);
    if (senderName || senderId)
      rows.push([
        t('monitoring.unified.chat.sender'),
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          {senderName && <span>{senderName}</span>}
          {senderId && senderId !== senderName && (
            <CopyableId
              value={senderId}
              label={t('monitoring.unified.chat.sender')}
            />
          )}
        </div>,
      ]);
    if (rows.length === 0) return null;
    const Icon = isGroup
      ? Users
      : chat?.type === 'person'
        ? User
        : MessageSquare;
    return (
      <div className="rounded-lg border">
        <div className="flex items-center gap-2 border-b bg-muted/30 px-3 py-2 text-xs font-medium">
          <Icon className="size-3.5 text-muted-foreground" />
          {isGroup
            ? t('monitoring.unified.chat.groupChat')
            : chat?.type === 'person'
              ? t('monitoring.unified.chat.privateChat')
              : t('monitoring.unified.chat.source')}
        </div>
        <dl className="grid grid-cols-[max-content_1fr] items-start gap-x-4 gap-y-2 px-3 py-2.5 text-sm">
          {rows.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="pt-0.5 text-xs text-muted-foreground">{label}</dt>
              <dd className="min-w-0">{value}</dd>
            </div>
          ))}
        </dl>
      </div>
    );
  };
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
                title={
                  error
                    ? t('monitoring.execution.detail.loadError')
                    : t('monitoring.refreshData')
                }
                onClick={() => setRefresh((value) => value + 1)}
              >
                <RefreshCw
                  className={`h-4 w-4 ${loading ? 'animate-spin' : ''} ${error ? 'text-destructive' : ''}`}
                />
              </Button>
            </div>
            {loading && !visible && <Skeleton className="h-36 w-full" />}
            {error && !visible && (
              <LoadErrorState
                title={t('monitoring.execution.detail.loadError')}
                onRetry={() => setRefresh((value) => value + 1)}
              />
            )}
            {record && (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge status={record.status_group}>
                    {executionStatusLabel(record, t)}
                  </Badge>
                  <ExecutionKindBadge row={record} />
                  <PluginHandledBadge handledBy={record.handled_by} />
                  {record.debug && (
                    <Badge status="debug">
                      {t('monitoring.execution.debug')}
                    </Badge>
                  )}
                  {href && (
                    <Button
                      asChild
                      variant="outline"
                      size="sm"
                      className="ml-auto h-7"
                    >
                      <Link to={href} onClick={onClose}>
                        {t('monitoring.execution.detail.openObject')}
                        <ArrowUpRight className="size-3.5" />
                      </Link>
                    </Button>
                  )}
                </div>
                {renderChat()}
                <div className="grid grid-cols-3 divide-x rounded-lg border bg-muted/20">
                  {[
                    [
                      t('monitoring.execution.detail.duration'),
                      record.duration_ms != null
                        ? formatRunDuration(record.duration_ms)
                        : '—',
                    ],
                    [
                      t('monitoring.llmCalls.totalTokens'),
                      record.usage?.total_tokens?.toLocaleString() ?? '—',
                    ],
                    [
                      t('monitoring.unified.deliveries'),
                      `${visible?.pages.deliveries?.items.length ?? 0}${visible?.pages.deliveries?.has_more ? '+' : ''}`,
                    ],
                  ].map(([label, value]) => (
                    <div key={label} className="space-y-0.5 px-3 py-2">
                      <p className="text-[11px] text-muted-foreground">
                        {label}
                      </p>
                      <p className="text-sm font-semibold tabular-nums">
                        {value}
                      </p>
                    </div>
                  ))}
                </div>
                {record.status_reason &&
                  !['stop', 'completed', 'success'].includes(
                    record.status_reason,
                  ) && (
                    <p className="rounded-md bg-muted p-3 text-sm">
                      {record.status_reason
                        .split('; ')
                        .map((reason) =>
                          reason === 'failure_reason_not_recorded'
                            ? t('common.failureReasonNotRecorded')
                            : reason,
                        )
                        .join('; ')}
                    </p>
                  )}
                {(visible?.pages.errors?.items.length ?? 0) > 0 && (
                  <section className="space-y-2 rounded-lg border border-red-500/25 bg-red-500/5 p-3">
                    <h3 className="text-sm font-semibold text-destructive">
                      {t('monitoring.unified.errors')}{' '}
                      <span className="font-normal tabular-nums">
                        {pageTitle('errors').count}
                      </span>
                    </h3>
                    {renderList('errors')}
                  </section>
                )}
                {renderTrigger()}
                {visible?.pages.outputs && (
                  <section className="space-y-2">
                    {sectionHeading('outputs', 2)}
                    {renderList('outputs')}
                  </section>
                )}
                {visible?.pages.deliveries && (
                  <section className="space-y-2">
                    {sectionHeading('deliveries', 3)}
                    {renderList('deliveries')}
                  </section>
                )}
                <section className="space-y-3 border-t pt-4">
                  <h3 className="text-sm font-semibold">
                    {t('monitoring.unified.diagnostics')}
                  </h3>
                  <div
                    role="tablist"
                    className="flex flex-wrap gap-1.5"
                    aria-label={t('monitoring.unified.diagnostics')}
                  >
                    {diagnosticSections.map((section) => {
                      const { label, count } = pageTitle(section);
                      const selected = activeDiagnostic === section;
                      return (
                        <button
                          key={section}
                          type="button"
                          role="tab"
                          aria-selected={selected}
                          onClick={() => selectDiagnostic(section)}
                          className={`inline-flex h-7 items-center gap-1.5 rounded-full border px-3 text-xs transition-colors ${
                            selected
                              ? 'border-primary bg-primary text-primary-foreground'
                              : count === '0'
                                ? 'text-muted-foreground/70 hover:bg-accent'
                                : 'hover:bg-accent'
                          }`}
                        >
                          {label}
                          {count != null && (
                            <span
                              className={`tabular-nums ${selected ? 'opacity-80' : 'text-muted-foreground'}`}
                            >
                              {count}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                  {activeDiagnostic ? (
                    <div role="tabpanel">{renderList(activeDiagnostic)}</div>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      {t('monitoring.unified.diagnosticsHint')}
                    </p>
                  )}
                </section>
                <Collapsible className="rounded-lg border px-3 py-2">
                  <CollapsibleTrigger className="group flex w-full items-center gap-1 text-sm">
                    <ChevronRight className="size-4 transition-transform group-data-[state=open]:rotate-90" />
                    {t('monitoring.unified.metadata')}
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <dl className="mt-3 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-xs">
                      {[
                        [
                          t('monitoring.execution.detail.executionId'),
                          record.id,
                        ],
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
                      ]
                        .filter(([, value]) => value)
                        .map(([label, value]) => (
                          <div key={label} className="contents">
                            <dt className="pt-0.5 text-muted-foreground">
                              {label}
                            </dt>
                            <dd className="min-w-0">
                              <CopyableId value={String(value)} />
                            </dd>
                          </div>
                        ))}
                    </dl>
                  </CollapsibleContent>
                </Collapsible>
              </>
            )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
