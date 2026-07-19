import { useSyncExternalStore } from 'react';

import type { WorkspaceBootstrapEntry } from '@/app/infra/entities/workspace';

let snapshot: WorkspaceBootstrapEntry[] = [];
const listeners = new Set<() => void>();

export function getWorkspaceBootstrapSnapshot(): WorkspaceBootstrapEntry[] {
  return snapshot;
}

export function setWorkspaceBootstrapSnapshot(
  workspaces: WorkspaceBootstrapEntry[],
): void {
  snapshot = workspaces;
  listeners.forEach((listener) => listener());
}

export function clearWorkspaceBootstrapSnapshot(): void {
  setWorkspaceBootstrapSnapshot([]);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** React-safe access to the Account's selectable Workspaces. */
export function useWorkspaceBootstrap(): WorkspaceBootstrapEntry[] {
  return useSyncExternalStore(
    subscribe,
    getWorkspaceBootstrapSnapshot,
    getWorkspaceBootstrapSnapshot,
  );
}
