import { BaseHttpClient } from './BaseHttpClient';
import {
  ApiRespProviderRequesters,
  ApiRespProviderRequester,
  ApiRespProviderLLMModels,
  ApiRespProviderLLMModel,
  LLMModel,
  ApiRespPipelines,
  Pipeline,
  ApiRespPlatformAdapters,
  ApiRespPlatformAdapter,
  ApiRespPlatformBots,
  ApiRespPlatformBot,
  Bot,
  ApiRespPlugins,
  ApiRespPlugin,
  ApiRespPluginConfig,
  AsyncTaskCreatedResp,
  ApiRespSystemInfo,
  ApiRespAsyncTasks,
  ApiRespUserToken,
  GetPipelineResponseData,
  GetPipelineMetadataResponseData,
  AsyncTask,
  ApiRespWebChatMessages,
  ApiRespKnowledgeBases,
  ApiRespKnowledgeBase,
  KnowledgeBase,
  ApiRespKnowledgeBaseFiles,
  ApiRespKnowledgeBaseRetrieve,
  ApiRespProviderEmbeddingModels,
  ApiRespProviderEmbeddingModel,
  EmbeddingModel,
  ApiRespPluginSystemStatus,
  ApiRespMCPServers,
  ApiRespMCPServer,
  MCPServer,
  ExternalKnowledgeBase,
  ApiRespExternalKnowledgeBases,
  ApiRespExternalKnowledgeBase,
} from '@/app/infra/entities/api';
import { Plugin } from '@/app/infra/entities/plugin';
import { GetBotLogsRequest } from '@/app/infra/http/requestParam/bots/GetBotLogsRequest';
import { GetBotLogsResponse } from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';

/**
 * 后端服务客户端
 * 负责与后端 API 的所有交互
 */
export class BackendClient extends BaseHttpClient {
  constructor(baseURL: string) {
    super(baseURL, false);
  }

  // ============ Provider API ============
  public getProviderRequesters(
    model_type: string,
  ): Promise<ApiRespProviderRequesters> {
    return this.get('/api/v1/provider/requesters', { type: model_type });
  }

  public getProviderRequester(name: string): Promise<ApiRespProviderRequester> {
    return this.get(`/api/v1/provider/requesters/${name}`);
  }

  public getProviderRequesterIconURL(name: string): string {
    if (this.instance.defaults.baseURL === '/') {
      // 获取用户访问的URL
      const url = window.location.href;
      const baseURL = url.split('/').slice(0, 3).join('/');
      return `${baseURL}/api/v1/provider/requesters/${name}/icon`;
    }
    return (
      this.instance.defaults.baseURL +
      `/api/v1/provider/requesters/${name}/icon`
    );
  }

  // ============ Provider Model LLM ============
  public getProviderLLMModels(): Promise<ApiRespProviderLLMModels> {
    return this.get('/api/v1/provider/models/llm');
  }

  public getProviderLLMModel(uuid: string): Promise<ApiRespProviderLLMModel> {
    return this.get(`/api/v1/provider/models/llm/${uuid}`);
  }

  public createProviderLLMModel(model: LLMModel): Promise<object> {
    return this.post('/api/v1/provider/models/llm', model);
  }

  public deleteProviderLLMModel(uuid: string): Promise<object> {
    return this.delete(`/api/v1/provider/models/llm/${uuid}`);
  }

  public updateProviderLLMModel(
    uuid: string,
    model: LLMModel,
  ): Promise<object> {
    return this.put(`/api/v1/provider/models/llm/${uuid}`, model);
  }

  public testLLMModel(uuid: string, model: LLMModel): Promise<object> {
    return this.post(`/api/v1/provider/models/llm/${uuid}/test`, model);
  }

  // ============ Provider Model Embedding ============
  public getProviderEmbeddingModels(): Promise<ApiRespProviderEmbeddingModels> {
    return this.get('/api/v1/provider/models/embedding');
  }

  public getProviderEmbeddingModel(
    uuid: string,
  ): Promise<ApiRespProviderEmbeddingModel> {
    return this.get(`/api/v1/provider/models/embedding/${uuid}`);
  }

  public createProviderEmbeddingModel(model: EmbeddingModel): Promise<object> {
    return this.post('/api/v1/provider/models/embedding', model);
  }

