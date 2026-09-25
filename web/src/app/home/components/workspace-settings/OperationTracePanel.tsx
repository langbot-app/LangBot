import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Fingerprint,
  History,
  Loader2,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemMedia,
  ItemTitle,
} from '@/components/ui/item';
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

/** Render one before → after pair in a compact, readable row. */
function ChangeRow({
  change,
  redactedLabel,
}: {
  change: OperationChangeField;
  redactedLabel: string;
}) {
  const format = (value: unknown): string => {
    if (value === null || value === undefined || value === '') return '—';
    // The backend stores a machine sentinel for masked fields; the label is
    // localized here so no interface text ships from the backend.
    if (value === REDACTED_SENTINEL) return redactedLabel;
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  };
  return (
    <div className="flex flex-wrap items-baseline gap-1.5 font-mono text-xs">
      <span className="text-muted-foreground">{change.field}</span>
      <span className="rounded bg-muted px-1.5 py-0.5 break-all">
        {format(change.before)}
      </span>
      <span aria-hidden="true" className="text-muted-foreground">
        →
      </span>
      <span className="rounded bg-primary/10 px-1.5 py-0.5 break-all">
        {format(change.after)}
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
  const [retentionDays, setRetentionDays] = useState<number>(30);
  const [maxRows, setMaxRows] = useState<number>(20000);
  const [dedupeSeconds, setDedupeSeconds] = useState<number>(60);

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
        setRetentionDays(governanceResponse.retention_days);
        setMaxRows(governanceResponse.max_rows);
        setDedupeSeconds(governanceResponse.dedupe_window_seconds);
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

  // Render the server page as-is. Record ids are unique and stable, the
  // backend already collapses repeated observations at write time, and a
  // client-side dedupe would hide legitimately distinct rows (making the
  // total badge disagree with the list) whenever a page is re-fetched.
  const visibleRecords = page?.records ?? [];

  const integrityFilter: OperationIntegrityFilter = query.integrity ?? 'all';

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

  async function changeLevel(level: OperationLevel) {
    if (!canConfigure) return;
    setSaving(true);
    try {
      const updated = await backendClient.updateOperationGovernance({ level });
      setGovernance(updated);
      toast.success(t('operationTrace.levelUpdated'));
      await load({ ...query, offset: 0 });
    } catch {
      toast.error(t('operationTrace.levelUpdateFailed'));
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
        | string
        | undefined;
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

  async function saveRetention() {
    if (!canConfigure || !governance) return;
    setSaving(true);
    try {
      // Saving the retention policy applies it immediately and keeps the
      // maintenance loop enforcing it afterwards; there is no manual prune.
      const updated = await backendClient.updateOperationGovernance({
        level: governance.configured_level,
        retention_days: retentionDays,
        max_rows: maxRows,
        dedupe_window_seconds: dedupeSeconds,
      });
      setGovernance(updated);
      toast.success(t('operationTrace.retentionUpdated'));
      await load({ ...query, offset: 0 });
    } catch {
      toast.error(t('operationTrace.retentionUpdateFailed'));
    } finally {
      setSaving(false);
    }
  }

  const levelOptions = useMemo(
    () => governance?.supported_levels ?? [],
    [governance],
  );

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
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">
            {t('operationTrace.title')}
          </p>
        </div>
        {/* Keep the actions in one right-aligned cluster: the panel toolbar
            spreads direct children apart, so they are grouped instead. */}
        <div className="ml-auto flex items-center gap-2">
          {governance && (
            <Badge
              variant={governance.configured_level > 0 ? 'default' : 'outline'}
            >
              {t(
                `operationTrace.levelNames.${governance.configured_level_name}`,
              )}
            </Badge>
          )}
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
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="size-4" />
            <h3 className="text-sm font-semibold">
              {t('operationTrace.captureLevel')}
            </h3>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            {levelOptions.map((option) => {
              const selected = governance?.configured_level === option.level;
              return (
                <button
                  key={option.level}
                  type="button"
                  disabled={!canConfigure || saving}
                  onClick={() => void changeLevel(option.level)}
                  className={`rounded-lg border p-3 text-left transition-colors disabled:opacity-60 ${
                    selected
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:bg-muted/50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">
                      {t(`${option.i18n_key}.label`)}
                    </span>
                    <Badge variant={selected ? 'default' : 'outline'}>
                      L{option.level}
                    </Badge>
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        <section className="space-y-3">
          <h3 className="text-sm font-semibold">
            {t('operationTrace.retention')}
          </h3>
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col gap-1 text-xs">
              <span className="text-muted-foreground">
                {t('operationTrace.retentionDays')}
              </span>
              <Input
                type="number"
                className="w-28"
                min={governance?.limits.min_retention_days ?? 1}
                max={governance?.limits.max_retention_days ?? 3650}
                value={retentionDays}
                disabled={!canConfigure}
                onChange={(event) =>
                  setRetentionDays(Number(event.target.value))
                }
              />
            </label>
            <label className="flex flex-col gap-1 text-xs">
              <span className="text-muted-foreground">
                {t('operationTrace.maxRows')}
              </span>
              <Input
                type="number"
                className="w-32"
                min={governance?.limits.min_max_rows ?? 100}
                max={governance?.limits.max_max_rows ?? 500000}
                value={maxRows}
                disabled={!canConfigure}
                onChange={(event) => setMaxRows(Number(event.target.value))}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs">
              <span className="text-muted-foreground">
                {t('operationTrace.dedupeWindow')}
              </span>
              <Input
                type="number"
                className="w-28"
                min={governance?.limits.min_dedupe_window_seconds ?? 0}
                max={governance?.limits.max_dedupe_window_seconds ?? 3600}
                value={dedupeSeconds}
                disabled={!canConfigure}
                onChange={(event) =>
                  setDedupeSeconds(Number(event.target.value))
                }
              />
            </label>
            <Button
              size="sm"
              onClick={() => void saveRetention()}
              disabled={!canConfigure || saving}
            >
              {t('operationTrace.save')}
            </Button>
          </div>
        </section>

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
            </div>
          </div>

          <div className="space-y-2">
            {visibleRecords.length === 0 && (
              <p className="rounded-lg border border-dashed p-6 text-center text-xs text-muted-foreground">
                {integrityFilter === 'all'
                  ? t('operationTrace.empty')
                  : t('operationTrace.emptyFiltered')}
              </p>
            )}
            {visibleRecords.map((record) => (
              <Item
                key={record.id}
                size="sm"
                variant="muted"
                className={`items-start rounded-lg ${
                  record.tampered
                    ? 'border-destructive/60 bg-destructive/5'
                    : ''
                }`}
              >
                <ItemMedia variant="icon">
                  {record.tampered ? (
                    <ShieldAlert className="size-4 text-destructive" />
                  ) : (
                    <History className="size-4" />
                  )}
                </ItemMedia>
                <ItemContent className="min-w-0">
                  <ItemTitle className="flex flex-wrap items-center gap-1.5">
                    <span>
                      {t(record.action_i18n_key, {
                        defaultValue: record.action ?? '',
                      })}
                    </span>
                    <Badge variant={outcomeVariant(record.outcome)}>
                      {t(`operationTrace.outcomes.${record.outcome}`)}
                    </Badge>
                    <Badge variant="outline">L{record.level}</Badge>
                    {record.resource_type && (
                      <Badge variant="secondary">
                        {t(
                          `operationTrace.resourceTypes.${record.resource_type}`,
                          {
                            defaultValue: record.resource_type,
                          },
                        )}
                      </Badge>
                    )}
                    {record.tampered ? (
                      <Badge variant="destructive">
                        <ShieldAlert className="size-3" />
                        {t('operationTrace.tamperedBadge')}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-emerald-600">
                        <ShieldCheck className="size-3" />
                        {t('operationTrace.verifiedBadge')}
                      </Badge>
                    )}
                  </ItemTitle>
                  <ItemDescription className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
                    <span className="font-medium">
                      {record.actor_name ??
                        record.actor_account_uuid ??
                        t('operationTrace.systemActor')}
                    </span>
                    <span aria-hidden="true">·</span>
                    <span>
                      {record.actor_role
                        ? t(`workspace.roles.${record.actor_role}`)
                        : t('operationTrace.systemActor')}
                    </span>
                    {record.http_method && (
                      <>
                        <span aria-hidden="true">·</span>
                        <span className="font-mono">{record.http_method}</span>
                      </>
                    )}
                    {record.status_code !== null && (
                      <>
                        <span aria-hidden="true">·</span>
                        <span className="font-mono">{record.status_code}</span>
                      </>
                    )}
                    <span aria-hidden="true">·</span>
                    <span>
                      {record.created_at
                        ? new Date(record.created_at).toLocaleString()
                        : ''}
                    </span>
                  </ItemDescription>
                  {record.summary && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {record.summary}
                    </p>
                  )}
                  {record.changes.length > 0 && (
                    <div className="mt-2 space-y-1 rounded-md bg-background/60 p-2">
                      {record.changes.map((change, index) => (
                        <ChangeRow
                          key={`${record.id}-${index}-${change.field}`}
                          change={change}
                          redactedLabel={t('operationTrace.redacted')}
                        />
                      ))}
                    </div>
                  )}
                </ItemContent>
                <ItemActions className="max-sm:hidden">
                  <div className="flex flex-col items-end gap-1">
                    <span className="text-xs text-muted-foreground">
                      {record.duration_ms}ms
                    </span>
                    {record.record_hash && (
                      <span
                        className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground"
                        title={record.record_hash}
                      >
                        <Fingerprint className="size-3" />
                        {record.record_hash.slice(0, 8)}
                      </span>
                    )}
                  </div>
                </ItemActions>
              </Item>
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
