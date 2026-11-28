export type PermissionCategory = 'workspace_operations' | 'capabilities';

export type PluginPermissionItem = {
  id: string;
  category: PermissionCategory;
  label?: Record<string, string> | null;
  required_permissions: string[];
  risk: 'read' | 'write' | 'dangerous';
  granted: boolean;
  grantable: boolean;
  domain?: string;
  summary?: string;
};

export type PluginPermissionState = {
  installation_uuid: string;
  can_manage: boolean;
  can_confirm: boolean;
  compatibility_mode: boolean;
  pending_confirmation: boolean;
  enabled: boolean;
  grants: Record<PermissionCategory, string[]>;
  permissions: PluginPermissionItem[];
  domains?: { domain: string; label: Record<string, string> }[];
};

/**
 * Selection a freshly loaded panel starts from: the current grants, plus every
 * grantable permission while the installation awaits confirmation.
 */
export function initialPermissionSelection(state: PluginPermissionState) {
  return new Set(
    state.permissions
      .filter(
        (item) =>
          item.granted ||
          (state.pending_confirmation &&
            (state.compatibility_mode || item.grantable)),
      )
      .map((item) => item.id),
  );
}

/** Permissions the selection adds to, or removes from, the saved grants. */
export function permissionSelectionDiff(
  state: PluginPermissionState,
  selected: Set<string>,
) {
  return {
    added: state.permissions.filter(
      (item) => selected.has(item.id) && !item.granted,
    ),
    removed: state.permissions.filter(
      (item) => !selected.has(item.id) && item.granted,
    ),
  };
}

/**
 * Request body for a grant change. Adding grants needs ``confirm``; the
 * compatibility mode can only be confirmed with every legacy capability.
 */
export function permissionGrantRequest(
  state: PluginPermissionState,
  selected: Set<string>,
  confirm: boolean,
) {
  const grants = (category: PermissionCategory) =>
    state.permissions
      .filter(
        (item) =>
          item.category === category &&
          (confirm
            ? state.compatibility_mode || selected.has(item.id)
            : item.granted && selected.has(item.id)),
      )
      .map((item) => item.id);
  return {
    workspace_operations: grants('workspace_operations'),
    capabilities: grants('capabilities'),
    confirm,
  };
}
