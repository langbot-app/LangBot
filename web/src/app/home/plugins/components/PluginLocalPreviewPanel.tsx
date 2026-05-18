import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Archive, CheckCircle2, Loader2, Package } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { httpClient } from '@/app/infra/http/HttpClient';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { usePluginInstallTasks } from '@/app/home/plugins/components/plugin-install-task';
import PluginComponentList from '@/app/home/plugins/components/plugin-installed/PluginComponentList';

type PluginLocalPreview = Awaited<
  ReturnType<typeof httpClient.previewPluginInstallFromLocal>
>;

interface PluginLocalPreviewPanelProps {
  file: File;
  onInstallStarted?: () => void;
  onCancel?: () => void;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
}

export default function PluginLocalPreviewPanel({
  file,
  onInstallStarted,
  onCancel,
}: PluginLocalPreviewPanelProps) {
  const { t } = useTranslation();
  const { addTask, setSelectedTaskId } = usePluginInstallTasks();
  const [preview, setPreview] = useState<PluginLocalPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadPreview = useCallback(async () => {
    setPreviewing(true);
    setPreview(null);
    setErrorMessage(null);
    try {
      const result = await httpClient.previewPluginInstallFromLocal(file);
      setPreview(result);
    } catch (error: unknown) {
      const message =
        error instanceof Error
          ? error.message
          : typeof error === 'object' && error && 'msg' in error
            ? String((error as { msg?: string }).msg || '')
            : String(error);
      setErrorMessage(message || t('plugins.localPreview.failed'));
    } finally {
      setPreviewing(false);
    }
  }, [file, t]);

  useEffect(() => {
    void loadPreview();
  }, [loadPreview]);

  async function handleInstall() {
    setInstalling(true);
    setErrorMessage(null);
    try {
      const resp = await httpClient.installPluginFromLocal(file);
      const taskId = resp.task_id;
      const taskKey = `local-${taskId}`;
      const pluginName =
        preview?.metadata.label && extractI18nObject(preview.metadata.label)
          ? extractI18nObject(preview.metadata.label)
          : preview?.metadata.name || file.name;

      addTask({
        taskId,
        pluginName,
        source: 'local',
        extensionType: 'plugin',
        fileSize: file.size,
      });
      setSelectedTaskId(taskKey);
      toast.success(t('plugins.installSuccess'));
      onInstallStarted?.();
    } catch (error: unknown) {
      const message =
        error instanceof Error
          ? error.message
          : typeof error === 'object' && error && 'msg' in error
            ? String((error as { msg?: string }).msg || '')
            : String(error);
      setErrorMessage(message || t('plugins.installFailed'));
    } finally {
      setInstalling(false);
    }
  }

  const metadata = preview?.metadata;
  const label = metadata?.label ? extractI18nObject(metadata.label) : '';
  const description = metadata?.description
    ? extractI18nObject(metadata.description)
    : '';
  const componentCounts = preview?.component_counts || {};

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 rounded-md bg-muted/40 px-3 py-3">
        <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md bg-background text-muted-foreground">
          {previewing ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Archive className="size-4" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">
            {previewing
              ? t('plugins.localPreview.unpacking')
              : t('plugins.localPreview.unpackComplete')}
          </div>
          <div className="mt-1 break-all text-xs text-muted-foreground">
            {file.name} · {formatFileSize(file.size)}
          </div>
        </div>
      </div>

      {preview && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Package className="size-4" />
            {t('plugins.localPreview.pluginInfo')}
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">
                {t('plugins.localPreview.name')}
              </span>
              <span className="truncate font-medium">
                {label || metadata?.name || '-'}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">
                {t('plugins.localPreview.author')}
              </span>
              <span className="truncate">{metadata?.author || '-'}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">
                {t('plugins.localPreview.version')}
              </span>
              <span>{metadata?.version || '-'}</span>
            </div>
          </div>
          {description && (
            <p className="text-sm leading-6 text-muted-foreground">
              {description}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <PluginComponentList
              components={componentCounts}
              showComponentName
              showTitle
              useBadge
              t={t}
            />
          </div>
        </div>
      )}

      {preview && (
        <div className="flex items-center gap-2 text-sm text-green-700 dark:text-green-300">
          <CheckCircle2 className="size-4" />
          {t('plugins.localPreview.ready')}
        </div>
      )}

      {errorMessage && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {errorMessage}
        </div>
      )}

      <div className="flex justify-end gap-2">
        {onCancel && (
          <Button variant="outline" onClick={onCancel} disabled={installing}>
            {t('common.cancel')}
          </Button>
        )}
        <Button
          type="button"
          onClick={handleInstall}
          disabled={!preview || previewing || installing}
        >
          {installing ? t('plugins.installing') : t('plugins.confirmInstall')}
        </Button>
      </div>
    </div>
  );
}
