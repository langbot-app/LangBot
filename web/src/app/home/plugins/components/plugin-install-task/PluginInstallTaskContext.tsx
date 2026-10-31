import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
} from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { AsyncTask } from '@/app/infra/entities/api';
import {
  InstallStage,
  INSTALL_PROGRESS_CAP,
  computeStageProgress,
  mapActionToStage,
} from './install-progress';

export { InstallStage } from './install-progress';

export type PluginTaskOperation = 'install' | 'upgrade';

export interface PluginInstallTask {
  id: string; // unique key: `${source}-${taskId}`
  taskId: number; // backend async task id
  pluginName: string; // display name
  source: 'github' | 'marketplace' | 'local';
  operation: PluginTaskOperation;
  stage: InstallStage;
  failedStage?: InstallStage;
  overallProgress: number; // 0-100
  extensionType: 'plugin' | 'mcp' | 'skill'; // type of extension being installed
  fileSize?: number; // bytes, if known
  // Download progress
  downloadCurrent?: number; // bytes downloaded so far
  downloadTotal?: number; // total bytes to download
  downloadSpeed?: number; // bytes per second
  error?: string;
  startedAt: number; // timestamp
  /** When the current stage began, used to bound in-stage drift. */
  stageStartedAt: number;
  currentAction: string; // raw backend action string
}

type OnTaskCompleteCallback = (
  taskId: number,
  success: boolean,
  error?: string,
  operation?: PluginTaskOperation,
) => void;

interface PluginInstallTaskContextValue {
  tasks: PluginInstallTask[];
  addTask: (params: {
    taskId: number;
    pluginName: string;
    source: 'github' | 'marketplace' | 'local';
    extensionType: 'plugin' | 'mcp' | 'skill';
    fileSize?: number;
    operation?: PluginTaskOperation;
  }) => void;
  removeTask: (id: string) => void;
  clearCompletedTasks: () => void;
  selectedTaskId: string | null;
  setSelectedTaskId: (id: string | null) => void;
  /** Register a callback for when a task completes (for toast/refresh). Cleared on unmount. */
  registerOnTaskComplete: (cb: OnTaskCompleteCallback) => void;
  unregisterOnTaskComplete: (cb: OnTaskCompleteCallback) => void;
}

const PluginInstallTaskContext =
  createContext<PluginInstallTaskContextValue | null>(null);

export function usePluginInstallTasks() {
  const ctx = useContext(PluginInstallTaskContext);
  if (!ctx) {
    throw new Error(
      'usePluginInstallTasks must be used within PluginInstallTaskProvider',
    );
  }
  return ctx;
}

/**
 * Extract install source from backend task name.
 */
function extractSourceFromName(
  name: string,
): 'github' | 'marketplace' | 'local' {
  if (name.includes('github')) return 'github';
  if (name.includes('marketplace')) return 'marketplace';
  if (name.startsWith('plugin-upgrade-')) return 'marketplace';
  return 'local';
}

export function pluginTaskKey(
  taskId: number,
  source: 'github' | 'marketplace' | 'local',
  operation: PluginTaskOperation = 'install',
) {
  return operation === 'upgrade'
    ? `upgrade-${source}-${taskId}`
    : `${source}-${taskId}`;
}

/**
 * Check if a backend task name is a plugin install task.
 */
function isPluginInstallTask(name: string): boolean {
  return (
    name.startsWith('plugin-install-') ||
    name.startsWith('plugin-upgrade-') ||
    name.startsWith('mcp-install-') ||
    name.startsWith('skill-install-')
  );
}

/**
 * Convert a backend AsyncTask to our PluginInstallTask.
 */
