import { BackendClient } from './BackendClient';
import { CloudServiceClient } from './CloudServiceClient';
import { ApiRespSystemInfo } from '@/app/infra/entities/api';

// 系统信息
export let systemInfo: ApiRespSystemInfo = {
  debug: false,
  version: '',
  enable_marketplace: true,
  cloud_service_url: '',
  allow_modify_login_info: true,
  disable_models_service: false,
};

// 用户信息
export let userInfo: {
  user: string;
  account_type: 'local' | 'space';
  has_password: boolean;
} | null = null;

/**
 * 获取基础 URL
 */
const getBaseURL = (): string => {
  if (typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
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
      systemInfo = info;
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
      systemInfo = await backendClient.getSystemInfo();
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
export const initializeSystemInfo = async (): Promise<void> => {
  try {
    systemInfo = await backendClient.getSystemInfo();
    cloudServiceClient.updateBaseURL(systemInfo.cloud_service_url);
  } catch (error) {
    console.error('Failed to initialize system info:', error);
  }
};

/**
 * 初始化用户信息
 * 应该在用户登录后调用此方法
 */
export const initializeUserInfo = async (): Promise<void> => {
  try {
    userInfo = await backendClient.getUserInfo();
  } catch (error) {
    console.error('Failed to initialize user info:', error);
    userInfo = null;
  }
};

/**
 * 清除用户信息
 * 应该在用户登出时调用此方法
 */
export const clearUserInfo = (): void => {
  userInfo = null;
};

// 导出类型，以便其他地方使用
export type { ResponseData, RequestConfig } from './BaseHttpClient';
export { BaseHttpClient } from './BaseHttpClient';
export { BackendClient } from './BackendClient';
export { CloudServiceClient } from './CloudServiceClient';
