import { useEffect, useState } from 'react';
import { backendClient } from '@/app/infra/http';
import type { Plugin } from '@/app/infra/entities/plugin';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ShieldAlert } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import {
  Download,
  CheckCircle2,
  XCircle,
  Loader2,
  RefreshCcw,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  usePluginInstallTasks,
  InstallStage,
  PluginInstallTask,
} from './PluginInstallTaskContext';
import PluginPermissions from '@/app/home/plugins/components/PluginPermissions';
import PluginInstallFollowUp, { NextStepBanner } from './PluginInstallFollowUp';

type StageConfig = {
  key: InstallStage;
  i18nKey: string;
};

function getStages(task: PluginInstallTask): StageConfig[] {
  return [
    ...(task.operation === 'upgrade'
      ? [
          {
            key: InstallStage.CHECKING,
            i18nKey: 'plugins.installProgress.checkingUpdate',
          } as StageConfig,
        ]
      : []),
    {
      key: InstallStage.DOWNLOADING,
      i18nKey: 'plugins.installProgress.downloading',
    },
    {
      key: InstallStage.VALIDATING,
      i18nKey: 'plugins.installProgress.validating',
    },
    {
      key: InstallStage.INSTALLING_DEPS,
      i18nKey:
        task.operation === 'upgrade'
          ? 'plugins.installProgress.applyingUpdate'
          : 'plugins.installProgress.installingDeps',
    },
    {
      key: InstallStage.LAUNCHING,
      i18nKey: 'plugins.installProgress.activating',
    },
  ];
}

function getStageIndex(stages: StageConfig[], stage: InstallStage): number {
  const displayStage =
    stage === InstallStage.INITIALIZING ? InstallStage.LAUNCHING : stage;
  const idx = stages.findIndex((item) => item.key === displayStage);
  return idx >= 0 ? idx : -1;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
}

