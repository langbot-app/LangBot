export const ACTIVE_WORKSPACE_STORAGE_KEY = 'langbot_active_workspace_uuid';
export const PENDING_INVITATION_TOKEN_KEY = 'langbot_pending_invitation_token';

let activeWorkspaceUuid: string | null = null;

function readStoredWorkspaceUuid(): string | null {
  if (typeof window === 'undefined') return null;
  const value = localStorage.getItem(ACTIVE_WORKSPACE_STORAGE_KEY)?.trim();
  return value || null;
}

export function getActiveWorkspaceUuid(): string | null {
  if (activeWorkspaceUuid) return activeWorkspaceUuid;
  activeWorkspaceUuid = readStoredWorkspaceUuid();
  return activeWorkspaceUuid;
}

export function setActiveWorkspaceUuid(workspaceUuid: string): void {
  const normalized = workspaceUuid.trim();
  if (!normalized) {
    throw new Error('Workspace UUID cannot be empty');
  }
  activeWorkspaceUuid = normalized;
  if (typeof window !== 'undefined') {
    localStorage.setItem(ACTIVE_WORKSPACE_STORAGE_KEY, normalized);
  }
}

export function clearActiveWorkspaceUuid(): void {
  activeWorkspaceUuid = null;
  if (typeof window !== 'undefined') {
    localStorage.removeItem(ACTIVE_WORKSPACE_STORAGE_KEY);
  }
}

export function getPendingInvitationToken(): string | null {
  if (typeof window === 'undefined') return null;
  const token = sessionStorage.getItem(PENDING_INVITATION_TOKEN_KEY)?.trim();
  return token || null;
}

export function setPendingInvitationToken(token: string): void {
  const normalized = token.trim();
  if (!normalized) throw new Error('Invitation token cannot be empty');
  if (typeof window !== 'undefined') {
    sessionStorage.setItem(PENDING_INVITATION_TOKEN_KEY, normalized);
  }
}

export function clearPendingInvitationToken(): void {
  if (typeof window !== 'undefined') {
    sessionStorage.removeItem(PENDING_INVITATION_TOKEN_KEY);
  }
}
