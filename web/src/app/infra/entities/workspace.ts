export type WorkspaceRole =
  'owner' | 'admin' | 'developer' | 'operator' | 'viewer';

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
  current_plan?: {
    subscription_started_at?: number | null;
    name: string;
    revision: number;
    limits: Record<string, number>;
    entitlement_features: Record<string, boolean>;
    monthly_bonus_credits: number;
  } | null;
  workspace: Workspace;
  membership: WorkspaceMembership;
  permissions: string[];
  placement_generation: number;
  /** Signed Cloud display metadata; never used for client-side authorization. */
  plan_name?: string | null;
  limitation?: Record<string, number> | null;
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

export interface E2BConfigInput {
  api_url: string;
  sandbox_url: string;
  api_key?: string;
  template: string;
}

export type WorkspaceLimits = Partial<
  Record<
    | 'timeout_sec'
    | 'idle_ttl_sec'
    | 'max_sessions'
    | 'cpus'
    | 'memory_mb'
    | 'pids_limit'
    | 'workspace_quota_mb',
    number
  >
>;

export interface WorkspaceSandboxSettings {
  limits?: WorkspaceLimits;
  limit_caps?: WorkspaceLimits;
  e2b?: Omit<E2BConfigInput, 'api_key'> & {
    api_key_configured: boolean;
    source: string;
  };
  e2b_configurable?: boolean;
  backend: string | null;
  effective_backend: string | null;
  enabled: boolean;
  backends: {
    name: string;
    available: boolean;
    reason: string | null;
    managed_processes?: boolean;
    template_validated?: boolean;
    template_validation?: string;
    limit_capabilities?: Partial<Record<keyof WorkspaceLimits, boolean>>;
  }[];
}