  public deleteProviderEmbeddingModel(uuid: string): Promise<object> {
    return this.delete(`/api/v1/provider/models/embedding/${uuid}`);
  }

  public updateProviderEmbeddingModel(
    uuid: string,
    model: EmbeddingModel,
  ): Promise<object> {
    return this.put(`/api/v1/provider/models/embedding/${uuid}`, model);
  }

  public testEmbeddingModel(
    uuid: string,
    model: EmbeddingModel,
  ): Promise<object> {
    return this.post(`/api/v1/provider/models/embedding/${uuid}/test`, model);
  }

  // ============ Pipeline API ============
  public getGeneralPipelineMetadata(): Promise<GetPipelineMetadataResponseData> {
    // as designed, this method will be deprecated, and only for developer to check the prefered config schema
    return this.get('/api/v1/pipelines/_/metadata');
  }

  public getPipelines(
    sortBy?: string,
    sortOrder?: string,
  ): Promise<ApiRespPipelines> {
    const params = new URLSearchParams();
    if (sortBy) params.append('sort_by', sortBy);
    if (sortOrder) params.append('sort_order', sortOrder);
    const queryString = params.toString();
    return this.get(`/api/v1/pipelines${queryString ? `?${queryString}` : ''}`);
  }

  public getPipeline(uuid: string): Promise<GetPipelineResponseData> {
    return this.get(`/api/v1/pipelines/${uuid}`);
  }

  public createPipeline(pipeline: Pipeline): Promise<{
    uuid: string;
  }> {
    return this.post('/api/v1/pipelines', pipeline);
  }

  public updatePipeline(uuid: string, pipeline: Pipeline): Promise<object> {
    return this.put(`/api/v1/pipelines/${uuid}`, pipeline);
  }

  public deletePipeline(uuid: string): Promise<object> {
    return this.delete(`/api/v1/pipelines/${uuid}`);
  }

  public getPipelineExtensions(uuid: string): Promise<{
    enable_all_plugins: boolean;
    enable_all_mcp_servers: boolean;
    bound_plugins: Array<{ author: string; name: string }>;
    available_plugins: Plugin[];
    bound_mcp_servers: string[];
    available_mcp_servers: MCPServer[];
  }> {
    return this.get(`/api/v1/pipelines/${uuid}/extensions`);
  }

  public updatePipelineExtensions(
    uuid: string,
    bound_plugins: Array<{ author: string; name: string }>,
    bound_mcp_servers: string[],
    enable_all_plugins: boolean = true,
    enable_all_mcp_servers: boolean = true,
  ): Promise<object> {
    return this.put(`/api/v1/pipelines/${uuid}/extensions`, {
      bound_plugins,
      bound_mcp_servers,
      enable_all_plugins,
      enable_all_mcp_servers,
    });
  }

  // ============ WebSocket Chat API ============
  public getWebSocketHistoryMessages(
    pipelineId: string,
    sessionType: string,
  ): Promise<ApiRespWebChatMessages> {
    return this.get(
      `/api/v1/pipelines/${pipelineId}/ws/messages/${sessionType}`,
    );
  }

  public async uploadWebSocketImage(
    pipelineId: string,
    imageFile: File,
  ): Promise<{ file_key: string }> {
    const formData = new FormData();
    formData.append('file', imageFile);

    return this.postFile(`/api/v1/files/images`, formData);
  }

  public resetWebSocketSession(
    pipelineId: string,
    sessionType: string,
  ): Promise<{ message: string }> {
    return this.post(`/api/v1/pipelines/${pipelineId}/ws/reset/${sessionType}`);
  }

  public getWebSocketConnections(pipelineId: string): Promise<{
    stats: {
      total_connections: number;
      pipelines: number;
      connections_by_pipeline: Record<string, number>;
      connections_by_session_type: Record<string, number>;
    };
    connections: Array<{
      connection_id: string;
      session_type: string;
      created_at: string;
      last_active: string;
      is_active: boolean;
    }>;
  }> {
    return this.get(`/api/v1/pipelines/${pipelineId}/ws/connections`);
  }