export function asyncTaskToPluginInstallTask(
  task: AsyncTask,
): PluginInstallTask {
  const source = extractSourceFromName(task.name);
  const md = (task.task_context?.metadata ?? {}) as Record<string, unknown>;
  const action = task.task_context?.current_action || '';
  const operation: PluginTaskOperation =
    md.operation === 'upgrade' || task.name.startsWith('plugin-upgrade-')
      ? 'upgrade'
      : 'install';
  const done = task.runtime.done;
  const exception = task.runtime.exception;

  const num = (v: unknown) => (typeof v === 'number' ? v : undefined);
  const str = (v: unknown) => (typeof v === 'string' ? v : undefined);

  let stage: InstallStage;
  let overallProgress: number;
  let error: string | undefined;
  let failedStage: InstallStage | undefined;

  if (done) {
    if (exception) {
      stage = InstallStage.ERROR;
      failedStage = mapActionToStage(action);
      overallProgress = computeStageProgress({
        stage: failedStage,
        stageElapsedSeconds: 0,
      });
      error = exception;
    } else {
      stage = InstallStage.DONE;
      overallProgress = 100;
    }
  } else {
    stage = mapActionToStage(action);
    overallProgress = Math.min(
      INSTALL_PROGRESS_CAP,
      computeStageProgress({
        stage,
        downloadCurrent: num(md.download_current),
        downloadTotal: num(md.download_total),
        reportedProgress: num(md.progress_percent),
        stageElapsedSeconds: 0,
      }),
    );
  }

  const pluginName = str(md.plugin_name) || task.label || `${source} extension`;

  let extensionType: 'plugin' | 'mcp' | 'skill' = 'plugin';
  if (task.name.startsWith('mcp-install-')) {
    extensionType = 'mcp';
  } else if (task.name.startsWith('skill-install-')) {
    extensionType = 'skill';
  }

  return {
    id: pluginTaskKey(task.id, source, operation),
    taskId: task.id,
    pluginName,
    source,
    operation,
    extensionType,
    stage,
    failedStage,
    overallProgress,
    downloadCurrent: num(md.download_current),
    downloadTotal: num(md.download_total),
    downloadSpeed: num(md.download_speed),
    error,
    startedAt: task.created_at ? task.created_at * 1000 : Date.now(),
    stageStartedAt: Date.now(),
    currentAction: action,
  };
}

