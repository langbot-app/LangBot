import { BackendClient } from './BackendClient';
import { CloudServiceClient } from './CloudServiceClient';
import { ApiRespSystemInfo } from '@/app/infra/entities/api';
import type {
  CurrentWorkspace,
  WorkspaceBootstrapEntry,
} from '@/app/infra/entities/workspace';
import {
  clearActiveWorkspaceUuid,
  getActiveWorkspaceUuid,
  setActiveWorkspaceUuid,
} from './workspaceContext';
import {
  getCurrentWorkspaceSnapshot,
  setCurrentWorkspaceSnapshot,
} from './currentWorkspaceStore';
import {
  clearWorkspaceBootstrapSnapshot,
  getWorkspaceBootstrapSnapshot,
  setWorkspaceBootstrapSnapshot,
} from './workspaceBootstrapStore';

// 系统信息
export const systemInfo: ApiRespSystemInfo = {
  debug: false,
  version: '',
  edition: 'community',
  mcp_stdio_enabled: false,
  enable_marketplace: true,
  cloud_service_url: '',
  allow_modify_login_info: true,
  disable_models_service: false,
  limitation: {
    max_bots: -1,
    max_pipelines: -1,
    max_extensions: -1,
  },
  outbound_ips: [],
  wizard_status: 'none',
  wizard_progress: null,
};

// 用户信息
export let userInfo: {
  account_uuid: string;
  user: string;
  account_type: 'local' | 'space';
  has_password: boolean;
} | null = null;

/**
 * 获取基础 URL
 */
