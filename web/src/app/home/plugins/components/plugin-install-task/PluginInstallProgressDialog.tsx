'use client';

import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import {
  Download,
  FolderOpen,
  Package,
  FlaskConical,
  CheckCircle2,
  XCircle,
  Loader2,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  usePluginInstallTasks,
  InstallStage,
  PluginInstallTask,
} from './PluginInstallTaskContext';
import { cn } from '@/lib/utils';

const STAGES: {
  key: InstallStage;
  icon: React.ElementType;
  i18nKey: string;
}[] = [
  {
    key: InstallStage.DOWNLOADING,
    icon: Download,
    i18nKey: 'plugins.installProgress.downloading',
  },
  {
    key: InstallStage.EXTRACTING,
    icon: FolderOpen,
    i18nKey: 'plugins.installProgress.extracting',
  },
  {
    key: InstallStage.INSTALLING_DEPS,
    icon: Package,
    i18nKey: 'plugins.installProgress.installingDeps',
  },
  {
    key: InstallStage.TESTING,
    icon: FlaskConical,
    i18nKey: 'plugins.installProgress.testing',
  },
];

function getStageIndex(stage: InstallStage): number {
  const idx = STAGES.findIndex((s) => s.key === stage);
  return idx >= 0 ? idx : -1;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
}

/**
 * A single stage row — used in both active (single) and completed (all) views.
 */
