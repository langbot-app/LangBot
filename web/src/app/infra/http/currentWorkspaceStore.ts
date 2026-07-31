import { useSyncExternalStore } from 'react';
import type { CurrentWorkspace } from '@/app/infra/entities/workspace';

let snapshot: CurrentWorkspace | null = null;
const listeners = new Set<() => void>();

export function getCurrentWorkspaceSnapshot(): CurrentWorkspace | null {
  return snapshot;
}

export function setCurrentWorkspaceSnapshot(
  workspace: CurrentWorkspace | null,
): void {
  snapshot = workspace;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** React-safe access to the currently selected Workspace and its permissions. */
export function useCurrentWorkspace(): CurrentWorkspace | null {
  return useSyncExternalStore(
    subscribe,
    getCurrentWorkspaceSnapshot,
    getCurrentWorkspaceSnapshot,
  );
}