  public broadcastWebSocketMessage(
    pipelineId: string,
    message: string,
  ): Promise<{ message: string }> {
    return this.post(`/api/v1/pipelines/${pipelineId}/ws/broadcast`, {
      message,
    });
  }

  // ============ Platform API ============
  public getAdapters(): Promise<ApiRespPlatformAdapters> {
    return this.get('/api/v1/platform/adapters');
  }

  public getAdapter(name: string): Promise<ApiRespPlatformAdapter> {
    return this.get(`/api/v1/platform/adapters/${name}`);
  }

  public getAdapterIconURL(name: string): string {
    if (this.instance.defaults.baseURL === '/') {
      // 获取用户访问的URL
      const url = window.location.href;
      const baseURL = url.split('/').slice(0, 3).join('/');
      return `${baseURL}/api/v1/platform/adapters/${name}/icon`;
    }
    return (
      this.instance.defaults.baseURL + `/api/v1/platform/adapters/${name}/icon`
    );
  }

  // ============ Platform Bots ============
  public getBots(): Promise<ApiRespPlatformBots> {
    return this.get('/api/v1/platform/bots');
  }

  public getBot(uuid: string): Promise<ApiRespPlatformBot> {
    return this.get(`/api/v1/platform/bots/${uuid}`);
  }

  public createBot(bot: Bot): Promise<{ uuid: string }> {
    return this.post('/api/v1/platform/bots', bot);
  }

  public updateBot(uuid: string, bot: Bot): Promise<object> {
    return this.put(`/api/v1/platform/bots/${uuid}`, bot);
  }

  public deleteBot(uuid: string): Promise<object> {
    return this.delete(`/api/v1/platform/bots/${uuid}`);
  }

  public getBotLogs(
    botId: string,
    request: GetBotLogsRequest,
  ): Promise<GetBotLogsResponse> {
    return this.post(`/api/v1/platform/bots/${botId}/logs`, request);
  }

