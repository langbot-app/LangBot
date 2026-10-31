'use client';

import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  Archive,
  Clock,
  Database,
  FileWarning,
  HardDrive,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { backendClient } from '@/app/infra/http';
import { PanelToolbar } from '../settings-dialog/panel-layout';

interface StorageSection {
  key: string;
  path: string;
  exists: boolean;
  size_bytes: number;
  file_count: number;
}

interface RuntimeStorageDirectory extends StorageSection {
  kind: 'root' | 'detail';
  parent_key?: string;
  error_count?: number;
  scope?: 'runtime_host' | 'sandbox_sessions';
}

interface RuntimeStorageProcess {
  key: 'langbot' | 'plugin_runtime' | 'box_runtime';
  status: 'available' | 'unavailable' | 'disabled' | 'not_applicable';
  source: 'local_process' | 'runtime_rpc';
  size_bytes: number | null;
  directories: RuntimeStorageDirectory[];
  error?: string;
  active_sessions?: number | null;
  managed_processes?: number | null;
}

interface CleanupCandidate {
  key?: string;
  name?: string;
  size_bytes: number;
  modified_at?: string;
  date?: string;
}

interface StorageAnalysis {
  generated_at: string;
  cleanup_policy: {
    uploaded_file_retention_days: number;
    log_retention_days: number;
  };
  sections: StorageSection[];
  processes?: RuntimeStorageProcess[];
  total_size_bytes?: number;
  database: {
    type: string;
    monitoring_counts: Record<string, number>;
    binary_storage: {
      count: number;
      size_bytes: number | null;
    };
  };
  cleanup_candidates: {
    uploaded_files: CleanupCandidate[];
    log_files: CleanupCandidate[];
  };
  tasks: Record<string, number | undefined>;
}

interface StorageAnalysisPanelProps {
  // True when this panel is the active section and the dialog is open.
  active: boolean;
}

