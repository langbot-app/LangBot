export type WorkspaceRole =
  | 'owner'
  | 'admin'
  | 'developer'
  | 'operator'
  | 'viewer';

export interface Workspace {
  uuid: string;
  instance_uuid: string;
  name: string;
  slug: string;
  type: 'personal' | 'team';
  status: 'provisioning' | 'active' | 'suspended' | 'archived' | 'deleted';
  source: 'local' | 'cloud_projection';
}

export interface WorkspaceMembership {
  uuid: string;
  workspace_uuid: string;
  account_uuid: string;
  display_name: string;
  email: string;
  role: WorkspaceRole;
  status: 'active' | 'disabled' | 'removed';
  joined_at: string | null;
  created_at: string;
}

export interface CurrentWorkspace {
  workspace: Workspace;
  membership: WorkspaceMembership;
  permissions: string[];
  placement_generation: number;
  /** Signed Cloud display metadata; never used for client-side authorization. */
  plan_name?: string | null;
}

export interface WorkspaceSpaceBilling {
  credits: number | null;
  owner_space_bound: boolean;
  is_workspace_owner: boolean;
}

/** Account-scoped Workspace entry returned before a Workspace is selected. */
export type WorkspaceBootstrapEntry = CurrentWorkspace;

export interface WorkspaceBootstrapResponse {
  workspaces: WorkspaceBootstrapEntry[];
}

export interface WorkspaceInvitation {
  uuid: string;
  workspace_uuid: string;
  normalized_email: string;
  role: Exclude<WorkspaceRole, 'owner'>;
  status: 'pending' | 'accepted' | 'revoked' | 'expired';
  expires_at: string;
  created_at: string;
}

export type WorkspaceInvitationDeliveryStatus = 'sent' | 'link_only' | 'failed';

export interface WorkspaceInvitationDelivery {
  status: WorkspaceInvitationDeliveryStatus;
  provider: 'resend' | 'smtp' | null;
}
