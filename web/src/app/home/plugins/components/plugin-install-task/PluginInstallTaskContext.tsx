'use client';

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
  EXTRACTING = 'extracting',
  INSTALLING_DEPS = 'installing_deps',
  TESTING = 'testing',
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
  if (lower.includes('extract') || lower.includes('unzip'))
    return InstallStage.EXTRACTING;
  if (lower.includes('dependencies') || lower.includes('requirements'))
    return InstallStage.INSTALLING_DEPS;
  if (
    lower.includes('initializ') ||
    lower.includes('launch') ||
    lower.includes('test')
  )
    return InstallStage.TESTING;
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
    case InstallStage.EXTRACTING:
      return 35;
    case InstallStage.INSTALLING_DEPS:
      return 55;
    case InstallStage.TESTING:
      return 80;
    case InstallStage.DONE:
      return 100;
    case InstallStage.ERROR:
      return 0;
    default:
      return 0;
  }
}

export function PluginInstallTaskProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [tasks, setTasks] = useState<PluginInstallTask[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const intervalRefs = useRef<Map<string, NodeJS.Timeout>>(new Map());

  // Cleanup all intervals on unmount
  useEffect(() => {
    return () => {
      intervalRefs.current.forEach((interval) => clearInterval(interval));
    };
  }, []);

  const pollTask = useCallback(
    (taskKey: string, taskId: number) => {
      const interval = setInterval(() => {
        httpClient
          .getAsyncTask(taskId)
          .then((res: AsyncTask) => {
            const action = res.task_context?.current_action || '';
            const done = res.runtime.done;
            const exception = res.runtime.exception;
            const md = (res.task_context?.metadata ?? {}) as Record<string, unknown>;

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
                  depsDownloadedSize: depsDownloadedSize ?? t.depsDownloadedSize,
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
                    return {
                      ...t,
                      stage: InstallStage.ERROR,
                      error: exception,
                      overallProgress: 0,
                      currentAction: action,
                      ...progressFields,
                    };
                  }

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
    [],
  );

  const addTask = useCallback(
    (params: {
      taskId: number;
      pluginName: string;
      source: 'github' | 'marketplace' | 'local';
      fileSize?: number;
    }) => {
      const taskKey = `${params.source}-${params.taskId}`;
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

      setTasks((prev) => [...prev, newTask]);
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
    setTasks((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clearCompletedTasks = useCallback(() => {
    setTasks((prev) =>
      prev.filter(
        (t) => t.stage !== InstallStage.DONE && t.stage !== InstallStage.ERROR,
      ),
    );
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
      }}
    >
      {children}
    </PluginInstallTaskContext.Provider>
  );
}
