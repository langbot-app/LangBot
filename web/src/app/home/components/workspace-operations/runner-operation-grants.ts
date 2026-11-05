import type { WorkspaceOperationItem } from '@/app/infra/entities/api';

export function operationsForRunner(
  operations: WorkspaceOperationItem[],
  runnerId: string | undefined,
  installationGrants: Record<string, string[]>,
): WorkspaceOperationItem[] {
  const plugin = runnerId?.startsWith('plugin:')
    ? runnerId.slice('plugin:'.length).split('/').slice(0, 2).join('/')
    : '';
  const granted = new Set(installationGrants[plugin] ?? []);
  return operations.map((operation) => ({
    ...operation,
    grantable: granted.has(operation.id),
  }));
}
