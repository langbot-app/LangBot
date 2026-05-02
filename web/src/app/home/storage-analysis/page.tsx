'use client';

import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, HardDrive, Database, FileWarning } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { backendClient } from '@/app/infra/http';

interface StorageSection {
  key: string;
  path: string;
  exists: boolean;
  size_bytes: number;
  file_count: number;
}

interface CleanupCandidate {
  key?: string;
  name?: string;
  size_bytes: number;
}

interface StorageAnalysis {
  generated_at: string;
  cleanup_policy: {
    uploaded_file_retention_days: number;
    log_retention_days: number;
  };
  sections: StorageSection[];
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
  tasks: {
    total?: number;
    running?: number;
    completed?: number;
  };
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

export default function StorageAnalysisPage() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(true);
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
    loadAnalysis();
  }, [loadAnalysis]);

  const totalBytes = useMemo(() => {
    return (
      analysis?.sections.reduce((sum, item) => sum + item.size_bytes, 0) ?? 0
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
    <div className="h-full px-6 py-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">
            {t('storageAnalysis.title')}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t('storageAnalysis.description')}
          </p>
        </div>
        <Button onClick={() => setOpen(true)} variant="outline">
          <HardDrive className="mr-2 size-4" />
          {t('storageAnalysis.openDialog')}
        </Button>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-4xl max-h-[82vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <HardDrive className="size-5 text-blue-500" />
              {t('storageAnalysis.dialogTitle')}
            </DialogTitle>
          </DialogHeader>

          <div className="flex items-center justify-between gap-3">
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
          </div>

          {error && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          {analysis && (
            <div className="space-y-5">
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
                  icon={<Database className="size-4" />}
                />
                <SummaryItem
                  label={t('storageAnalysis.uploadCleanup')}
                  value={formatBytes(uploadedCandidateBytes)}
                  icon={<FileWarning className="size-4" />}
                />
                <SummaryItem
                  label={t('storageAnalysis.logCleanup')}
                  value={formatBytes(logCandidateBytes)}
                  icon={<FileWarning className="size-4" />}
                />
              </div>

              <section>
                <h2 className="mb-2 text-sm font-medium">
                  {t('storageAnalysis.sections')}
                </h2>
                <div className="overflow-hidden rounded-md border">
                  {analysis.sections.map((section) => (
                    <div
                      key={section.key}
                      className="grid grid-cols-[1fr_auto_auto] gap-3 border-b px-3 py-2 text-sm last:border-b-0"
                    >
                      <div>
                        <div className="font-medium">
                          {t(`storageAnalysis.sectionNames.${section.key}`)}
                        </div>
                        <div className="break-all text-xs text-muted-foreground">
                          {section.path}
                        </div>
                      </div>
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

              <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <h2 className="mb-2 text-sm font-medium">
                    {t('storageAnalysis.monitoringTables')}
                  </h2>
                  <KeyValueList values={analysis.database.monitoring_counts} />
                </div>
                <div>
                  <h2 className="mb-2 text-sm font-medium">
                    {t('storageAnalysis.runtimeTasks')}
                  </h2>
                  <KeyValueList values={analysis.tasks} />
                </div>
              </section>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SummaryItem({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: ReactNode;
}) {
  return (
    <div className="rounded-md border px-3 py-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-2 text-xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function KeyValueList({
  values,
}: {
  values: Record<string, number | undefined>;
}) {
  return (
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
  );
}
