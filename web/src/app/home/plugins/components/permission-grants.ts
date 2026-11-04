export type PermissionCategory = 'workspace_operations' | 'capabilities';

export type PluginPermissionItem = {
  id: string;
  category: PermissionCategory;
  required_permissions: string[];
  risk: 'read' | 'write' | 'dangerous';
  granted: boolean;
  grantable: boolean;
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
};

export function permissionGrantRequest(
  state: PluginPermissionState,
  selected: Set<string>,
  confirm: boolean,
  revoked?: PluginPermissionItem,
) {
  const grants = (category: PermissionCategory) =>
    confirm
      ? state.permissions
          .filter(
            (item) =>
              item.category === category &&
              (state.compatibility_mode || selected.has(item.id)),
          )
          .map((item) => item.id)
      : state.grants[category].filter((id) => id !== revoked?.id);
  return {
    workspace_operations: grants('workspace_operations'),
    capabilities: grants('capabilities'),
    confirm,
  };
}
