import { BaseHttpClient } from './BaseHttpClient';
import {
  ApiRespMarketplacePluginDetail,
  ApiRespMarketplacePlugins,
} from '@/app/infra/entities/api';
import { PluginV4 } from '@/app/infra/entities/plugin';
import { I18nObject } from '@/app/infra/entities/common';

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
    type_filter?: string,
  ): Promise<ApiRespMarketplacePlugins> {
    // Use different endpoints based on type_filter
    if (type_filter === 'mcp') {
      return this.post<{ mcps: PluginV4[]; total: number }>(
        '/api/v1/marketplace/mcps/search',
        {
          query,
          page,
          page_size,
          sort_by,
          sort_order,
          tags_filter,
        },
      ).then((resp) => ({
        plugins: (resp?.mcps || []).map((mcp) => ({
          ...mcp,
          plugin_id: mcp.mcp_id || mcp.plugin_id,
          type: 'mcp' as const,
        })),
        total: resp?.total || 0,
      }));
    } else if (type_filter === 'skill') {
      return this.post<{ skills: PluginV4[]; total: number }>(
        '/api/v1/marketplace/skills/search',
        {
          query,
          page,
          page_size,
          sort_by,
          sort_order,
          tags_filter,
        },
      ).then((resp) => ({
        plugins: (resp?.skills || []).map((skill) => ({
          ...skill,
          plugin_id: skill.skill_id || skill.plugin_id,
          type: 'skill' as const,
        })),
        total: resp?.total || 0,
      }));
    }

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
        type_filter,
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

  public getGitHubRepoInfo(): Promise<GitHubRepoInfo> {
    return this.get<GitHubRepoInfo>('/api/v1/dist/info/repo');
  }

  public getAllTags(): Promise<{ tags: PluginTag[] }> {
    return this.get<{ tags: PluginTag[] }>('/api/v1/marketplace/tags');
  }

  public getRecommendationLists(): Promise<{ lists: RecommendationList[] }> {
    return this.get<{ lists: RecommendationList[] }>(
      '/api/v1/marketplace/recommendation-lists',
    );
  }
}

export interface RecommendationList {
  uuid: string;
  label: I18nObject;
  sort_order: number;
  plugins: PluginV4[];
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

export interface GitHubRepoInfo {
  repo: {
    stargazers_count: number;
    forks_count: number;
    open_issues_count: number;
    [key: string]: unknown;
  };
  contributors: unknown[];
}
