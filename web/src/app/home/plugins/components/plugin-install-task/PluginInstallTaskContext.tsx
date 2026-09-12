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
  /** Furthest non-terminal stage reached — kept when the task fails so the
   *  UI can still show which phase failed. */
  lastStage?: InstallStage;
  overallProgress: number; // 0-100
  extensionType: 'plugin' | 'mcp' | 'skill'; // type of extension being installed
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
  /** Timestamp when the current stage began; used for smooth creeping. */
  stageStartedAt?: number;
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
    extensionType: 'plugin' | 'mcp' | 'skill';
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
 * Ordered lifecycle stages. Used to enforce forward-only transitions so the
 * progress bar never moves backwards while a task is running.
 */
const STAGE_ORDER: InstallStage[] = [
  InstallStage.DOWNLOADING,
  InstallStage.INSTALLING_DEPS,
  InstallStage.INITIALIZING,
  InstallStage.LAUNCHING,
  InstallStage.DONE,
];

/**
 * Lower bound (%) for each stage. A task's progress is never allowed to drop
 * below the floor of the furthest stage it has already reached.
 */
const STAGE_FLOOR: Record<InstallStage, number> = {
  [InstallStage.DOWNLOADING]: 2,
  [InstallStage.INSTALLING_DEPS]: 55,
  [InstallStage.INITIALIZING]: 85,
  [InstallStage.LAUNCHING]: 94,
  [InstallStage.DONE]: 100,
  [InstallStage.ERROR]: 0,
};

/** Get the lower-bound percentage for a stage. */
function stageFloor(stage: InstallStage): number {
  return STAGE_FLOOR[stage] ?? 0;
}

/** Get the lower bound of the stage that follows the given one. */
function nextStageFloor(stage: InstallStage): number {
  const idx = STAGE_ORDER.indexOf(stage);
  const next = idx >= 0 ? STAGE_ORDER[idx + 1] : undefined;
  return next ? stageFloor(next) : 100;
}

/** Return whichever stage is further along in the lifecycle. */
function maxStage(current: InstallStage, incoming: InstallStage): InstallStage {
  const currentIdx = STAGE_ORDER.indexOf(current);
  const incomingIdx = STAGE_ORDER.indexOf(incoming);
  if (currentIdx === -1) return incoming;
  if (incomingIdx === -1) return current;
  return incomingIdx >= currentIdx ? incoming : current;
}

/**
 * Map backend `current_action` to our InstallStage.
 *
 * Unknown / transitional actions must NOT map back to an earlier stage,
 * otherwise the bar would jump backwards mid-install.
 */
function mapActionToStage(action: string): InstallStage {
  const lower = (action || '').toLowerCase();
  if (!lower) return InstallStage.DOWNLOADING;

  // "preparing"/"resolving" happen before any bytes land on disk.
  if (lower.includes('prepar') || lower.includes('resolv'))
    return InstallStage.DOWNLOADING;

  if (lower.includes('download') && !lower.includes('dependenc'))
    return InstallStage.DOWNLOADING;

  // Activation / readiness tail phase — its own slice of the bar.
  if (
    lower.includes('launch') ||
    lower.includes('start') ||
    lower.includes('wait') ||
    lower.includes('ready') ||
    lower.includes('initializ')
  ) {
    return InstallStage.LAUNCHING;
  }

  // Dependency installation and package finalization.
  if (
    lower.includes('dependenc') ||
    lower.includes('requirements') ||
    lower.includes('parsing') ||
    lower.includes('extract') ||
    lower.includes('inspect') ||
    lower.includes('persist') ||
    lower.includes('stor') ||
    lower.includes('install') ||
    lower.includes('setting')
  ) {
    return InstallStage.INSTALLING_DEPS;
  }

  // Unknown transitional actions belong to the busy middle of the install.
  return InstallStage.INSTALLING_DEPS;
}

/**
 * Time-based creep so the bar keeps moving when no counters exist.
 *
 * Uses an asymptote so the increment decelerates as it approaches the stage
 * ceiling — the bar always feels alive but never overshoots into the next
 * stage's range.
 */
function creep(stageStartedAt: number, span: number): number {
  if (span <= 0) return 0;
  const elapsed = (Date.now() - stageStartedAt) / 1000;
  // Approaching `span` asymptotically: after ~60s we are ~86% of the span.
  const ratio = 1 - Math.exp(-elapsed / 30);
  return span * ratio;
}

/**
 * Compute a progress value for the current stage.
 *
 * Real byte / dependency counters drive the value when available; otherwise
 * the value creeps forward slowly based on elapsed time. Callers are expected
 * to combine the result with the previous value via `Math.max` so it is
 * monotonic.
 */
