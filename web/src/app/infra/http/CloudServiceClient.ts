import { BaseHttpClient } from './BaseHttpClient';
import {
  ApiRespMarketplacePluginDetail,
  ApiRespMarketplacePlugins,
} from '@/app/infra/entities/api';

/**
 * 云服务客户端
 * 负责与 cloud service 的所有交互
 */
export class CloudServiceClient extends BaseHttpClient {
  constructor(baseURL: string = '') {
    // cloud service 不需要 token 认证
    super(baseURL, true);
  }

  public getMarketplacePlugins(
    page: number,
    page_size: number,
    sort_by?: string,
    sort_order?: string,
  ): Promise<ApiRespMarketplacePlugins> {
    return this.get<ApiRespMarketplacePlugins>('/api/v1/marketplace/plugins', {
      page,
      page_size,
      sort_by,
      sort_order,
    });
  }

  public searchMarketplacePlugins(
    query: string,
    page: number,
    page_size: number,
    sort_by?: string,
    sort_order?: string,
  ): Promise<ApiRespMarketplacePlugins> {
    return this.post<ApiRespMarketplacePlugins>(
      '/api/v1/marketplace/plugins/search',
      {
        query,
        page,
        page_size,
        sort_by,
        sort_order,
      },
    );
  }

  public getPluginDetail(
    author: string,
    pluginName: string,
  ): Promise<ApiRespMarketplacePluginDetail> {
    return this.get<ApiRespMarketplacePluginDetail>(
      `/api/v1/marketplace/plugins/${author}/${pluginName}`,
    );
  }

  public getPluginREADME(
    author: string,
    pluginName: string,
  ): Promise<{ readme: string }> {
    return this.get<{ readme: string }>(
      `/api/v1/marketplace/plugins/${author}/${pluginName}/resources/README`,
    );
  }

  public getPluginIconURL(author: string, name: string): string {
    return `${this.baseURL}/api/v1/marketplace/plugins/${author}/${name}/resources/icon`;
  }

  public getPluginAssetURL(
    author: string,
    pluginName: string,
    filepath: string,
  ): string {
    return `${this.baseURL}/api/v1/marketplace/plugins/${author}/${pluginName}/resources/assets/${filepath}`;
  }

  public getPluginMarketplaceURL(author: string, name: string): string {
    return `${this.baseURL}/market?author=${author}&plugin=${name}`;
  }
}