export function PluginInstallTaskProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [tasks, setTasks] = useState<PluginInstallTask[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const intervalRefs = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const syncIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const onTaskCompleteCallbacks = useRef<Set<OnTaskCompleteCallback>>(
    new Set(),
  );
  // Track tasks that have already been marked as completed/failed (to avoid duplicate callbacks)
  const notifiedTaskIds = useRef<Set<number>>(new Set());
  // Track task IDs that the user has explicitly dismissed
  const dismissedTaskIds = useRef<Set<number>>(new Set());

  // Cleanup all intervals on unmount
  useEffect(() => {
    const intervals = intervalRefs.current;
    return () => {
      intervals.forEach((interval) => {
        clearInterval(interval);
      });
      if (syncIntervalRef.current) clearInterval(syncIntervalRef.current);
    };
  }, []);

  const registerOnTaskComplete = useCallback((cb: OnTaskCompleteCallback) => {
    onTaskCompleteCallbacks.current.add(cb);
  }, []);

  const unregisterOnTaskComplete = useCallback((cb: OnTaskCompleteCallback) => {
    onTaskCompleteCallbacks.current.delete(cb);
  }, []);

  const notifyTaskComplete = useCallback(
    (
      taskId: number,
      success: boolean,
      error?: string,
      operation?: PluginTaskOperation,
    ) => {
      if (notifiedTaskIds.current.has(taskId)) return;
      notifiedTaskIds.current.add(taskId);
      onTaskCompleteCallbacks.current.forEach((cb) => {
        cb(taskId, success, error, operation);
      });
    },
    [],
  );

  const pollTask = useCallback(
    (taskKey: string, taskId: number) => {
      // Don't start duplicate polling for the same task
      if (intervalRefs.current.has(taskKey)) return;

      const interval = setInterval(() => {
        httpClient
          .getAsyncTask(taskId)
          .then((res: AsyncTask) => {
            const action = res.task_context?.current_action || '';
            const done = res.runtime.done;
            const exception = res.runtime.exception;
            const md = (res.task_context?.metadata ?? {}) as Record<
              string,
              unknown
            >;

            // Download byte counts are the only measurable install progress
            // the backend reports for this task.
            const num = (v: unknown) => (typeof v === 'number' ? v : undefined);

            const downloadCurrent = num(md.download_current);
            const downloadTotal = num(md.download_total);
            const downloadSpeed = num(md.download_speed);

            setTasks((prev) =>
              prev.map((t) => {
                if (t.id !== taskKey) return t;

                const progressFields = {
                  downloadCurrent: downloadCurrent ?? t.downloadCurrent,
                  downloadTotal: downloadTotal ?? t.downloadTotal,
                  downloadSpeed: downloadSpeed ?? t.downloadSpeed,
                };

                if (done) {
                  // Stop polling
                  const iv = intervalRefs.current.get(taskKey);
                  if (iv) {
                    clearInterval(iv);
                    intervalRefs.current.delete(taskKey);
                  }

                  if (exception) {
                    notifyTaskComplete(taskId, false, exception, t.operation);
                    return {
                      ...t,
                      stage: InstallStage.ERROR,
                      failedStage: mapActionToStage(action),
                      error: exception,
                      overallProgress: computeStageProgress({
                        stage: mapActionToStage(action),
                        stageElapsedSeconds: 0,
                      }),
                      currentAction: action,
                      ...progressFields,
                    };
                  }

                  notifyTaskComplete(taskId, true, undefined, t.operation);
                  return {
                    ...t,
                    stage: InstallStage.DONE,
                    overallProgress: 100,
                    currentAction: action,
                    ...progressFields,
                  };
                }

                const stage = mapActionToStage(action);
                // Reset the in-stage clock whenever the reported stage moves
                // so drift reflects time spent in this stage, not the whole
                // installation.
                const stageChanged = stage !== t.stage;
                const stageStartedAt = stageChanged
                  ? Date.now()
                  : t.stageStartedAt;
                const stageProgress = computeStageProgress({
                  stage,
                  downloadCurrent,
                  downloadTotal,
                  reportedProgress: num(md.progress_percent),
                  stageElapsedSeconds: (Date.now() - stageStartedAt) / 1000,
                });
                const progress = Math.min(
                  INSTALL_PROGRESS_CAP,
                  Math.max(t.overallProgress, stageProgress),
                );

                return {
                  ...t,
                  stage,
                  stageStartedAt,
                  overallProgress: progress,
                  currentAction: action,
                  ...progressFields,
                };
              }),
            );
          })
          .catch(() => {
            // Silently ignore polling errors
          });
      }, 1000);

      intervalRefs.current.set(taskKey, interval);
    },
    [notifyTaskComplete],
  );

  /**
   * Fetch all plugin-operation tasks from backend and sync state.
   * This is called on mount and periodically to recover tasks after refresh.
   */
  const syncTasksFromBackend = useCallback(async () => {
    try {
      const resp = await httpClient.getAsyncTasks({ kind: 'plugin-operation' });
      const backendTasks = (resp.tasks || []).filter((t: AsyncTask) =>
        isPluginInstallTask(t.name),
      );

      setTasks((prevTasks) => {
        const existingTaskIds = new Set(prevTasks.map((t) => t.taskId));
        const updatedTasks = [...prevTasks];

        for (const bt of backendTasks) {
          // Skip tasks that the user has dismissed
          if (dismissedTaskIds.current.has(bt.id)) continue;

          if (!existingTaskIds.has(bt.id)) {
            // New task from backend (e.g. after page refresh) — add it
            const newTask = asyncTaskToPluginInstallTask(bt);
            updatedTasks.push(newTask);

            // If not done, start polling for progress
            if (!bt.runtime.done) {
              pollTask(newTask.id, bt.id);
            } else {
              // Mark as already notified so we don't re-trigger toasts for old completed tasks
              notifiedTaskIds.current.add(bt.id);
            }
          } else {
            // Already tracking — if it's done in backend but still active locally, update it
            const idx = updatedTasks.findIndex((t) => t.taskId === bt.id);
            if (idx !== -1) {
              const existing = updatedTasks[idx];
              if (
                bt.runtime.done &&
                existing.stage !== InstallStage.DONE &&
                existing.stage !== InstallStage.ERROR
              ) {
                const converted = asyncTaskToPluginInstallTask(bt);
                converted.startedAt = existing.startedAt;
                converted.pluginName = existing.pluginName;
                converted.fileSize = existing.fileSize;
                converted.extensionType = existing.extensionType;
                updatedTasks[idx] = converted;
              }
            }
          }
        }

        return updatedTasks;
      });
    } catch {
      // Silently ignore sync errors
    }
  }, [pollTask]);

  // Initial sync on mount to recover any orphaned tasks
  const syncOnMountRef = useRef(syncTasksFromBackend);
  syncOnMountRef.current = syncTasksFromBackend;
  useEffect(() => {
    syncOnMountRef.current();
  }, []);

  // Only poll periodically when there are active (non-terminal) tasks
  useEffect(() => {
    const hasActiveTasks = tasks.some(
      (t) => t.stage !== InstallStage.DONE && t.stage !== InstallStage.ERROR,
    );

    if (hasActiveTasks) {
      syncIntervalRef.current = setInterval(syncTasksFromBackend, 3000);
    } else {
      if (syncIntervalRef.current) {
        clearInterval(syncIntervalRef.current);
        syncIntervalRef.current = null;
      }
    }

    return () => {
      if (syncIntervalRef.current) clearInterval(syncIntervalRef.current);
    };
  }, [tasks, syncTasksFromBackend]);

  const addTask = useCallback(
    (params: {
      taskId: number;
      pluginName: string;
      source: 'github' | 'marketplace' | 'local';
      extensionType: 'plugin' | 'mcp' | 'skill';
      fileSize?: number;
      operation?: PluginTaskOperation;
    }) => {
      const operation = params.operation ?? 'install';
      const taskKey = pluginTaskKey(params.taskId, params.source, operation);

      // Remove from dismissed set if re-added
      dismissedTaskIds.current.delete(params.taskId);

      const newTask: PluginInstallTask = {
        id: taskKey,
        taskId: params.taskId,
        pluginName: params.pluginName,
        source: params.source,
        operation,
        extensionType: params.extensionType,
        stage:
          operation === 'upgrade'
            ? InstallStage.CHECKING
            : InstallStage.DOWNLOADING,
        overallProgress: operation === 'upgrade' ? 3 : 5,
        fileSize: params.fileSize,
        startedAt: Date.now(),
        stageStartedAt: Date.now(),
        currentAction: '',
      };

      setTasks((prev) => {
        // Avoid duplicate
        if (prev.some((t) => t.taskId === params.taskId)) return prev;
        return [...prev, newTask];
      });
      pollTask(taskKey, params.taskId);
    },
    [pollTask],
  );

  const removeTask = useCallback((id: string) => {
    const iv = intervalRefs.current.get(id);
    if (iv) {
      clearInterval(iv);
      intervalRefs.current.delete(id);
    }

    setTasks((prev) => {
      const task = prev.find((t) => t.id === id);
      if (task) {
        dismissedTaskIds.current.add(task.taskId);
      }
      return prev.filter((t) => t.id !== id);
    });
  }, []);

  const clearCompletedTasks = useCallback(() => {
    setTasks((prev) => {
      const completed = prev.filter(
        (t) => t.stage === InstallStage.DONE || t.stage === InstallStage.ERROR,
      );
      completed.forEach((t) => {
        dismissedTaskIds.current.add(t.taskId);
      });
      return prev.filter(
        (t) => t.stage !== InstallStage.DONE && t.stage !== InstallStage.ERROR,
      );
    });
  }, []);

  return (
    <PluginInstallTaskContext.Provider
      value={{
        tasks,
        addTask,
        removeTask,
        clearCompletedTasks,
        selectedTaskId,
        setSelectedTaskId,
        registerOnTaskComplete,
        unregisterOnTaskComplete,
      }}
    >
      {children}
    </PluginInstallTaskContext.Provider>
  );
}