function formatSpeed(bytesPerSec: number): string {
  if (bytesPerSec === 0) return '0 B/s';
  const k = 1024;
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
  const i = Math.floor(Math.log(bytesPerSec) / Math.log(k));
  return (bytesPerSec / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
}

function TaskProgressContent({ task }: { task: PluginInstallTask }) {
  const { t } = useTranslation();
  const { setSelectedTaskId } = usePluginInstallTasks();

  const stages = getStages(task);
  const isDone = task.stage === InstallStage.DONE;
  const isError = task.stage === InstallStage.ERROR;
  const currentStageIndex = getStageIndex(stages, task.stage);

  // Keep the dialog compact: show only the current step + overall progress
  // while running, and a single result banner when done / failed.
  // MCP / Skill have no plugin stages, so they use a generic label.
  const isPlugin = task.extensionType === 'plugin';
  const [pendingConfirmation, setPendingConfirmation] = useState<
    boolean | null
  >(task.pendingConfirmation ?? null);
  const [installedPlugin, setInstalledPlugin] = useState<Plugin | null>(null);
  // Set once permissions are granted in this dialog. The plugin restarts
  // right after, so re-reading it can briefly fail or lag; trust the grant.
  const [grantedHere, setGrantedHere] = useState(false);
  useEffect(() => {
    if (!isDone || !isPlugin) return;
    let cancelled = false;
    setPendingConfirmation(task.pendingConfirmation ?? null);
    setInstalledPlugin(null);
    const [author, name] = task.pluginName.split('/');
    if (author && name) {
      // The post-install follow-up steps depend on the components that
      // actually shipped, so they come from the installed plugin. It may
      // still be starting, so re-read until it lists its components (or
      // turns out to wait for a permission review).
      void (async () => {
        for (let attempt = 0; attempt < 30 && !cancelled; attempt += 1) {
          try {
            const { plugin } = await backendClient.getPlugin(author, name);
            if (cancelled) return;
            const pending =
              plugin.permission_status?.pending_confirmation ?? false;
            setPendingConfirmation(pending);
            setInstalledPlugin(plugin);
            if (
              pending ||
              (plugin.status === 'initialized' && plugin.components?.length)
            ) {
              return;
            }
          } catch {
            // Not readable yet; keep trying.
          }
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      })();
    }
    return () => {
      cancelled = true;
    };
  }, [isDone, isPlugin, task.pluginName, task.pendingConfirmation]);
  const needsReview =
    isDone && isPlugin && !grantedHere && pendingConfirmation !== false;
  // The next steps come from the installed manifest. A plugin awaiting
  // permissions is not started yet and reports no components, so after the
  // grant re-read it until the restarted plugin is up and lists them.
  useEffect(() => {
    if (!grantedHere) return;
    const [author, name] = task.pluginName.split('/');
    if (!author || !name) return;
    let cancelled = false;
    void (async () => {
      for (let attempt = 0; attempt < 30 && !cancelled; attempt += 1) {
        try {
          const { plugin } = await backendClient.getPlugin(author, name);
          if (cancelled) return;
          setInstalledPlugin(plugin);
          if (plugin.status === 'initialized' && plugin.components?.length) {
            return;
          }
        } catch {
          // The plugin restarts right after the grant; keep trying.
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [grantedHere, task.pluginName]);
  const simpleInstallingLabel =
    task.extensionType === 'mcp'
      ? t('addExtension.installStage.mcpInstalling')
      : t('addExtension.installStage.skillInstalling');

  const currentStage =
    currentStageIndex >= 0 ? stages[currentStageIndex] : undefined;
  const statusLabel = isPlugin
    ? currentStage
      ? t(currentStage.i18nKey)
      : t('plugins.installProgress.overallProgress')
    : simpleInstallingLabel;

  /** Download progress text (only meaningful while downloading). */
  const getDownloadDetail = (): string | undefined => {
    if (!isPlugin || task.stage !== InstallStage.DOWNLOADING) return undefined;
    const dlTotal = task.downloadTotal || task.fileSize;
    const dlCurrent = task.downloadCurrent;
    if (!dlTotal) return undefined;
    if (dlCurrent == null) {
      return t('plugins.installProgress.downloadSize', {
        size: formatFileSize(dlTotal),
      });
    }
    const parts = [`${formatFileSize(dlCurrent)} / ${formatFileSize(dlTotal)}`];
    if (task.downloadSpeed && task.downloadSpeed > 0) {
      parts.push(formatSpeed(task.downloadSpeed));
    }
    return parts.join(' · ');
  };

  if (isDone) {
    const title = needsReview
      ? t('pluginPermissions.pending')
      : !isPlugin
        ? t('addExtension.installStage.installed')
        : task.operation === 'upgrade'
          ? t('plugins.installProgress.updateComplete')
          : t('plugins.installProgress.installComplete');
    return (
      <NextStepBanner
        tone={needsReview ? 'attention' : 'success'}
        icon={needsReview ? ShieldAlert : CheckCircle2}
        title={title}
      >
        {/* Confirm permissions right here; the next steps follow once done. */}
        {needsReview && task.pluginName.includes('/') && (
          <div className="border-t p-2" data-testid="install-permission-review">
            <PluginPermissions
              author={task.pluginName.split('/')[0]}
              name={task.pluginName.split('/')[1]}
              onChange={() => setGrantedHere(true)}
            />
          </div>
        )}
        {isPlugin && !needsReview && (
          <PluginInstallFollowUp
            plugin={installedPlugin}
            onNavigate={() => setSelectedTaskId(null)}
          />
        )}
      </NextStepBanner>
    );
  }

  if (isError) {
    return (
      <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900">
        <XCircle className="w-5 h-5 shrink-0 text-red-600 dark:text-red-400" />
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-medium text-red-700 dark:text-red-300">
            {t('plugins.installProgress.failed')}
          </p>
          {task.error && (
            <p className="text-xs text-red-600 dark:text-red-400 break-all line-clamp-4">
              {task.error}
            </p>
          )}
        </div>
      </div>
    );
  }

  const detail = getDownloadDetail();

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="flex items-center gap-2 min-w-0 text-blue-700 dark:text-blue-300 font-medium">
          <Loader2 className="w-4 h-4 shrink-0 animate-spin" />
          <span className="truncate">{statusLabel}</span>
        </span>
        <span className="shrink-0 text-blue-600 dark:text-blue-400 font-medium">
          {task.overallProgress}%
        </span>
      </div>
      <Progress
        value={task.overallProgress}
        className="h-2 bg-blue-100 dark:bg-blue-900/30 [&>div]:bg-blue-500 dark:[&>div]:bg-blue-400"
      />
      {detail && (
        <p className="text-xs text-muted-foreground break-words">{detail}</p>
      )}
    </div>
  );
}

export default function PluginInstallProgressDialog() {
  const { t } = useTranslation();
  const { tasks, selectedTaskId, setSelectedTaskId, removeTask } =
    usePluginInstallTasks();

  const selectedTask = tasks.find((t) => t.id === selectedTaskId) || null;
  const TitleIcon =
    selectedTask?.operation === 'upgrade' ? RefreshCcw : Download;
  const open = !!selectedTask;

  const handleClose = () => {
    setSelectedTaskId(null);
  };

  const handleDismiss = () => {
    if (selectedTask) {
      if (
        selectedTask.stage === InstallStage.DONE ||
        selectedTask.stage === InstallStage.ERROR
      ) {
        removeTask(selectedTask.id);
      }
    }
    setSelectedTaskId(null);
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent
        className="sm:max-w-lg w-[90vw] max-h-[80vh] p-4 sm:p-6 bg-white dark:bg-[#1a1a1e] overflow-y-auto overflow-x-hidden"
        hideCloseButton
      >
        <DialogHeader>
          <DialogTitle className="flex items-start gap-3">
            <TitleIcon className="size-5 shrink-0 mt-0.5" />
            <span className="break-words">
              {selectedTask
                ? selectedTask.operation === 'upgrade'
                  ? t('plugins.installProgress.updateTitle', {
                      name: selectedTask.pluginName,
                    })
                  : t('plugins.installProgress.title', {
                      name: selectedTask.pluginName,
                    })
                : t('plugins.installProgress.titleGeneric')}
            </span>
          </DialogTitle>
        </DialogHeader>

        {selectedTask && <TaskProgressContent task={selectedTask} />}

        <div className="flex justify-end gap-2 mt-2">
          <Button
            variant="default"
            size="sm"
            onClick={
              selectedTask?.stage === InstallStage.DONE ||
              selectedTask?.stage === InstallStage.ERROR
                ? handleDismiss
                : handleClose
            }
          >
            {selectedTask?.stage === InstallStage.DONE ||
            selectedTask?.stage === InstallStage.ERROR
              ? t('common.close')
              : t('plugins.installProgress.background')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
