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

/**
 * Installation stages mapped from backend current_action strings.
 */
export enum InstallStage {
  DOWNLOADING = 'downloading',
  INSTALLING_DEPS = 'installing_deps',
  INITIALIZING = 'initializing',
  LAUNCHING = 'launching',
  DONE = 'done',
  ERROR = 'error',
}

export interface PluginInstallTask {
  id: string; // unique key: `${source}-${taskId}`
  taskId: number; // backend async task id
  pluginName: string; // display name
  source: 'github' | 'marketplace' | 'local';
  stage: InstallStage;
  overallProgress: number; // 0-100
  fileSize?: number; // bytes, if known
  // Download progress
  downloadCurrent?: number; // bytes downloaded so far
  downloadTotal?: number; // total bytes to download
  downloadSpeed?: number; // bytes per second
  // Dependency progress
  depsTotal?: number; // total dependency count
  depsInstalled?: number; // deps installed so far
  depsRemaining?: number; // remaining
  currentDep?: string; // currently installing dep name
  depsDownloadedSize?: number; // total bytes of downloaded deps
  depsSpeed?: number; // deps download speed bytes/s
  error?: string;
  startedAt: number; // timestamp
  currentAction: string; // raw backend action string
}

type OnTaskCompleteCallback = (
  taskId: number,
  success: boolean,
  error?: string,
) => void;