const getBaseURL = (): string => {
  if (typeof window !== 'undefined' && import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  return '/';
};

// 创建后端客户端实例
export const backendClient = new BackendClient(getBaseURL());
// 为了兼容性，也导出为 httpClient
export const httpClient = backendClient;

// 创建云服务客户端实例（初始化时使用默认 URL）
export const cloudServiceClient = new CloudServiceClient(
  'https://space.langbot.app',
);

// 应用启动时自动初始化系统信息
if (typeof window !== 'undefined' && systemInfo.cloud_service_url === '') {
  backendClient
    .getSystemInfo()
    .then((info) => {
      Object.assign(systemInfo, info);
      cloudServiceClient.updateBaseURL(info.cloud_service_url);
    })
    .catch((error) => {
      console.error('Failed to initialize system info on startup:', error);
    });
}

/**
 * 获取云服务客户端
 * 如果 cloud service URL 尚未初始化，会自动从后端获取
 */
export const getCloudServiceClient = async (): Promise<CloudServiceClient> => {
  if (systemInfo.cloud_service_url === '') {
    try {
      Object.assign(systemInfo, await backendClient.getSystemInfo());
      // 更新 cloud service client 的 baseURL
      cloudServiceClient.updateBaseURL(systemInfo.cloud_service_url);
    } catch (error) {
      console.error('Failed to get system info:', error);
      // 如果获取失败，继续使用默认 URL
    }
  }
  return cloudServiceClient;
};

/**
 * 获取云服务客户端（同步版本）
 * 注意：如果 cloud service URL 尚未初始化，将使用默认 URL
 */
export const getCloudServiceClientSync = (): CloudServiceClient => {
  return cloudServiceClient;
};

/**
 * 手动初始化系统信息
 * 可以在应用启动时调用此方法预先获取系统信息
 */
export const initializeSystemInfo = async (options?: {
  throwOnError?: boolean;
}): Promise<void> => {
  try {
    Object.assign(systemInfo, await backendClient.getSystemInfo());
    cloudServiceClient.updateBaseURL(systemInfo.cloud_service_url);
  } catch (error) {
    console.error('Failed to initialize system info:', error);
    if (options?.throwOnError) {
      throw error;
    }
  }
};

/**
 * 初始化用户信息
 * 应该在用户登录后调用此方法
 */
export const initializeUserInfo = async (options?: {
  throwOnError?: boolean;
}): Promise<void> => {
  try {
    userInfo = await backendClient.getUserInfo();
    if (typeof window !== 'undefined') {
      localStorage.setItem('userEmail', userInfo.user);
    }
  } catch (error) {
    console.error('Failed to initialize user info:', error);
    userInfo = null;
    if (options?.throwOnError) {
      throw error;
    }
  }
};

export const initializeWorkspaceInfo = async (): Promise<void> => {
  const storedWorkspaceUuid = getActiveWorkspaceUuid();
  try {
    const workspace = await backendClient.getCurrentWorkspace();
    setCurrentWorkspaceSnapshot(workspace);
    setActiveWorkspaceUuid(workspace.workspace.uuid);
  } catch (error) {
    setCurrentWorkspaceSnapshot(null);
    clearActiveWorkspaceUuid();
    // A restored Community browser session can outlive a database reset or an
    // instance replacement. Its stale selector is not an authorization
    // credential, and the OSS policy still has exactly one legal Workspace,
    // so retry once without it. Cloud must remain explicit and fail closed.
    if (storedWorkspaceUuid && systemInfo.edition === 'community') {
      const workspace = await backendClient.getCurrentWorkspace();
      setCurrentWorkspaceSnapshot(workspace);
      setActiveWorkspaceUuid(workspace.workspace.uuid);
      return;
    }
    throw error;
  }
};

export type WorkspaceBootstrapResult =
  | {
      status: 'ready';
      workspace: CurrentWorkspace;
      workspaces: WorkspaceBootstrapEntry[];
    }
  | {
      status: 'selection-required';
      workspaces: WorkspaceBootstrapEntry[];
    }
  | {
      status: 'unavailable';
      workspaces: [];
    };

export interface WorkspaceBootstrapOptions {
  /** Discard any selector left by a previous Account session. */
  resetSelection?: boolean;
  /** Explicit intent, such as accepting an invitation. */
  preferredWorkspaceUuid?: string;
  /** Always show the chooser when the Account has multiple Workspaces. */
  requireExplicitSelection?: boolean;
}

function clearWorkspaceSelection(): void {
  setCurrentWorkspaceSnapshot(null);
  clearActiveWorkspaceUuid();
}

/**
 * Store a new Account token without carrying Workspace state across Accounts.
 * Call bootstrapWorkspaceSession immediately afterwards.
 */
export function beginAuthenticatedSession(
  token: string,
  userEmail?: string,
): void {
  userInfo = null;
  clearWorkspaceSelection();
  clearWorkspaceBootstrapSnapshot();

  if (typeof window === 'undefined') return;
  localStorage.removeItem('token');
  localStorage.removeItem('userEmail');
  localStorage.setItem('token', token);
  if (userEmail) localStorage.setItem('userEmail', userEmail);
}

async function initializeSelectedWorkspace(
  workspaceUuid: string,
  workspaces: WorkspaceBootstrapEntry[],
): Promise<WorkspaceBootstrapResult> {
  setActiveWorkspaceUuid(workspaceUuid);
  try {
    await Promise.all([
      initializeUserInfo({ throwOnError: true }),
      initializeWorkspaceInfo(),
    ]);
  } catch (error) {
    clearWorkspaceSelection();
    throw error;
  }

  const workspace = getCurrentWorkspaceSnapshot();
  if (!workspace) {
    clearWorkspaceSelection();
    throw new Error('Selected Workspace could not be initialized');
  }
  return { status: 'ready', workspace, workspaces };
}

/**
 * Resolve Account membership before any Workspace-scoped request is made.
 * A singleton is selected automatically; multiple Workspaces require explicit
 * user intent unless a still-valid selector already exists.
 */
export async function bootstrapWorkspaceSession(
  options: WorkspaceBootstrapOptions = {},
): Promise<WorkspaceBootstrapResult> {
  if (options.resetSelection) {
    clearWorkspaceSelection();
    clearWorkspaceBootstrapSnapshot();
  }

  const response = await backendClient.getWorkspaceBootstrap();
  const workspaces = response.workspaces;
  setWorkspaceBootstrapSnapshot(workspaces);

  if (workspaces.length === 0) {
    clearWorkspaceSelection();
    return { status: 'unavailable', workspaces: [] };
  }

  const preferredWorkspace = options.preferredWorkspaceUuid
    ? workspaces.find(
        (entry) => entry.workspace.uuid === options.preferredWorkspaceUuid,
      )
    : undefined;
  if (options.preferredWorkspaceUuid && !preferredWorkspace) {
    clearWorkspaceSelection();
    return { status: 'selection-required', workspaces };
  }

  const activeWorkspace = !options.requireExplicitSelection
    ? workspaces.find(
        (entry) => entry.workspace.uuid === getActiveWorkspaceUuid(),
      )
    : undefined;
  const selectedWorkspace =
    preferredWorkspace ??
    (workspaces.length === 1 ? workspaces[0] : activeWorkspace);

  if (!selectedWorkspace) {
    clearWorkspaceSelection();
    return { status: 'selection-required', workspaces };
  }

  return initializeSelectedWorkspace(
    selectedWorkspace.workspace.uuid,
    workspaces,
  );
}

/** Revalidate and activate an explicit choice made on the chooser page. */
export async function selectWorkspace(
  workspaceUuid: string,
): Promise<WorkspaceBootstrapResult> {
  const response = await backendClient.getWorkspaceBootstrap();
  setWorkspaceBootstrapSnapshot(response.workspaces);
  const selected = response.workspaces.find(
    (entry) => entry.workspace.uuid === workspaceUuid,
  );
  if (!selected) {
    clearWorkspaceSelection();
    if (response.workspaces.length === 0) {
      return { status: 'unavailable', workspaces: [] };
    }
    return { status: 'selection-required', workspaces: response.workspaces };
  }
  return initializeSelectedWorkspace(
    selected.workspace.uuid,
    response.workspaces,
  );
}

/** Clear in-memory Workspace snapshots before reloading into a new scope. */
export function switchWorkspaceAndReload(workspaceUuid: string): void {
  const isAvailable = getWorkspaceBootstrapSnapshot().some(
    (entry) => entry.workspace.uuid === workspaceUuid,
  );
  if (!isAvailable || workspaceUuid === getActiveWorkspaceUuid()) return;

  clearWorkspaceSelection();
  clearWorkspaceBootstrapSnapshot();
  setActiveWorkspaceUuid(workspaceUuid);
  window.location.replace('/home/monitoring');
}

/**
 * 清除用户信息
 * 应该在用户登出时调用此方法
 */
export const clearUserInfo = (): void => {
  userInfo = null;
  clearWorkspaceSelection();
  clearWorkspaceBootstrapSnapshot();
};

export {
  clearActiveWorkspaceUuid,
  clearPendingInvitationToken,
  getActiveWorkspaceUuid,
  getPendingInvitationToken,
  setActiveWorkspaceUuid,
  setPendingInvitationToken,
} from './workspaceContext';

// 导出类型，以便其他地方使用
export type { ResponseData, RequestConfig } from './BaseHttpClient';
export { BaseHttpClient } from './BaseHttpClient';
export { BackendClient } from './BackendClient';
export { CloudServiceClient } from './CloudServiceClient';
export {
  getCurrentWorkspaceSnapshot,
  useCurrentWorkspace,
} from './currentWorkspaceStore';
export {
  getWorkspaceBootstrapSnapshot,
  useWorkspaceBootstrap,
} from './workspaceBootstrapStore';
