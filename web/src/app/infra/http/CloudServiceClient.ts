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
    component_filter?: string,
    tags_filter?: string[],
  ): Promise<ApiRespMarketplacePlugins> {
    return this.post<ApiRespMarketplacePlugins>(
      '/api/v1/marketplace/plugins/search',
      {
        query,
        page,
        page_size,
        sort_by,
        sort_order,
        component_filter,
        tags_filter,
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
    language?: string,
  ): Promise<{ readme: string }> {
    return this.get<{ readme: string }>(
      `/api/v1/marketplace/plugins/${author}/${pluginName}/resources/README`,
      language ? { language } : undefined,
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

  public getPluginMarketplaceURL(
    cloud_service_url: string,
    author: string,
    name: string,
  ): string {
    return `${cloud_service_url}/market/${author}/${name}`;
  }

  public getLangBotReleases(): Promise<GitHubRelease[]> {
    return this.get<GitHubRelease[]>('/api/v1/dist/info/releases');
  }

  public getAllTags(): Promise<{ tags: PluginTag[] }> {
    return this.get<{ tags: PluginTag[] }>('/api/v1/marketplace/tags');
  }
}

export interface PluginTag {
  tag: string;
  display_name: {
    zh_Hans?: string;
    en_US?: string;
    zh_Hant?: string;
    ja_JP?: string;
  };
}

export interface GitHubRelease {
  tag_name: string;
  name: string;
  body: string;
  html_url: string;
  published_at: string;
  prerelease: boolean;
  draft: boolean;
}