function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) {
    return '-';
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 ? 1 : 2)} ${units[unitIndex]}`;
}

export default function StorageAnalysisPanel({
  active,
}: StorageAnalysisPanelProps) {
  const { t } = useTranslation();
  const [analysis, setAnalysis] = useState<StorageAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await backendClient.get<StorageAnalysis>(
        '/api/v1/system/storage-analysis',
      );
      setAnalysis(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (active) {
      loadAnalysis();
    }
  }, [loadAnalysis, active]);

  const totalBytes = useMemo(() => {
    return (
      analysis?.total_size_bytes ??
      analysis?.sections.reduce((sum, item) => sum + item.size_bytes, 0) ??
      0
    );
  }, [analysis]);

  const uploadedCandidateBytes = useMemo(() => {
    return (
      analysis?.cleanup_candidates.uploaded_files.reduce(
        (sum, item) => sum + item.size_bytes,
        0,
      ) ?? 0
    );
  }, [analysis]);

  const logCandidateBytes = useMemo(() => {
    return (
      analysis?.cleanup_candidates.log_files.reduce(
        (sum, item) => sum + item.size_bytes,
        0,
      ) ?? 0
    );
  }, [analysis]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PanelToolbar>
        <div className="text-sm text-muted-foreground">
          {analysis
            ? t('storageAnalysis.generatedAt', {
                time: new Date(analysis.generated_at).toLocaleString(),
              })
            : t('storageAnalysis.loading')}
        </div>
        <Button
          onClick={loadAnalysis}
          variant="outline"
          size="sm"
          disabled={loading}
        >
          <RefreshCw
            className={`mr-2 size-4 ${loading ? 'animate-spin' : ''}`}
          />
          {t('storageAnalysis.refresh')}
        </Button>
      </PanelToolbar>

      <ScrollArea className="min-h-0 flex-1 overflow-hidden">
        <div className="space-y-5 px-6 py-5">
          {error && (
            <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertCircle className="mt-0.5 size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loading && !analysis && <StorageAnalysisSkeleton />}

          {analysis && (
            <>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                <SummaryItem
                  label={t('storageAnalysis.totalSize')}
                  value={formatBytes(totalBytes)}
                  icon={<HardDrive className="size-4" />}
                />
                <SummaryItem
                  label={t('storageAnalysis.binaryStorage')}
                  value={formatBytes(
                    analysis.database.binary_storage.size_bytes,
                  )}
                  meta={`${analysis.database.binary_storage.count}`}
                  icon={<Database className="size-4" />}
                />
                <SummaryItem
                  label={t('storageAnalysis.uploadCleanup')}
                  value={formatBytes(uploadedCandidateBytes)}
                  meta={`${analysis.cleanup_candidates.uploaded_files.length}`}
                  icon={<FileWarning className="size-4" />}
                />
                <SummaryItem
                  label={t('storageAnalysis.logCleanup')}
                  value={formatBytes(logCandidateBytes)}
                  meta={`${analysis.cleanup_candidates.log_files.length}`}
                  icon={<FileWarning className="size-4" />}
                />
              </div>

              <section className="rounded-md border px-3 py-3">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-medium">
                  <Clock className="size-4 text-muted-foreground" />
                  {t('storageAnalysis.cleanupPolicy')}
                </h2>
                <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-3">
                  <PolicyItem
                    label={t('storageAnalysis.uploadRetention')}
                    value={`${analysis.cleanup_policy.uploaded_file_retention_days} ${t('storageAnalysis.days')}`}
                  />
                  <PolicyItem
                    label={t('storageAnalysis.logRetention')}
                    value={`${analysis.cleanup_policy.log_retention_days} ${t('storageAnalysis.days')}`}
                  />
                  <PolicyItem
                    label={t('storageAnalysis.databaseType')}
                    value={analysis.database.type}
                  />
                </div>
              </section>

              {analysis.processes?.length ? (
                <section>
                  <div className="mb-3">
                    <h2 className="text-sm font-medium">
                      {t('storageAnalysis.processStorage')}
                    </h2>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {t('storageAnalysis.processStorageDescription')}
                    </p>
                  </div>
                  <div className="space-y-3">
                    {analysis.processes.map((process) => (
                      <RuntimeStorageGroup
                        key={process.key}
                        process={process}
                      />
                    ))}
                  </div>
                </section>
              ) : (
                <LegacyStorageSections sections={analysis.sections} />
              )}

              <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <MetricPanel
                  title={t('storageAnalysis.monitoringTables')}
                  values={analysis.database.monitoring_counts}
                />
                <MetricPanel
                  title={t('storageAnalysis.runtimeTasks')}
                  values={analysis.tasks}
                />
              </section>

              <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <CandidatePanel
                  title={t('storageAnalysis.expiredUploads')}
                  emptyText={t('storageAnalysis.noExpiredUploads')}
                  candidates={analysis.cleanup_candidates.uploaded_files}
                />
                <CandidatePanel
                  title={t('storageAnalysis.expiredLogs')}
                  emptyText={t('storageAnalysis.noExpiredLogs')}
                  candidates={analysis.cleanup_candidates.log_files}
                />
              </section>
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

function StorageAnalysisSkeleton() {
  return (
    <div className="space-y-4" aria-hidden="true">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-24 rounded-md" />
        ))}
      </div>
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="space-y-3 rounded-md border p-4">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ))}
    </div>
  );
}

function RuntimeStorageGroup({ process }: { process: RuntimeStorageProcess }) {
  const { t } = useTranslation();
  const available = process.status === 'available';

  return (
    <div className="overflow-hidden rounded-md border bg-card">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b bg-muted/20 px-4 py-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">
              {t(`storageAnalysis.processNames.${process.key}`)}
            </h3>
            <Badge variant={available ? 'secondary' : 'outline'}>
              {t(`storageAnalysis.statusLabels.${process.status}`)}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {t(`storageAnalysis.processDescriptions.${process.key}`)}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {t(`storageAnalysis.sourceLabels.${process.source}`)}
          </p>
        </div>
        <div className="text-right">
          <div className="text-base font-semibold tabular-nums">
            {formatBytes(process.size_bytes)}
          </div>
          {process.key === 'box_runtime' && available && (
            <div className="mt-1 text-xs text-muted-foreground">
              {t('storageAnalysis.boxActivity', {
                sessions: process.active_sessions ?? 0,
                processes: process.managed_processes ?? 0,
              })}
            </div>
          )}
        </div>
      </div>

      {!available ? (
        <div className="px-4 py-4 text-sm text-muted-foreground">
          {process.error || t('storageAnalysis.runtimeUnavailable')}
        </div>
      ) : process.directories.length === 0 ? (
        <div className="px-4 py-6 text-center text-sm text-muted-foreground">
          {t('storageAnalysis.noManagedDirectories')}
        </div>
      ) : (
        <div>
          <div className="hidden grid-cols-[minmax(0,1fr)_100px_90px] gap-4 border-b px-4 py-2 text-xs text-muted-foreground sm:grid">
            <span>{t('storageAnalysis.directory')}</span>
            <span className="text-right">{t('storageAnalysis.size')}</span>
            <span className="text-right">{t('storageAnalysis.files')}</span>
          </div>
          {process.directories.map((directory) => (
            <div
              key={directory.key}
              className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 border-b px-4 py-3 text-sm last:border-b-0 sm:grid-cols-[minmax(0,1fr)_100px_90px] sm:gap-4"
            >
              <div
                className={`min-w-0 ${
                  directory.kind === 'detail'
                    ? 'ml-3 border-l-2 border-muted pl-3'
                    : ''
                }`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">
                    {t(`storageAnalysis.sectionNames.${directory.key}`)}
                  </span>
                  {!directory.exists && (
                    <Badge variant="outline" className="font-normal">
                      {t('storageAnalysis.notCreated')}
                    </Badge>
                  )}
                  {!!directory.error_count && (
                    <Badge variant="outline" className="font-normal">
                      {t('storageAnalysis.scanWarnings', {
                        count: directory.error_count,
                      })}
                    </Badge>
                  )}
                  {directory.scope && (
                    <Badge variant="outline" className="font-normal">
                      {t(`storageAnalysis.scopeLabels.${directory.scope}`)}
                    </Badge>
                  )}
                </div>
                <div className="mt-1 break-all font-mono text-xs text-muted-foreground">
                  {directory.path || '-'}
                </div>
              </div>
              <div className="self-center text-right tabular-nums">
                {formatBytes(directory.size_bytes)}
              </div>
              <div className="col-span-2 self-center text-right text-xs text-muted-foreground tabular-nums sm:col-span-1 sm:text-sm">
                {directory.file_count}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LegacyStorageSections({ sections }: { sections: StorageSection[] }) {
  const { t } = useTranslation();
  return (
    <section>
      <h2 className="mb-2 text-sm font-medium">
        {t('storageAnalysis.sections')}
      </h2>
      <div className="overflow-hidden rounded-md border">
        {sections.map((section) => (
          <div
            key={section.key}
            className="grid grid-cols-[1fr_auto_auto_auto] gap-3 border-b px-3 py-2 text-sm last:border-b-0"
          >
            <div className="min-w-0">
              <div className="font-medium">
                {t(`storageAnalysis.sectionNames.${section.key}`)}
              </div>
              <div className="break-all text-xs text-muted-foreground">
                {section.path || '-'}
              </div>
            </div>
            {section.exists ? (
              <span />
            ) : (
              <Badge variant="outline" className="self-center">
                {t('storageAnalysis.missing')}
              </Badge>
            )}
            <div className="self-center tabular-nums">
              {formatBytes(section.size_bytes)}
            </div>
            <div className="self-center text-muted-foreground tabular-nums">
              {section.file_count}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function SummaryItem({
  label,
  value,
  icon,
  meta,
}: {
  label: string;
  value: string;
  icon: ReactNode;
  meta?: string;
}) {
  return (
    <div className="rounded-md border px-3 py-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-2 flex items-end justify-between gap-2">
        <span className="text-xl font-semibold tabular-nums">{value}</span>
        {meta && <span className="text-xs text-muted-foreground">{meta}</span>}
      </div>
    </div>
  );
}

function PolicyItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/40 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 font-medium">{value}</div>
    </div>
  );
}

function MetricPanel({
  title,
  values,
}: {
  title: string;
  values: Record<string, number | undefined>;
}) {
  return (
    <div>
      <h2 className="mb-2 text-sm font-medium">{title}</h2>
      <div className="rounded-md border">
        {Object.entries(values).map(([key, value]) => (
          <div
            key={key}
            className="flex items-center justify-between border-b px-3 py-2 text-sm last:border-b-0"
          >
            <span className="text-muted-foreground">{key}</span>
            <span className="font-medium tabular-nums">{value ?? '-'}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function CandidatePanel({
  title,
  emptyText,
  candidates,
}: {
  title: string;
  emptyText: string;
  candidates: CleanupCandidate[];
}) {
  return (
    <div>
      <h2 className="mb-2 flex items-center gap-2 text-sm font-medium">
        <Archive className="size-4 text-muted-foreground" />
        {title}
      </h2>
      <div className="rounded-md border">
        {candidates.length === 0 ? (
          <div className="px-3 py-6 text-center text-sm text-muted-foreground">
            {emptyText}
          </div>
        ) : (
          candidates.slice(0, 8).map((candidate, index) => (
            <div
              key={`${candidate.key ?? candidate.name}-${index}`}
              className="grid grid-cols-[1fr_auto] gap-3 border-b px-3 py-2 text-sm last:border-b-0"
            >
              <div className="min-w-0">
                <div className="truncate font-medium">
                  {candidate.key ?? candidate.name}
                </div>
                <div className="text-xs text-muted-foreground">
                  {candidate.modified_at ?? candidate.date ?? '-'}
                </div>
              </div>
              <div className="self-center tabular-nums">
                {formatBytes(candidate.size_bytes)}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