function computeStageProgress(
  task: PluginInstallTask,
  stage: InstallStage,
): number {
  const floor = stageFloor(stage);
  const ceiling = Math.max(floor, nextStageFloor(stage) - 1);
  // Creep from when this stage began so a stage change restarts the ramp
  // instead of inheriting the previous stage's elapsed time.
  const stageStartedAt = task.stageStartedAt ?? task.startedAt;
  const creepValue = Math.min(
    ceiling,
    floor + creep(stageStartedAt, ceiling - floor),
  );

  if (stage === InstallStage.DOWNLOADING) {
    const total = task.downloadTotal ?? task.fileSize;
    const current = task.downloadCurrent;
    if (total && total > 0 && current != null && current > 0) {
      const ratio = Math.min(1, current / total);
      // Never let a stale counter pull the value below the creep baseline.
      return Math.max(creepValue, floor + (ceiling - floor) * ratio);
    }
    return creepValue;
  }

  if (stage === InstallStage.INSTALLING_DEPS) {
    const total = task.depsTotal;
    const installed = task.depsInstalled;
    if (total && total > 0 && installed != null && installed > 0) {
      const ratio = Math.min(1, installed / total);
      // Leave headroom for the finalize/launch phase that has no counters.
      return Math.max(creepValue, floor + (ceiling - floor) * ratio * 0.9);
    }
    return creepValue;
  }

  return creepValue;
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
  return (
    name.startsWith('plugin-install-') ||
    name.startsWith('mcp-install-') ||
    name.startsWith('skill-install-')
  );
}

/**
 * Convert a backend AsyncTask to our PluginInstallTask.
 *
 * `previous` (when provided) carries monotonic state forward so re-syncing
 * after a refresh or a poll cannot make the progress bar move backwards.
 */