interface PluginInstallTaskContextValue {
  tasks: PluginInstallTask[];
  addTask: (params: {
    taskId: number;
    pluginName: string;
    source: 'github' | 'marketplace' | 'local';
    fileSize?: number;
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
 * Map backend `current_action` to our InstallStage.
 */
function mapActionToStage(action: string): InstallStage {
  if (!action) return InstallStage.DOWNLOADING;
  const lower = action.toLowerCase();
  if (lower.includes('download')) return InstallStage.DOWNLOADING;
  if (lower.includes('dependencies') || lower.includes('requirements'))
    return InstallStage.INSTALLING_DEPS;
  if (lower.includes('initializ') || lower.includes('setting'))
    return InstallStage.INITIALIZING;
  if (lower.includes('launch')) return InstallStage.LAUNCHING;
  if (lower.includes('installed') || lower.includes('complete'))
    return InstallStage.DONE;
  return InstallStage.DOWNLOADING;
}

/**
 * Get overall progress percentage from a stage.
 */
function stageToProgress(stage: InstallStage): number {
  switch (stage) {
    case InstallStage.DOWNLOADING:
      return 10;
    case InstallStage.INSTALLING_DEPS:
      return 40;
    case InstallStage.INITIALIZING:
      return 70;
    case InstallStage.LAUNCHING:
      return 85;
    case InstallStage.DONE:
      return 100;
    case InstallStage.ERROR:
      return 0;
    default:
      return 0;
  }
}

/**
 * Extract install source from backend task name.
 */
function extractSourceFromName(
  name: string,
): 'github' | 'marketplace' | 'local' {
  if (name.includes('github')) return 'github';
  if (name.includes('marketplace')) return 'marketplace';
  return 'local';
}

/**
 * Check if a backend task name is a plugin install task.
 */
function isPluginInstallTask(name: string): boolean {
  return name.startsWith('plugin-install-');
}

/**
 * Convert a backend AsyncTask to our PluginInstallTask.
 */
function asyncTaskToPluginInstallTask(task: AsyncTask): PluginInstallTask {
  const source = extractSourceFromName(task.name);
  const md = (task.task_context?.metadata ?? {}) as Record<string, unknown>;
  const action = task.task_context?.current_action || '';
  const done = task.runtime.done;
  const exception = task.runtime.exception;

  const num = (v: unknown) => (typeof v === 'number' ? v : undefined);
  const str = (v: unknown) => (typeof v === 'string' ? v : undefined);

  let stage: InstallStage;
  let overallProgress: number;
  let error: string | undefined;

  if (done) {
    if (exception) {
      stage = InstallStage.ERROR;
      overallProgress = 0;
      error = exception;
    } else {
      stage = InstallStage.DONE;
      overallProgress = 100;
    }
  } else {
    stage = mapActionToStage(action);
    overallProgress = Math.min(95, stageToProgress(stage));
  }

  const pluginName = str(md.plugin_name) || task.label || `${source} plugin`;

  return {
    id: `${source}-${task.id}`,
    taskId: task.id,
    pluginName,
    source,
    stage,
    overallProgress,
    downloadCurrent: num(md.download_current),
    downloadTotal: num(md.download_total),
    downloadSpeed: num(md.download_speed),
    depsTotal: num(md.deps_total),
    depsInstalled: num(md.deps_installed),
    depsRemaining: num(md.deps_remaining),
    currentDep: str(md.current_dep),
    depsDownloadedSize: num(md.deps_downloaded_size),
    depsSpeed: num(md.deps_speed),
    error,
    startedAt: Date.now(),
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
    return () => {
      intervalRefs.current.forEach((interval) => {
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
    (taskId: number, success: boolean, error?: string) => {
      if (notifiedTaskIds.current.has(taskId)) return;
      notifiedTaskIds.current.add(taskId);
      onTaskCompleteCallbacks.current.forEach((cb) => {
        cb(taskId, success, error);
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

            // Extract progress fields from metadata
            const num = (v: unknown) => (typeof v === 'number' ? v : undefined);
            const str = (v: unknown) => (typeof v === 'string' ? v : undefined);

            const downloadCurrent = num(md.download_current);
            const downloadTotal = num(md.download_total);
            const downloadSpeed = num(md.download_speed);
            const depsTotal = num(md.deps_total);
            const depsInstalled = num(md.deps_installed);
            const depsRemaining = num(md.deps_remaining);
            const currentDep = str(md.current_dep);
            const depsDownloadedSize = num(md.deps_downloaded_size);
            const depsSpeed = num(md.deps_speed);

            setTasks((prev) =>
              prev.map((t) => {
                if (t.id !== taskKey) return t;

                const progressFields = {
                  downloadCurrent: downloadCurrent ?? t.downloadCurrent,
                  downloadTotal: downloadTotal ?? t.downloadTotal,
                  downloadSpeed: downloadSpeed ?? t.downloadSpeed,
                  depsTotal: depsTotal ?? t.depsTotal,
                  depsInstalled: depsInstalled ?? t.depsInstalled,
                  depsRemaining: depsRemaining ?? t.depsRemaining,
                  currentDep: currentDep ?? t.currentDep,
                  depsDownloadedSize:
                    depsDownloadedSize ?? t.depsDownloadedSize,
                  depsSpeed: depsSpeed ?? t.depsSpeed,
                };

                if (done) {
                  // Stop polling
                  const iv = intervalRefs.current.get(taskKey);
                  if (iv) {
                    clearInterval(iv);
                    intervalRefs.current.delete(taskKey);
                  }

                  if (exception) {
                    notifyTaskComplete(taskId, false, exception);
                    return {
                      ...t,
                      stage: InstallStage.ERROR,
                      error: exception,
                      overallProgress: 0,
                      currentAction: action,
                      ...progressFields,
                    };
                  }

                  notifyTaskComplete(taskId, true);
                  return {
                    ...t,
                    stage: InstallStage.DONE,
                    overallProgress: 100,
                    currentAction: action,
                    ...progressFields,
                  };
                }

                const stage = mapActionToStage(action);
                const baseProgress = stageToProgress(stage);
                // Add small time-based increment within stage
                const elapsed = (Date.now() - t.startedAt) / 1000;
                const withinStageIncrement = Math.min(
                  15,
                  Math.floor(elapsed / 2),
                );
                const progress = Math.min(
                  95,
                  baseProgress + withinStageIncrement,
                );

                return {
                  ...t,
                  stage,
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

  // Initial sync on mount + periodic sync every 3s
  useEffect(() => {
    syncTasksFromBackend();
    syncIntervalRef.current = setInterval(syncTasksFromBackend, 3000);
    return () => {
      if (syncIntervalRef.current) clearInterval(syncIntervalRef.current);
    };
  }, [syncTasksFromBackend]);

  const addTask = useCallback(
    (params: {
      taskId: number;
      pluginName: string;
      source: 'github' | 'marketplace' | 'local';
      fileSize?: number;
    }) => {
      const taskKey = `${params.source}-${params.taskId}`;

      // Remove from dismissed set if re-added
      dismissedTaskIds.current.delete(params.taskId);

      const newTask: PluginInstallTask = {
        id: taskKey,
        taskId: params.taskId,
        pluginName: params.pluginName,
        source: params.source,
        stage: InstallStage.DOWNLOADING,
        overallProgress: 5,
        fileSize: params.fileSize,
        startedAt: Date.now(),
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