  // ============ File management API ============
  public uploadDocumentFile(file: File): Promise<{ file_id: string }> {
    const formData = new FormData();
    formData.append('file', file);

    return this.request<{ file_id: string }>({
      method: 'post',
      url: '/api/v1/files/documents',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  }

  // ============ Knowledge Base API ============
  public getKnowledgeBases(): Promise<ApiRespKnowledgeBases> {
    return this.get('/api/v1/knowledge/bases');
  }

  public getKnowledgeBase(uuid: string): Promise<ApiRespKnowledgeBase> {
    return this.get(`/api/v1/knowledge/bases/${uuid}`);
  }

  public createKnowledgeBase(base: KnowledgeBase): Promise<{ uuid: string }> {
    return this.post('/api/v1/knowledge/bases', base);
  }

  public updateKnowledgeBase(
    uuid: string,
    base: KnowledgeBase,
  ): Promise<{ uuid: string }> {
    return this.put(`/api/v1/knowledge/bases/${uuid}`, base);
  }

  public uploadKnowledgeBaseFile(
    uuid: string,
    file_id: string,
  ): Promise<object> {
    return this.post(`/api/v1/knowledge/bases/${uuid}/files`, {
      file_id,
    });
  }

  public getKnowledgeBaseFiles(
    uuid: string,
  ): Promise<ApiRespKnowledgeBaseFiles> {
    return this.get(`/api/v1/knowledge/bases/${uuid}/files`);
  }

  public deleteKnowledgeBaseFile(
    uuid: string,
    file_id: string,
  ): Promise<object> {
    return this.delete(`/api/v1/knowledge/bases/${uuid}/files/${file_id}`);
  }

  public deleteKnowledgeBase(uuid: string): Promise<object> {
    return this.delete(`/api/v1/knowledge/bases/${uuid}`);
  }

  public retrieveKnowledgeBase(
    uuid: string,
    query: string,
  ): Promise<ApiRespKnowledgeBaseRetrieve> {
    return this.post(`/api/v1/knowledge/bases/${uuid}/retrieve`, { query });
  }

  // ============ External Knowledge Base API ============
  public getExternalKnowledgeBases(): Promise<ApiRespExternalKnowledgeBases> {
    return this.get('/api/v1/knowledge/external-bases');
  }

  public getExternalKnowledgeBase(
    uuid: string,
  ): Promise<ApiRespExternalKnowledgeBase> {
    return this.get(`/api/v1/knowledge/external-bases/${uuid}`);
  }

  public createExternalKnowledgeBase(
    base: ExternalKnowledgeBase,
  ): Promise<{ uuid: string }> {
    return this.post('/api/v1/knowledge/external-bases', base);
  }

  public updateExternalKnowledgeBase(
    uuid: string,
    base: ExternalKnowledgeBase,
  ): Promise<{ uuid: string }> {
    return this.put(`/api/v1/knowledge/external-bases/${uuid}`, base);
  }

  public deleteExternalKnowledgeBase(uuid: string): Promise<object> {
    return this.delete(`/api/v1/knowledge/external-bases/${uuid}`);
  }

  public retrieveExternalKnowledgeBase(
    uuid: string,
    query: string,
  ): Promise<ApiRespKnowledgeBaseRetrieve> {
    return this.post(`/api/v1/knowledge/external-bases/${uuid}/retrieve`, {
      query,
    });
  }

  public listKnowledgeRetrievers(): Promise<{ retrievers: unknown[] }> {
    return this.get('/api/v1/knowledge/external-bases/retrievers');
  }

  // ============ Plugins API ============
  public getPlugins(): Promise<ApiRespPlugins> {
    return this.get('/api/v1/plugins');
  }

  public getPlugin(author: string, name: string): Promise<ApiRespPlugin> {
    return this.get(`/api/v1/plugins/${author}/${name}`);
  }

  public getPluginConfig(
    author: string,
    name: string,
  ): Promise<ApiRespPluginConfig> {
    return this.get(`/api/v1/plugins/${author}/${name}/config`);
  }

  public updatePluginConfig(
    author: string,
    name: string,
    config: object,
  ): Promise<object> {
    return this.put(`/api/v1/plugins/${author}/${name}/config`, config);
  }

  public uploadPluginConfigFile(file: File): Promise<{ file_key: string }> {
    const formData = new FormData();
    formData.append('file', file);

    return this.request<{ file_key: string }>({
      method: 'post',
      url: '/api/v1/plugins/config-files',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  }

  public deletePluginConfigFile(
    fileKey: string,
  ): Promise<{ deleted: boolean }> {
    return this.delete(`/api/v1/plugins/config-files/${fileKey}`);
  }

  public getPluginReadme(
    author: string,
    name: string,
    language: string = 'en',
  ): Promise<{ readme: string }> {
    return this.get(
      `/api/v1/plugins/${author}/${name}/readme?language=${language}`,
    );
  }

  public getPluginAssetURL(
    author: string,
    name: string,
    filepath: string,
  ): string {
    return (
      this.instance.defaults.baseURL +
      `/api/v1/plugins/${author}/${name}/assets/${filepath}`
    );
  }

  public getPluginIconURL(author: string, name: string): string {
    if (this.instance.defaults.baseURL === '/') {
      const url = window.location.href;
      const baseURL = url.split('/').slice(0, 3).join('/');
      return `${baseURL}/api/v1/plugins/${author}/${name}/icon`;
    }
    return (
      this.instance.defaults.baseURL + `/api/v1/plugins/${author}/${name}/icon`
    );
  }

  public installPluginFromGithub(
    assetUrl: string,
    owner: string,
    repo: string,
    releaseTag: string,
  ): Promise<AsyncTaskCreatedResp> {
    return this.post('/api/v1/plugins/install/github', {
      asset_url: assetUrl,
      owner,
      repo,
      release_tag: releaseTag,
    });
  }

  public getGithubReleases(repoUrl: string): Promise<{
    releases: Array<{
      id: number;
      tag_name: string;
      name: string;
      published_at: string;
      prerelease: boolean;
      draft: boolean;
    }>;
    owner: string;
    repo: string;
  }> {
    return this.post('/api/v1/plugins/github/releases', { repo_url: repoUrl });
  }

  public getGithubReleaseAssets(
    owner: string,
    repo: string,
    releaseId: number,
  ): Promise<{
    assets: Array<{
      id: number;
      name: string;
      size: number;
      download_url: string;
      content_type: string;
    }>;
  }> {
    return this.post('/api/v1/plugins/github/release-assets', {
      owner,
      repo,
      release_id: releaseId,
    });
  }

  public installPluginFromLocal(file: File): Promise<AsyncTaskCreatedResp> {
    const formData = new FormData();
    formData.append('file', file);
    return this.postFile('/api/v1/plugins/install/local', formData);
  }

  public installPluginFromMarketplace(
    author: string,
    name: string,
    version: string,
  ): Promise<AsyncTaskCreatedResp> {
    return this.post('/api/v1/plugins/install/marketplace', {
      plugin_author: author,
      plugin_name: name,
      plugin_version: version,
    });
  }

  public removePlugin(
    author: string,
    name: string,
    deleteData: boolean = false,
  ): Promise<AsyncTaskCreatedResp> {
    return this.delete(
      `/api/v1/plugins/${author}/${name}?delete_data=${deleteData}`,
    );
  }

  public upgradePlugin(
    author: string,
    name: string,
  ): Promise<AsyncTaskCreatedResp> {
    return this.post(`/api/v1/plugins/${author}/${name}/upgrade`);
  }

  // ============ MCP API ============
  public getMCPServers(): Promise<ApiRespMCPServers> {
    return this.get('/api/v1/mcp/servers');
  }

  public getMCPServer(serverName: string): Promise<ApiRespMCPServer> {
    return this.get(`/api/v1/mcp/servers/${serverName}`);
  }

  public createMCPServer(server: MCPServer): Promise<AsyncTaskCreatedResp> {
    return this.post('/api/v1/mcp/servers', server);
  }

  public updateMCPServer(
    serverName: string,
    server: Partial<MCPServer>,
  ): Promise<AsyncTaskCreatedResp> {
    return this.put(`/api/v1/mcp/servers/${serverName}`, server);
  }

  public deleteMCPServer(serverName: string): Promise<AsyncTaskCreatedResp> {
    return this.delete(`/api/v1/mcp/servers/${serverName}`);
  }

  public toggleMCPServer(
    serverName: string,
    target_enabled: boolean,
  ): Promise<AsyncTaskCreatedResp> {
    return this.put(`/api/v1/mcp/servers/${serverName}`, {
      enable: target_enabled,
    });
  }

  public testMCPServer(
    serverName: string,
    serverData: object,
  ): Promise<AsyncTaskCreatedResp> {
    return this.post(`/api/v1/mcp/servers/${serverName}/test`, serverData);
  }

  public installMCPServerFromGithub(
    source: string,
  ): Promise<AsyncTaskCreatedResp> {
    return this.post('/api/v1/mcp/install/github', { source });
  }

  public installMCPServerFromSSE(
    source: object,
  ): Promise<AsyncTaskCreatedResp> {
    return this.post('/api/v1/mcp/servers', { source });
  }

  // ============ System API ============
  public getSystemInfo(): Promise<ApiRespSystemInfo> {
    return this.get('/api/v1/system/info');
  }

  public getAsyncTasks(): Promise<ApiRespAsyncTasks> {
    return this.get('/api/v1/system/tasks');
  }

  public getAsyncTask(id: number): Promise<AsyncTask> {
    return this.get(`/api/v1/system/tasks/${id}`);
  }

  public getPluginSystemStatus(): Promise<ApiRespPluginSystemStatus> {
    return this.get('/api/v1/system/status/plugin-system');
  }

  // ============ User API ============
  public checkIfInited(): Promise<{ initialized: boolean }> {
    return this.get('/api/v1/user/init');
  }

  public initUser(user: string, password: string): Promise<object> {
    return this.post('/api/v1/user/init', { user, password });
  }

  public authUser(user: string, password: string): Promise<ApiRespUserToken> {
    return this.post('/api/v1/user/auth', { user, password });
  }

  public checkUserToken(): Promise<ApiRespUserToken> {
    return this.get('/api/v1/user/check-token');
  }

  public resetPassword(
    user: string,
    recoveryKey: string,
    newPassword: string,
  ): Promise<{ user: string }> {
    return this.post('/api/v1/user/reset-password', {
      user,
      recovery_key: recoveryKey,
      new_password: newPassword,
    });
  }

  public changePassword(
    currentPassword: string,
    newPassword: string,
  ): Promise<{ user: string }> {
    return this.post('/api/v1/user/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }
}
