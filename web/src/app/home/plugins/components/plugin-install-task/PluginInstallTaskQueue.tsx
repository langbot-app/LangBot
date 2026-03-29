'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';
import { Progress } from '@/components/ui/progress';
import {
  Download,
  FolderOpen,
  Package,
  FlaskConical,
  CheckCircle2,
  XCircle,
  Loader2,
  X,
  ListTodo,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Badge } from '@/components/ui/badge';
import {
  usePluginInstallTasks,
  InstallStage,
  PluginInstallTask,
} from './PluginInstallTaskContext';
import { cn } from '@/lib/utils';

const STAGE_ICONS: Record<string, React.ElementType> = {
  [InstallStage.DOWNLOADING]: Download,
  [InstallStage.EXTRACTING]: FolderOpen,
  [InstallStage.INSTALLING_DEPS]: Package,
  [InstallStage.TESTING]: FlaskConical,
  [InstallStage.DONE]: CheckCircle2,
  [InstallStage.ERROR]: XCircle,
};

function TaskQueueItem({
  task,
  onClick,
  onRemove,
}: {
  task: PluginInstallTask;
  onClick: () => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const isDone = task.stage === InstallStage.DONE;
  const isError = task.stage === InstallStage.ERROR;
  const isRunning = !isDone && !isError;
  const StageIcon = STAGE_ICONS[task.stage] || Download;

  const stageLabel = (() => {
    switch (task.stage) {
      case InstallStage.DOWNLOADING:
        return t('plugins.installProgress.downloading');
      case InstallStage.EXTRACTING:
        return t('plugins.installProgress.extracting');
      case InstallStage.INSTALLING_DEPS:
        return t('plugins.installProgress.installingDeps');
      case InstallStage.TESTING:
        return t('plugins.installProgress.testing');
      case InstallStage.DONE:
        return t('plugins.installProgress.completed');
      case InstallStage.ERROR:
        return t('plugins.installProgress.failed');
      default:
        return '';
    }
  })();

  return (
    <div
      className="flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-muted/60 cursor-pointer transition-colors group"
      onClick={onClick}
    >
      <div
        className={cn(
          'flex items-center justify-center w-7 h-7 rounded-full shrink-0',
          isDone && 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400',
          isError && 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400',
          isRunning && 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
        )}
      >
        {isRunning ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <StageIcon className="w-3.5 h-3.5" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{task.pluginName}</div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{stageLabel}</span>
          {isRunning && (
            <span className="text-xs text-muted-foreground">
              {task.overallProgress}%
            </span>
          )}
        </div>
        {isRunning && (
          <Progress value={task.overallProgress} className="h-1 mt-1" />
        )}
      </div>

      {(isDone || isError) && (
        <Button
          variant="ghost"
          size="icon"
          className="w-6 h-6 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
        >
          <X className="w-3 h-3" />
        </Button>
      )}
    </div>
  );
}

export default function PluginInstallTaskQueue() {
  const { t } = useTranslation();
  const { tasks, setSelectedTaskId, removeTask, clearCompletedTasks } =
    usePluginInstallTasks();

  const runningCount = tasks.filter(
    (t) => t.stage !== InstallStage.DONE && t.stage !== InstallStage.ERROR,
  ).length;
  const hasCompleted = tasks.some(
    (t) => t.stage === InstallStage.DONE || t.stage === InstallStage.ERROR,
  );

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className="relative px-4 py-5 cursor-pointer"
        >
          <ListTodo className="w-4 h-4 mr-2" />
          {t('plugins.installProgress.taskQueue')}
          {runningCount > 0 && (
            <Badge
              variant="default"
              className="ml-2 h-5 min-w-5 px-1.5 text-xs"
            >
              {runningCount}
            </Badge>
          )}
          {runningCount > 0 && (
            <span className="absolute top-1 right-1 flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-primary" />
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[340px] p-2" align="end">
        <div className="flex items-center justify-between px-2 py-1.5 mb-1">
          <span className="text-sm font-semibold">
            {t('plugins.installProgress.taskQueue')}
          </span>
          {hasCompleted && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs px-2"
              onClick={clearCompletedTasks}
            >
              {t('plugins.installProgress.clearCompleted')}
            </Button>
          )}
        </div>
        <div className="max-h-[300px] overflow-y-auto space-y-0.5">
          {tasks.length === 0 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              {t('plugins.installProgress.noTasks')}
            </div>
          ) : (
            tasks.map((task) => (
              <TaskQueueItem
                key={task.id}
                task={task}
                onClick={() => setSelectedTaskId(task.id)}
                onRemove={() => removeTask(task.id)}
              />
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
