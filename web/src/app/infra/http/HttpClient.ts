/**
 * @deprecated 此文件仅用于向后兼容。请使用新的 client：
 * - import { backendClient } from '@/app/infra/http'
 * - import { getCloudServiceClient } from '@/app/infra/http'
 */

// 重新导出新的客户端实现，保持向后兼容
export {
  backendClient as httpClient,
  systemInfo,
  type ResponseData,
  type RequestConfig,
} from './index';

// 为了兼容性，重新导出 BackendClient 作为 HttpClient
import { BackendClient } from './BackendClient';
export const HttpClient = BackendClient;
