import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Fingerprint,
  History,
  Loader2,
  RefreshCw,
  ShieldAlert,
  SlidersHorizontal,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Item, ItemContent, ItemMedia, ItemTitle } from '@/components/ui/item';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type {
  OperationChangeField,
  OperationGovernance,
  OperationIntegrityFilter,
  OperationLevel,
  OperationLogFilters,
  OperationLogPage,
  OperationLogQuery,
  OperationLogRecord,
} from '@/app/infra/entities/operation-log';
import { Download } from 'lucide-react';
import { backendClient, useCurrentWorkspace } from '@/app/infra/http';
import OperationTraceCollectionDialog from './OperationTraceCollectionDialog';
import {
  PanelBody,
  PanelToolbar,
} from '@/app/home/components/settings-dialog/panel-layout';

interface OperationTracePanelProps {
  active: boolean;
}

const ALL_VALUE = '__all__';
const PAGE_SIZE = 20;

/**
 * Machine sentinel the backend stores in place of a masked value. It mirrors
 * ``settings.REDACTED_SENTINEL`` and is the only value the panel translates
 * itself rather than resolving an i18n key from the API.
 */
const REDACTED_SENTINEL = '__redacted__';

/**
 * Longest value a collapsed row shows verbatim. Anything longer is replaced by
 * its size, because a pipeline ``config`` or ``extensions_preferences`` renders
 * as hundreds of characters that wrap onto several lines and read as two
 * near-identical blobs side by side.
 */
const COLLAPSED_VALUE_CHARS = 64;

/** Render a before/after value in full (used when a row is expanded). */
function formatValue(value: unknown, redactedLabel: string): string {
  if (value === null || value === undefined || value === '') return '—';
  // The backend stores a machine sentinel for masked fields; the label is
  // localized here so no interface text ships from the backend.
  if (value === REDACTED_SENTINEL) return redactedLabel;
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

/**
 * Render a before/after value compactly: short values verbatim, long ones as
 * their size. The two sizes almost always differ, so the change stays legible
 * without the full payload competing with the rest of the row.
 */
function summarizeValue(
  value: unknown,
  redactedLabel: string,
  sizeLabel: (count: number) => string,
): string {
  if (value === REDACTED_SENTINEL) return redactedLabel;
  if (value === null || value === undefined || value === '') return '—';
  const text =
    typeof value === 'string' ? value : (JSON.stringify(value) ?? '');
  if (text.length > COLLAPSED_VALUE_CHARS) return sizeLabel(text.length);
  return text;
}

/** Render one before → after pair in a compact, readable row. */
function ChangeRow({
  change,
  redactedLabel,
  sizeLabel,
  collapsed = false,
}: {
  change: OperationChangeField;
  redactedLabel: string;
  sizeLabel: (count: number) => string;
  collapsed?: boolean;
}) {
  const render = (value: unknown): string =>
    collapsed
      ? summarizeValue(value, redactedLabel, sizeLabel)
      : formatValue(value, redactedLabel);
  return (
    <div className="flex flex-wrap items-baseline gap-1.5 font-mono text-xs">
      <span className="text-muted-foreground">{change.field}</span>
      <span className="rounded bg-muted px-1.5 py-0.5 break-all">
        {render(change.before)}
      </span>
      <span aria-hidden="true" className="text-muted-foreground">
        →
      </span>
      <span className="rounded bg-primary/10 px-1.5 py-0.5 break-all">
        {render(change.after)}
      </span>
    </div>
  );
}

function outcomeVariant(
  outcome: OperationLogRecord['outcome'],
): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (outcome === 'error') return 'destructive';
  if (outcome === 'denied') return 'outline';
  return 'secondary';
}

/**
 * How many changes a collapsed row spells out before summarizing the rest.
 * Three covers the common case (a name + a couple of flags) so the vast
 * majority of rows answer "what changed" without a click.
 */
const COLLAPSED_CHANGE_LIMIT = 3;