function StageRow({
  icon: Icon,
  label,
  isActive,
  isCompleted,
  isError,
  detail,
}: {
  icon: React.ElementType;
  label: string;
  isActive: boolean;
  isCompleted: boolean;
  isError: boolean;
  detail?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-300',
        isActive && !isError && 'bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800',
        isCompleted && 'bg-green-50/50 dark:bg-green-950/15 border border-green-100 dark:border-green-900/50',
        isError && isActive && 'bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900',
      )}
    >
      {/* Left: status indicator */}
      <div
        className={cn(
          'flex items-center justify-center w-7 h-7 rounded-full shrink-0',
          isCompleted && 'bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400',
          isActive && !isError && !isCompleted && 'bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400',
          isError && isActive && 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400',
        )}
      >
        {isCompleted ? (
          <CheckCircle2 className="w-4 h-4" />
        ) : isError && isActive ? (
          <XCircle className="w-4 h-4" />
        ) : isActive ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Icon className="w-4 h-4" />
        )}
      </div>

      {/* Middle: label + detail */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              'text-sm font-medium',
              isActive && !isError && !isCompleted && 'text-blue-700 dark:text-blue-300',
              isCompleted && 'text-green-600 dark:text-green-400',
              isError && isActive && 'text-red-600 dark:text-red-400',
            )}
          >
            {label}
          </span>
          {/* Small icon after text */}
          <Icon
            className={cn(
              'w-3.5 h-3.5 shrink-0',
              isActive && !isError && !isCompleted && 'text-blue-400 dark:text-blue-500',
              isCompleted && 'text-green-400 dark:text-green-500',
              isError && isActive && 'text-red-400 dark:text-red-500',
            )}
          />
        </div>
        {detail && (
          <div className={cn(
            'text-xs mt-0.5',
            isCompleted ? 'text-green-600/70 dark:text-green-400/70' : 'text-blue-600/70 dark:text-blue-400/70',
          )}>
            {detail}
          </div>
        )}
      </div>
    </div>
  );
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

  const currentStageIndex = getStageIndex(task.stage);
  const isDone = task.stage === InstallStage.DONE;
  const isError = task.stage === InstallStage.ERROR;

  /** Build detail node for a stage */
  const getStageDetail = (
    stageKey: InstallStage,
    isCompletedView: boolean,
  ): React.ReactNode | undefined => {
    if (stageKey === InstallStage.DOWNLOADING) {
      // Show download progress: current / total + speed
      const dlTotal = task.downloadTotal || task.fileSize;
      const dlCurrent = task.downloadCurrent;
      const dlSpeed = task.downloadSpeed;

      if (isCompletedView && dlTotal) {
        // Done view: just show total size
        return t('plugins.installProgress.downloadSize', {
          size: formatFileSize(dlTotal),
        });
      }

      if (dlTotal && dlCurrent != null) {
        const parts: string[] = [];
        parts.push(`${formatFileSize(dlCurrent)} / ${formatFileSize(dlTotal)}`);
        if (dlSpeed && dlSpeed > 0) {
          parts.push(formatSpeed(dlSpeed));
        }
        return parts.join('  ·  ');
      }

      if (dlTotal) {
        return t('plugins.installProgress.downloadSize', {
          size: formatFileSize(dlTotal),
        });
      }

      return undefined;
    }

    if (stageKey === InstallStage.INSTALLING_DEPS) {
      const total = task.depsTotal;
      const installed = task.depsInstalled;
      const remaining = task.depsRemaining;
      const currentDep = task.currentDep;
      const dlSize = task.depsDownloadedSize;
      const speed = task.depsSpeed;

      if (isCompletedView && total != null) {
        const parts: string[] = [];
        parts.push(t('plugins.installProgress.depsInfo', { count: total }));
        if (dlSize && dlSize > 0) {
          parts.push(formatFileSize(dlSize));
        }
        return parts.join('  ·  ');
      }

      if (total != null && installed != null) {
        const parts: string[] = [];
        parts.push(
          t('plugins.installProgress.depsProgress', {
            installed,
            total,
            remaining: remaining ?? total - installed,
          }),
        );
        if (dlSize && dlSize > 0) {
          parts.push(formatFileSize(dlSize));
        }
        if (speed && speed > 0) {
          parts.push(formatSpeed(speed));
        }
        if (currentDep) {
          return (
            <>
              <span>{parts.join('  ·  ')}</span>
              <br />
              <span className="opacity-70">{currentDep}</span>
            </>
          );
        }
        return parts.join('  ·  ');
      }

      if (total != null) {
        return t('plugins.installProgress.depsInfo', { count: total });
      }

      return undefined;
    }

    return undefined;
  };

  return (
    <div className="space-y-4">
      {/* Overall progress bar — always blue */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className={cn(
            'text-sm font-medium',
            isDone ? 'text-green-700 dark:text-green-300' : 'text-blue-700 dark:text-blue-300',
          )}>
            {isDone
              ? t('plugins.installProgress.completed')
              : isError
                ? t('plugins.installProgress.failed')
                : t('plugins.installProgress.overallProgress')}
          </span>
          <span className={cn(
            'text-sm font-medium',
            isDone ? 'text-green-600 dark:text-green-400' : 'text-blue-600 dark:text-blue-400',
          )}>
            {isDone ? '100%' : `${task.overallProgress}%`}
          </span>
        </div>
        <Progress
          value={isDone ? 100 : task.overallProgress}
          className={cn(
            'h-2.5',
            '[&>div]:bg-blue-500 dark:[&>div]:bg-blue-400',
            'bg-blue-100 dark:bg-blue-900/30',
            isDone && '[&>div]:bg-green-500 dark:[&>div]:bg-green-400 bg-green-100 dark:bg-green-900/30',
            isError && '[&>div]:bg-red-500 dark:[&>div]:bg-red-400 bg-red-100 dark:bg-red-900/30',
          )}
        />
      </div>

      {/* Stage display */}
      <div className="space-y-1.5">
        {isDone ? (
          /* When done: show all stages with completed style */
          STAGES.map((stageConfig) => (
            <StageRow
              key={stageConfig.key}
              icon={stageConfig.icon}
              label={t(stageConfig.i18nKey)}
              isActive={false}
              isCompleted={true}
              isError={false}
              detail={getStageDetail(stageConfig.key, true)}
            />
          ))
        ) : isError ? (
          /* Error: show the failed stage */
          currentStageIndex >= 0 && (
            <StageRow
              icon={STAGES[currentStageIndex].icon}
              label={t(STAGES[currentStageIndex].i18nKey)}
              isActive={true}
              isCompleted={false}
              isError={true}
              detail={task.error}
            />
          )
        ) : (
          /* In progress: only show the current active stage */
          currentStageIndex >= 0 && (
            <StageRow
              icon={STAGES[currentStageIndex].icon}
              label={t(STAGES[currentStageIndex].i18nKey)}
              isActive={true}
              isCompleted={false}
              isError={false}
              detail={getStageDetail(STAGES[currentStageIndex].key, false)}
            />
          )
        )}
      </div>

      {/* Done banner */}
      {isDone && (
        <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-900">
          <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
          <span className="text-sm text-green-700 dark:text-green-300 font-medium">
            {t('plugins.installProgress.installComplete')}
          </span>
        </div>
      )}

      {/* Error detail */}
      {isError && task.error && (
        <div className="px-3 py-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900">
          <p className="text-xs text-red-600 dark:text-red-400 break-all line-clamp-4">
            {task.error}
          </p>
        </div>
      )}
    </div>
  );
}

export default function PluginInstallProgressDialog() {
  const { t } = useTranslation();
  const { tasks, selectedTaskId, setSelectedTaskId, removeTask } =
    usePluginInstallTasks();

  const selectedTask = tasks.find((t) => t.id === selectedTaskId) || null;
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
      <DialogContent className="w-[460px] max-h-[80vh] p-6 bg-white dark:bg-[#1a1a1e] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <Download className="size-5" />
            <span className="truncate">
              {selectedTask
                ? t('plugins.installProgress.title', {
                    name: selectedTask.pluginName,
                  })
                : t('plugins.installProgress.titleGeneric')}
            </span>
          </DialogTitle>
        </DialogHeader>

        {selectedTask && <TaskProgressContent task={selectedTask} />}

        <div className="flex justify-end gap-2 mt-2">
          {selectedTask &&
            (selectedTask.stage === InstallStage.DONE ||
              selectedTask.stage === InstallStage.ERROR) && (
              <Button variant="outline" size="sm" onClick={handleDismiss}>
                {t('plugins.installProgress.dismiss')}
              </Button>
            )}
          <Button variant="default" size="sm" onClick={handleClose}>
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