function asyncTaskToPluginInstallTask(
  task: AsyncTask,
  previous?: PluginInstallTask,
): PluginInstallTask {
  const source = extractSourceFromName(task.name);
  const md = (task.task_context?.metadata ?? {}) as Record<string, unknown>;
  const action = task.task_context?.current_action || '';
  const done = task.runtime.done;
  const exception = task.runtime.exception;

  const num = (v: unknown) => (typeof v === 'number' ? v : undefined);
  const str = (v: unknown) => (typeof v === 'string' ? v : undefined);

  const pluginName = str(md.plugin_name) || task.label || `${source} extension`;

  let extensionType: 'plugin' | 'mcp' | 'skill' = 'plugin';
  if (task.name.startsWith('mcp-install-')) {
    extensionType = 'mcp';
  } else if (task.name.startsWith('skill-install-')) {
    extensionType = 'skill';
  }

  // Prefer the task's real creation time so a refresh (or first sync) restores
  // the correct elapsed baseline instead of restarting the ramp from zero.
  const backendStartedAt =
    typeof task.created_at === 'number' && task.created_at > 0
      ? task.created_at * 1000
      : undefined;
  const startedAt = previous?.startedAt ?? backendStartedAt ?? Date.now();
  let stageStartedAt =
    previous?.stageStartedAt ??
    previous?.startedAt ??
    backendStartedAt ??
    startedAt;

  let stage: InstallStage;
  let overallProgress: number;
  let error: string | undefined;

  // Furthest non-terminal stage reached, kept across failures.
  let lastStage = previous?.lastStage ?? previous?.stage;

  if (done) {
    if (exception) {
      // Preserve how far the task got before failing, so the bar shows the
      // failure point instead of jumping back to zero.
      stage = InstallStage.ERROR;
      overallProgress = previous?.overallProgress ?? 0;
      error = exception;
    } else {
      stage = InstallStage.DONE;
      overallProgress = 100;
    }
  } else {
    const incoming = mapActionToStage(action);
    // Forward-only: never move back to an earlier stage than we already reached.
    stage = previous ? maxStage(previous.stage, incoming) : incoming;
    if (!previous || previous.stage !== stage) {
      stageStartedAt = Date.now();
    }
    lastStage = stage;

    const counters: PluginInstallTask = {
      id: `${source}-${task.id}`,
      taskId: task.id,
      pluginName,
      source,
      extensionType,
      stage,
      overallProgress: 0,
      downloadCurrent: num(md.download_current) ?? previous?.downloadCurrent,
      downloadTotal: num(md.download_total) ?? previous?.downloadTotal,
      downloadSpeed: num(md.download_speed) ?? previous?.downloadSpeed,
      depsTotal: num(md.deps_total) ?? previous?.depsTotal,
      depsInstalled: num(md.deps_installed) ?? previous?.depsInstalled,
      depsRemaining: num(md.deps_remaining) ?? previous?.depsRemaining,
      currentDep: str(md.current_dep) ?? previous?.currentDep,
      depsDownloadedSize:
        num(md.deps_downloaded_size) ?? previous?.depsDownloadedSize,
      depsSpeed: num(md.deps_speed) ?? previous?.depsSpeed,
      startedAt,
      stageStartedAt,
      currentAction: action,
    };

    const computed = computeStageProgress(counters, stage);
    overallProgress = Math.max(previous?.overallProgress ?? 0, computed);
    // Keep the bar strictly below 100 until the backend confirms completion.
    overallProgress = Math.round(Math.min(99, overallProgress));
  }

  return {
    id: `${source}-${task.id}`,
    taskId: task.id,
    pluginName,
    source,
    extensionType,
    stage,
    lastStage,
    overallProgress,
    downloadCurrent: num(md.download_current) ?? previous?.downloadCurrent,
    downloadTotal: num(md.download_total) ?? previous?.downloadTotal,
    downloadSpeed: num(md.download_speed) ?? previous?.downloadSpeed,
    depsTotal: num(md.deps_total) ?? previous?.depsTotal,
    depsInstalled: num(md.deps_installed) ?? previous?.depsInstalled,
    depsRemaining: num(md.deps_remaining) ?? previous?.depsRemaining,
    currentDep: str(md.current_dep) ?? previous?.currentDep,
    depsDownloadedSize:
      num(md.deps_downloaded_size) ?? previous?.depsDownloadedSize,
    depsSpeed: num(md.deps_speed) ?? previous?.depsSpeed,
    error,
    startedAt,
    stageStartedAt,
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
                      // Keep the phase that failed for the UI to display.
                      lastStage: t.lastStage ?? t.stage,
                      error: exception,
                      // Show where it failed instead of resetting to 0.
                      overallProgress: t.overallProgress,
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

                // Forward-only stage transition.
                const incoming = mapActionToStage(action);
                const stage = maxStage(t.stage, incoming);
                // Reset the per-stage ramp whenever we enter a new stage.
                const stageAdvanced = stage !== t.stage;

                const next: PluginInstallTask = {
                  ...t,
                  stage,
                  lastStage: stage,
                  stageStartedAt: stageAdvanced
                    ? Date.now()
                    : (t.stageStartedAt ?? t.startedAt),
                  currentAction: action,
                  ...progressFields,
                };
                const computed = computeStageProgress(next, stage);
                // Progress must never move backwards while the task runs.
                const overallProgress = Math.round(
                  Math.min(99, Math.max(t.overallProgress, computed)),
                );
                return { ...next, overallProgress };
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
        const updatedTasks = [...prevTasks];
        // Collect tasks that need polling started after state is committed.
        const toPoll: Array<{ key: string; taskId: number }> = [];

        for (const bt of backendTasks) {
          // Skip tasks that the user has dismissed
          if (dismissedTaskIds.current.has(bt.id)) continue;

          const idx = updatedTasks.findIndex((t) => t.taskId === bt.id);

          if (idx === -1) {
            // New task from backend (e.g. after page refresh) — add it
            const newTask = asyncTaskToPluginInstallTask(bt);
            updatedTasks.push(newTask);

            if (!bt.runtime.done) {
              toPoll.push({ key: newTask.id, taskId: bt.id });
            } else {
              // Mark as already notified so we don't re-trigger toasts for old completed tasks
              notifiedTaskIds.current.add(bt.id);
            }
            continue;
          }

          // Already tracking — merge the backend snapshot into the existing
          // task. Passing `existing` keeps `startedAt`, `pluginName` and
          // progress monotonic so re-syncing never rewinds the bar.
          const existing = updatedTasks[idx];
          const converted = asyncTaskToPluginInstallTask(bt, existing);
          converted.pluginName = existing.pluginName;
          converted.fileSize = existing.fileSize;
          converted.extensionType = existing.extensionType;

          // Never downgrade a terminal task that is already done/failed locally,
          // unless the backend reports it finished as well.
          if (
            (existing.stage === InstallStage.DONE ||
              existing.stage === InstallStage.ERROR) &&
            !bt.runtime.done
          ) {
            continue;
          }

          updatedTasks[idx] = converted;

          if (!bt.runtime.done) {
            toPoll.push({ key: converted.id, taskId: bt.id });
          }
        }

        // Schedule polling outside the state updater.
        queueMicrotask(() => {
          toPoll.forEach(({ key, taskId }) => pollTask(key, taskId));
        });

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
    }) => {
      const taskKey = `${params.source}-${params.taskId}`;

      // Remove from dismissed set if re-added
      dismissedTaskIds.current.delete(params.taskId);

      const startedAt = Date.now();
      const newTask: PluginInstallTask = {
        id: taskKey,
        taskId: params.taskId,
        pluginName: params.pluginName,
        source: params.source,
        extensionType: params.extensionType,
        stage: InstallStage.DOWNLOADING,
        // Start at the downloading floor and creep up from real counters.
        overallProgress: stageFloor(InstallStage.DOWNLOADING),
        fileSize: params.fileSize,
        downloadTotal: params.fileSize,
        startedAt,
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