/**
 * Render a record's before → after diff inline.
 *
 * "What was changed into what" is the reason this log exists, and the diff
 * already arrived with the page, so it is shown on the collapsed row instead
 * of behind a click. Only the fields that differ are listed; the rest fold
 * into a single "+N" note that the expanded row spells out in full.
 */
function ChangeList({
  changes,
  redactedLabel,
  sizeLabel,
  limit,
  moreLabel,
  collapsed = false,
}: {
  changes: OperationChangeField[];
  redactedLabel: string;
  sizeLabel: (count: number) => string;
  limit?: number;
  moreLabel: (hidden: number) => string;
  collapsed?: boolean;
}) {
  const shown = limit === undefined ? changes : changes.slice(0, limit);
  const hidden = changes.length - shown.length;
  return (
    <div className="flex flex-col gap-0.5">
      {shown.map((change, index) => (
        <ChangeRow
          key={`${change.field}-${index}`}
          change={change}
          redactedLabel={redactedLabel}
          sizeLabel={sizeLabel}
          collapsed={collapsed}
        />
      ))}
      {hidden > 0 && (
        <span className="font-mono text-[10px] text-muted-foreground">
          {moreLabel(hidden)}
        </span>
      )}
    </div>
  );
}

/** A record paired with how many times it repeated on the current page. */
interface GroupedRecord {
  key: string;
  record: OperationLogRecord;
  count: number;
}

/**
 * Collapse consecutive identical observations into a single row.
 *
 * An open WebUI or a refresh burst otherwise fills the log with the same
 * "view X" line and buries the operations that actually changed something.
 * The identity includes the summary and the change digest, so two rows are
 * merged only when nothing about them differs; a differing change is kept as
 * its own row.
 */
function groupRecords(records: OperationLogRecord[]): GroupedRecord[] {
  const grouped: GroupedRecord[] = [];
  for (const record of records) {
    const key = [
      record.action,
      record.resource_type,
      record.resource_id,
      record.actor_account_uuid,
      record.outcome,
      record.status_code,
      record.summary ?? '',
      record.changes.map((change) => change.field).join(','),
    ].join('|');
    const last = grouped[grouped.length - 1];
    if (last && last.key === key) {
      last.count += 1;
      continue;
    }
    grouped.push({ key, record, count: 1 });
  }
  return grouped;
}

/**
 * Build a compact page list: the first and last page are always shown, with a
 * one-page window around the current page and gaps collapsed to an ellipsis.
 * ``'…'`` entries are rendered as non-clickable separators.
 */
function pageWindow(
  current: number,
  count: number,
  span = 1,
): (number | '…')[] {
  if (count <= 0) return [];
  const pages = new Set<number>([1, count]);
  for (let page = current - span; page <= current + span; page += 1) {
    if (page >= 1 && page <= count) pages.add(page);
  }
  const sorted = [...pages].sort((a, b) => a - b);
  const result: (number | '…')[] = [];
  let previous = 0;
  for (const page of sorted) {
    if (previous && page - previous > 1) result.push('…');
    result.push(page);
    previous = page;
  }
  return result;
}

/** Compact timestamp: time-only for today, date+time otherwise. */
function formatTimestamp(value: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();
  const time = date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
  return sameDay ? time : `${date.toLocaleDateString()} ${time}`;
}

/**
 * Local calendar day a record belongs to. "today"/"yesterday" are named so the
 * timeline reads relatively at the top and absolutely further back.
 */
