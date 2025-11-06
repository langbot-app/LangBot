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
  ApiRespWebChatMessage,
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
    bound_plugins: Array<{ author: string; name: string }>;
    available_plugins: Plugin[];
  }> {
    return this.get(`/api/v1/pipelines/${uuid}/extensions`);
  }

  public updatePipelineExtensions(
    uuid: string,
    bound_plugins: Array<{ author: string; name: string }>,
  ): Promise<object> {
    return this.put(`/api/v1/pipelines/${uuid}/extensions`, {
      bound_plugins,
    });
  }

  // ============ Debug WebChat API ============

  // ============ Debug WebChat API ============
  public sendWebChatMessage(
    sessionType: string,
    messageChain: object[],
    pipelineId: string,
    timeout: number = 15000,
  ): Promise<ApiRespWebChatMessage> {
    return this.post(
      `/api/v1/pipelines/${pipelineId}/chat/send`,
      {
        session_type: sessionType,
        message: messageChain,
      },
      {
        timeout,
      },
    );
  }

  public async sendStreamingWebChatMessage(
    sessionType: string,
    messageChain: object[],
    pipelineId: string,
    onMessage: (data: ApiRespWebChatMessage) => void,
    onComplete: () => void,
    onError: (error: Error) => void,
  ): Promise<void> {
    try {
      // 构造完整的URL，处理相对路径的情况
      let url = `${this.baseURL}/api/v1/pipelines/${pipelineId}/chat/send`;
      if (this.baseURL === '/') {
        // 获取用户访问的完整URL
        const baseURL = window.location.origin;
        url = `${baseURL}/api/v1/pipelines/${pipelineId}/chat/send`;
      }

      // 使用fetch发送流式请求，因为axios在浏览器环境中不直接支持流式响应
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.getSessionSync()}`,
        },
        body: JSON.stringify({
          session_type: sessionType,
          message: messageChain,
          is_stream: true,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('ReadableStream not supported');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // 读取流式响应
      try {
        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            onComplete();
            break;
          }

          // 解码数据
          buffer += decoder.decode(value, { stream: true });

          // 处理完整的JSON对象
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data:')) {
              try {
                const data = JSON.parse(line.slice(5));

                if (data.type === 'end') {
                  // 流传输结束
                  reader.cancel();
                  onComplete();
                  return;
                }
                if (data.type === 'start') {
                  console.log(data.type);
                }

                if (data.message) {
                  // 处理消息数据
                  onMessage(data);
                }
              } catch (error) {
                console.error('Error parsing streaming data:', error);
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    } catch (error) {
      onError(error as Error);
    }
  }

  public getWebChatHistoryMessages(
    pipelineId: string,
    sessionType: string,
  ): Promise<ApiRespWebChatMessages> {
    return this.get(
      `/api/v1/pipelines/${pipelineId}/chat/messages/${sessionType}`,
    );
  }

  public resetWebChatSession(
    pipelineId: string,
    sessionType: string,
  ): Promise<{ message: string }> {
    return this.post(
      `/api/v1/pipelines/${pipelineId}/chat/reset/${sessionType}`,
    );
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