function dayKey(value: string | null): string {
  const date = value ? new Date(value) : null;
  if (!date || Number.isNaN(date.getTime())) return 'unknown';
  const iso = (candidate: Date) =>
    `${candidate.getFullYear()}-${candidate.getMonth()}-${candidate.getDate()}`;
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (iso(date) === iso(now)) return 'today';
  if (iso(date) === iso(yesterday)) return 'yesterday';
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate(),
  ).padStart(2, '0')}`;
}

/** A day's worth of records, so a long history reads as a timeline. */
interface DayGroup {
  key: string;
  records: GroupedRecord[];
}

/** Header for a day group; absolute dates pass through unchanged. */
function dayHeading(
  key: string,
  labels: { today: string; yesterday: string; unknown: string },
): string {
  if (key === 'today') return labels.today;
  if (key === 'yesterday') return labels.yesterday;
  if (key === 'unknown') return labels.unknown;
  return key;
}

/**
 * Bucket records by calendar day, preserving the newest-first order.
 *
 * The backend returns a flat stream newest-first; without day headers an
 * operator paging through hundreds of rows cannot tell where "today" ends and
 * "last week" begins, which is the first thing they look for.
 */
function groupByDay(records: GroupedRecord[]): DayGroup[] {
  const groups: DayGroup[] = [];
  for (const record of records) {
    const key = dayKey(record.record.created_at);
    const last = groups[groups.length - 1];
    if (last && last.key === key) {
      last.records.push(record);
      continue;
    }
    groups.push({ key, records: [record] });
  }
  return groups;
}

export default function OperationTracePanel({
  active,
}: OperationTracePanelProps) {
  const { t } = useTranslation();
  const currentWorkspace = useCurrentWorkspace();

  const [governance, setGovernance] = useState<OperationGovernance | null>(
    null,
  );
  const [filters, setFilters] = useState<OperationLogFilters | null>(null);
  const [page, setPage] = useState<OperationLogPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [query, setQuery] = useState<OperationLogQuery>({});
  const [settingsOpen, setSettingsOpen] = useState(false);
  // Only one record shows its full change detail at a time, so the list stays
  // scannable: the payload diff is long and is opt-in per row.
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const role = currentWorkspace?.membership.role ?? null;
  const canConfigure = role === 'owner' || role === 'admin';

  // Fetch only the records page. Paging through the log must not re-request
  // the governance payload and the filter catalogue: those change rarely and
  // the two extra round trips made every page click three times slower.
  const loadPage = useCallback(
    async (nextQuery: OperationLogQuery) => {
      setLoading(true);
      try {
        const pageResponse = await backendClient.getOperationLogs({
          limit: PAGE_SIZE,
          offset: nextQuery.offset ?? 0,
          ...nextQuery,
        });
        setPage(pageResponse);
      } catch {
        toast.error(t('operationTrace.loadFailed'));
      } finally {
        setLoading(false);
      }
    },
    [t],
  );

  const load = useCallback(
    async (nextQuery: OperationLogQuery) => {
      setLoading(true);
      try {
        const [governanceResponse, filtersResponse, pageResponse] =
          await Promise.all([
            backendClient.getOperationGovernance(),
            backendClient.getOperationLogFilters(),
            backendClient.getOperationLogs({
              limit: PAGE_SIZE,
              offset: nextQuery.offset ?? 0,
              ...nextQuery,
            }),
          ]);
        setGovernance(governanceResponse);
        setFilters(filtersResponse);
        setPage(pageResponse);
      } catch {
        toast.error(t('operationTrace.loadFailed'));
      } finally {
        setLoading(false);
      }
    },
    [t],
  );

  // Track visibility so the first render after opening the panel performs the
  // full load, while later query changes (filters, pagination) only refresh
  // the records page.
  const wasActiveRef = useRef(false);

  useEffect(() => {
    if (!active) {
      wasActiveRef.current = false;
      return;
    }
    if (!wasActiveRef.current) {
      wasActiveRef.current = true;
      void load(query);
      return;
    }
    void loadPage(query);
    // Reload the full payload only when the panel becomes visible; filter and
    // pagination changes are handled by the records-only path above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, query]);

  const offset = query.offset ?? 0;
  const total = page?.total ?? 0;
  const canGoBack = offset > 0;
  const canGoForward = offset + PAGE_SIZE < total;
  const pageCount = Math.max(Math.ceil(total / PAGE_SIZE), 1);
  const pageIndex = Math.floor(offset / PAGE_SIZE) + 1;

  // Collapse consecutive identical rows so a refresh burst reads as one line
  // with a count instead of twenty identical entries.
  const groupedRecords = useMemo(
    () => groupRecords(page?.records ?? []),
    [page],
  );

  // A timeline reads top-down: "today", then "yesterday", then dated buckets.
  const dayGroups = useMemo(() => groupByDay(groupedRecords), [groupedRecords]);

  const integrityFilter: OperationIntegrityFilter = query.integrity ?? 'all';
  // "Mutations only" is the default answer to "who changed something"; the
  // level filter already exists, so this is a one-click view rather than new
  // query API surface. Level >= 1 drops the pure "view" observations that
  // otherwise dominate an L2 (read-level) log.
  const mutationsOnly = query.level === 1;

  // Clicking a counter turns it into a drill-down: the panel is the only place
  // the operator can learn *which* records failed verification, so a badge that
  // cannot be acted on would be a dead end.
  function toggleIntegrityFilter(next: OperationIntegrityFilter) {
    setQuery((prev) => ({
      ...prev,
      integrity: prev.integrity === next ? undefined : next,
      offset: 0,
    }));
  }

  async function saveCollectionSettings(settings: {
    level: OperationLevel;
    retentionDays: number;
    maxRows: number;
    dedupeSeconds: number;
  }) {
    if (!canConfigure) return;
    setSaving(true);
    try {
      // One governed write per dialog save: the level and the retention policy
      // are applied together, and the maintenance loop enforces them after.
      const updated = await backendClient.updateOperationGovernance({
        level: settings.level,
        retention_days: settings.retentionDays,
        max_rows: settings.maxRows,
        dedupe_window_seconds: settings.dedupeSeconds,
      });
      setGovernance(updated);
      toast.success(t('operationTrace.settingsUpdated'));
      await load({ ...query, offset: 0 });
    } catch {
      toast.error(t('operationTrace.settingsUpdateFailed'));
    } finally {
      setSaving(false);
    }
  }

  async function downloadLogs() {
    if (exporting) return;
    setExporting(true);
    try {
      // Fetch through the HTTP client so the session token and the active
      // Workspace header are applied. A bare ``window.open`` navigation would
      // drop both and the audit endpoint would reject the request.
      const url = backendClient.buildOperationLogExportURL({
        action: query.action,
        resource_type: query.resource_type,
        actor: query.actor,
        level: query.level,
        since: query.since,
        until: query.until,
        integrity: query.integrity,
      });
      const response = await backendClient.downloadFile(url);
      const disposition = response.headers['content-disposition'] as
        string | undefined;
      const match = disposition?.match(/filename="?([^";\n]+)"?/);
      const filename = match?.[1] ?? `operation-logs-${Date.now()}.csv`;
      const blob = new Blob([response.data], {
        type: 'text/csv;charset=utf-8;',
      });
      const objectUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(objectUrl);
    } catch {
      toast.error(t('operationTrace.exportFailed'));
    } finally {
      setExporting(false);
    }
  }

  if (loading && !governance) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="size-6 animate-spin" />
      </div>
    );
  }

  return (
    <>
      <PanelToolbar>
        <div className="flex min-w-0 items-center gap-2">
          <p className="truncate text-sm font-medium">
            {t('operationTrace.title')}
          </p>
          {governance && (
            <Badge
              variant={governance.configured_level > 0 ? 'default' : 'outline'}
            >
              {t('operationTrace.levelBadge', {
                level: t(
                  `operationTrace.levelNames.${governance.configured_level_name}`,
                ),
              })}
            </Badge>
          )}
        </div>
        {/* Keep the actions in one right-aligned cluster: the panel toolbar
            spreads direct children apart, so they are grouped instead. */}
        <div className="ml-auto flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setSettingsOpen(true)}
          >
            <SlidersHorizontal className="size-3.5" />
            {t('operationTrace.collectionSettings')}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void downloadLogs()}
            disabled={exporting}
          >
            {exporting ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Download className="size-3.5" />
            )}
            {t('operationTrace.export')}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void load(query)}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <RefreshCw className="size-3.5" />
            )}
            {t('operationTrace.refresh')}
          </Button>
        </div>
      </PanelToolbar>

      <PanelBody className="space-y-6">
        <OperationTraceCollectionDialog
          open={settingsOpen}
          onOpenChange={setSettingsOpen}
          governance={governance}
          canConfigure={canConfigure}
          saving={saving}
          onSave={(settings) => void saveCollectionSettings(settings)}
        />

        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <History className="size-4" />
              <h3 className="text-sm font-semibold">
                {t('operationTrace.records')}
              </h3>
              <Badge variant="secondary">{total}</Badge>
              {/* The two failure modes are rendered independently: a record can
                  drop its chain link without corrupting its own hash, so gating
                  one badge on the other counter would hide a real mismatch.
                  The counters cover the whole filtered history, so they stay
                  stable while the operator pages through the records. */}
              {(page?.integrity_failed_count ?? 0) > 0 && (
                <button
                  type="button"
                  onClick={() => toggleIntegrityFilter('hash_mismatch')}
                  className="cursor-pointer"
                >
                  <Badge variant="destructive">
                    {t('operationTrace.integrityFailedCount', {
                      count: page?.integrity_failed_count ?? 0,
                    })}
                  </Badge>
                </button>
              )}
              {(page?.chain_failed_count ?? 0) > 0 && (
                <button
                  type="button"
                  onClick={() => toggleIntegrityFilter('chain_broken')}
                  className="cursor-pointer"
                >
                  <Badge variant="destructive">
                    {t('operationTrace.chainFailedCount', {
                      count: page?.chain_failed_count ?? 0,
                    })}
                  </Badge>
                </button>
              )}
              {page?.scan_truncated && (
                <Badge variant="outline">
                  {t('operationTrace.scanTruncated', {
                    count: page?.scanned_count ?? 0,
                  })}
                </Badge>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Select
                value={query.action ?? ALL_VALUE}
                onValueChange={(value) =>
                  setQuery((prev) => ({
                    ...prev,
                    action: value === ALL_VALUE ? undefined : value,
                    offset: 0,
                  }))
                }
              >
                <SelectTrigger size="sm" className="w-40">
                  <SelectValue placeholder={t('operationTrace.filterAction')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL_VALUE}>
                    {t('operationTrace.filterAllActions')}
                  </SelectItem>
                  {(filters?.actions ?? []).map((action) => (
                    <SelectItem key={action} value={action}>
                      {t(`operationTrace.actions.${action}`, {
                        defaultValue: action,
                      })}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={query.resource_type ?? ALL_VALUE}
                onValueChange={(value) =>
                  setQuery((prev) => ({
                    ...prev,
                    resource_type: value === ALL_VALUE ? undefined : value,
                    offset: 0,
                  }))
                }
              >
                <SelectTrigger size="sm" className="w-40">
                  <SelectValue
                    placeholder={t('operationTrace.filterResource')}
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL_VALUE}>
                    {t('operationTrace.filterAllResources')}
                  </SelectItem>
                  {(filters?.resource_types ?? []).map((resource) => (
                    <SelectItem key={resource} value={resource}>
                      {/* The API ships the raw resource family (``resource``,
                          ``member``...); the label is resolved here so no
                          interface text leaks from the backend. */}
                      {t(`operationTrace.resourceTypes.${resource}`, {
                        defaultValue: resource,
                      })}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={query.actor ?? ALL_VALUE}
                onValueChange={(value) =>
                  setQuery((prev) => ({
                    ...prev,
                    actor: value === ALL_VALUE ? undefined : value,
                    offset: 0,
                  }))
                }
              >
                <SelectTrigger size="sm" className="w-44">
                  <SelectValue placeholder={t('operationTrace.filterActor')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL_VALUE}>
                    {t('operationTrace.filterAllActors')}
                  </SelectItem>
                  {(filters?.actors ?? []).map((actor) => (
                    <SelectItem
                      key={actor.account_uuid}
                      value={actor.account_uuid}
                    >
                      {actor.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {/* The log is an answer to "who changed something", so the pure
                  "view" observations can be hidden in one click. It reuses the
                  level filter (mutations are level >= 1) rather than adding new
                  query API. */}
              <Button
                size="sm"
                variant={mutationsOnly ? 'default' : 'outline'}
                className="h-8"
                onClick={() =>
                  setQuery((prev) => ({
                    ...prev,
                    level: prev.level === 1 ? undefined : 1,
                    offset: 0,
                  }))
                }
              >
                {t('operationTrace.mutationsOnly')}
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            {groupedRecords.length === 0 && (
              <p className="rounded-lg border border-dashed p-6 text-center text-xs text-muted-foreground">
                {integrityFilter === 'all'
                  ? t('operationTrace.empty')
                  : t('operationTrace.emptyFiltered')}
              </p>
            )}
            {dayGroups.map((group) => (
              <div key={group.key} className="space-y-2">
                <div className="flex items-center gap-2 pt-1">
                  <span className="text-[11px] font-medium text-muted-foreground">
                    {dayHeading(group.key, {
                      today: t('operationTrace.today'),
                      yesterday: t('operationTrace.yesterday'),
                      unknown: t('operationTrace.unknownDay'),
                    })}
                  </span>
                  <span className="h-px flex-1 bg-border" />
                </div>
                {group.records.map(({ key, record, count }) => {
                  const expanded = expandedId === record.id;
                  const actor =
                    record.actor_name ??
                    record.actor_account_uuid ??
                    t('operationTrace.systemActor');
                  const role = record.actor_role
                    ? t(`workspace.roles.${record.actor_role}`)
                    : t('operationTrace.systemActor');
                  return (
                    <Item
                      key={key}
                      size="sm"
                      variant="muted"
                      role="button"
                      tabIndex={0}
                      aria-expanded={expanded}
                      onClick={() => setExpandedId(expanded ? null : record.id)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          setExpandedId(expanded ? null : record.id);
                        }
                      }}
                      className={`items-start rounded-lg ${
                        record.tampered
                          ? 'border-destructive/60 bg-destructive/5'
                          : ''
                      } ${expanded ? 'ring-1 ring-border' : ''}`}
                    >
                      <ItemMedia variant="icon">
                        {record.tampered ? (
                          <ShieldAlert className="size-4 text-destructive" />
                        ) : (
                          <History className="size-4" />
                        )}
                      </ItemMedia>
                      <ItemContent className="min-w-0 gap-1.5">
                        {/* Identity first: who did it and when. That is the
                            question the log is opened to answer, so it leads
                            instead of hiding in a muted description line. */}
                        <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs">
                          <span className="font-medium text-foreground">
                            {actor}
                          </span>
                          <span className="text-muted-foreground">·</span>
                          <span className="text-muted-foreground">{role}</span>
                          <span className="text-muted-foreground">·</span>
                          <span className="text-muted-foreground">
                            {formatTimestamp(record.created_at)}
                          </span>
                        </div>
                        {/* What happened, to which resource — always present,
                            followed on the next line by the concrete diff. */}
                        <ItemTitle className="flex flex-wrap items-center gap-1.5">
                          <span className="font-medium">
                            {t(record.action_i18n_key, {
                              defaultValue: record.action ?? '',
                            })}
                          </span>
                          {record.resource_type && (
                            <span className="text-xs text-muted-foreground">
                              {t(
                                `operationTrace.resourceTypes.${record.resource_type}`,
                                { defaultValue: record.resource_type },
                              )}
                            </span>
                          )}
                          {record.resource_id && (
                            <span
                              className="max-w-[18rem] truncate font-mono text-xs text-muted-foreground"
                              title={record.resource_id}
                            >
                              {record.resource_id}
                            </span>
                          )}
                          {record.outcome !== 'ok' && (
                            <Badge variant={outcomeVariant(record.outcome)}>
                              {t(`operationTrace.outcomes.${record.outcome}`)}
                            </Badge>
                          )}
                          {record.tampered && (
                            <Badge variant="destructive">
                              <ShieldAlert className="size-3" />
                              {t('operationTrace.tamperedBadge')}
                            </Badge>
                          )}
                          {count > 1 && (
                            <Badge variant="outline" className="shrink-0">
                              ×{count}
                            </Badge>
                          )}
                        </ItemTitle>
                        {/* "What was changed into what" is the whole point of
                            the log and the data already arrived with the page,
                            so the diff is spelled out on the collapsed row. */}
                        {record.changes.length > 0 && (
                          <div className="rounded-md bg-background/60 p-2">
                            <ChangeList
                              changes={record.changes}
                              redactedLabel={t('operationTrace.redacted')}
                              sizeLabel={(size) =>
                                t('operationTrace.elidedValue', { count: size })
                              }
                              limit={
                                expanded ? undefined : COLLAPSED_CHANGE_LIMIT
                              }
                              moreLabel={(hidden) =>
                                t('operationTrace.moreChanges', {
                                  count: hidden,
                                })
                              }
                              collapsed={!expanded}
                            />
                          </div>
                        )}
                        {/* The whole card is the toggle, so the chevron is the
                            only affordance needed; clicking anywhere expands
                            it. That removes the ambiguity of a small text link
                            whose expanded state looked almost identical. */}
                        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                          <ChevronDown
                            className={`size-3 transition-transform ${
                              expanded ? 'rotate-180' : ''
                            }`}
                            aria-hidden="true"
                          />
                          {expanded
                            ? t('operationTrace.hideDetails')
                            : t('operationTrace.showDetails')}
                        </span>
                        {/* Diagnostics are opt-in: route, method, status,
                            duration and the evidence hash matter when an
                            operator investigates one entry, not while scanning
                            the timeline. */}
                        {expanded && (
                          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 border-t border-border/60 pt-1.5 font-mono text-[10px] text-muted-foreground">
                            {record.route && (
                              <span className="truncate" title={record.route}>
                                {record.route}
                              </span>
                            )}
                            {record.http_method && (
                              <span>
                                {record.http_method}
                                {record.status_code !== null
                                  ? ` ${record.status_code}`
                                  : ''}
                              </span>
                            )}
                            <span>{record.duration_ms}ms</span>
                            {record.record_hash && (
                              <span
                                className="flex items-center gap-1"
                                title={record.record_hash}
                              >
                                <Fingerprint className="size-3" />
                                {record.record_hash.slice(0, 16)}
                              </span>
                            )}
                          </div>
                        )}
                      </ItemContent>
                    </Item>
                  );
                })}
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {t('operationTrace.pageInfo', {
                from: total === 0 ? 0 : offset + 1,
                to: Math.min(offset + PAGE_SIZE, total),
                total,
              })}
            </span>
            <div className="flex items-center gap-1">
              <Button
                size="icon"
                variant="outline"
                disabled={!canGoBack || loading}
                onClick={() =>
                  setQuery((prev) => ({
                    ...prev,
                    offset: Math.max(offset - PAGE_SIZE, 0),
                  }))
                }
                aria-label={t('operationTrace.previousPage')}
              >
                <ChevronLeft className="size-4" />
              </Button>
              {/* Numbered pager: the first and last page stay visible with an
                  ellipsis between, so any page is one click away without the
                  arrows filling the bar with "Page x / y" rows. */}
              {pageWindow(pageIndex, pageCount).map((item, index) =>
                item === '…' ? (
                  <span
                    key={`gap-${index}`}
                    className="px-1 text-xs text-muted-foreground"
                  >
                    …
                  </span>
                ) : (
                  <Button
                    key={item}
                    size="sm"
                    variant={item === pageIndex ? 'default' : 'outline'}
                    className="h-8 min-w-8 px-2 font-mono text-xs"
                    disabled={loading}
                    onClick={() =>
                      setQuery((prev) => ({
                        ...prev,
                        offset: (item - 1) * PAGE_SIZE,
                      }))
                    }
                  >
                    {item}
                  </Button>
                ),
              )}
              <Button
                size="icon"
                variant="outline"
                disabled={!canGoForward || loading}
                onClick={() =>
                  setQuery((prev) => ({ ...prev, offset: offset + PAGE_SIZE }))
                }
                aria-label={t('operationTrace.nextPage')}
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        </section>
      </PanelBody>
    </>
  );
}
