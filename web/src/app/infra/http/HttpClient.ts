import axios, {
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  AxiosError,
} from 'axios';
import {
  ApiRespProviderRequesters,
  ApiRespProviderRequester,
  ApiRespProviderLLMModels,
  ApiRespProviderLLMModel,
  LLMModel,
  ApiRespProviderEmbeddingModels,
  ApiRespProviderEmbeddingModel,
  EmbeddingModel,
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
  PluginReorderElement,
  AsyncTaskCreatedResp,
  ApiRespSystemInfo,
  ApiRespAsyncTasks,
  ApiRespUserToken,
  MarketPluginResponse,
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
} from '@/app/infra/entities/api';
import { GetBotLogsRequest } from '@/app/infra/http/requestParam/bots/GetBotLogsRequest';
import { GetBotLogsResponse } from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';

type JSONValue = string | number | boolean | JSONObject | JSONArray | null;
interface JSONObject {
  [key: string]: JSONValue;
}
type JSONArray = Array<JSONValue>;

export interface ResponseData<T = unknown> {
  code: number;
  message: string;
  data: T;
  timestamp: number;
}

export interface RequestConfig extends AxiosRequestConfig {
  isSSR?: boolean; // 服务端渲染标识
  retry?: number; // 重试次数
}

export let systemInfo: ApiRespSystemInfo | null = null;

class HttpClient {
  private instance: AxiosInstance;
  private disableToken: boolean = false;
  private baseURL: string;
  // 暂不需要SSR
  // private ssrInstance: AxiosInstance | null = null

  constructor(baseURL: string, disableToken?: boolean) {
    this.baseURL = baseURL;
    this.instance = axios.create({
      baseURL: baseURL,
      timeout: 15000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
    this.disableToken = disableToken || false;
    this.initInterceptors();

    if (systemInfo === null && baseURL != 'https://space.langbot.app') {
      this.getSystemInfo().then((res) => {
        systemInfo = res;
      });
    }
  }

  // 外部获取baseURL的方法
  getBaseUrl(): string {
    return this.baseURL;
  }

  // 获取Session
  private async getSession() {
    // NOT IMPLEMENT
    return '';
  }

  // 同步获取Session
  private getSessionSync() {
    // NOT IMPLEMENT
    return localStorage.getItem('token');
  }

  // 拦截器配置
  private initInterceptors() {
    // 请求拦截
    this.instance.interceptors.request.use(
      async (config) => {
        // 服务端请求自动携带 cookie, Langbot暂时用不到SSR相关
        // if (typeof window === 'undefined' && config.isSSR) { }
        // cookie not required
        // const { cookies } = await import('next/headers')
        // config.headers.Cookie = cookies().toString()

        // 客户端添加认证头
        if (typeof window !== 'undefined' && !this.disableToken) {
          const session = this.getSessionSync();
          config.headers.Authorization = `Bearer ${session}`;
        }

        return config;
      },
      (error) => Promise.reject(error),
    );

    // 响应拦截
    this.instance.interceptors.response.use(
      (response: AxiosResponse<ResponseData>) => {
        // 响应拦截处理写在这里，暂无业务需要

        return response;
      },
      (error: AxiosError<ResponseData>) => {
        // 统一错误处理
        if (error.response) {
          const { status, data } = error.response;
          const errMessage = data?.message || error.message;

          switch (status) {
            case 401:
              console.log('401 error: ', errMessage, error.request);
              console.log('responseURL', error.request.responseURL);
              localStorage.removeItem('token');
              if (!error.request.responseURL.includes('/check-token')) {
                window.location.href = '/login';
              }
              break;
            case 403:
              console.error('Permission denied:', errMessage);
              break;
            case 500:
              // NOTE: move to component layer for customized message?
              // toast.error(errMessage);
              console.error('Server error:', errMessage);
              break;
          }

          return Promise.reject({
            code: data?.code || status,
            message: errMessage,
            data: data?.data || null,
          });
        }

        return Promise.reject({
          code: -1,
          message: error.message || 'Network Error',
          data: null,
        });
      },
    );
  }

  // 转换下划线为驼峰
  private convertKeysToCamel(obj: JSONValue): JSONValue {
    if (Array.isArray(obj)) {
      return obj.map((v) => this.convertKeysToCamel(v));
    } else if (obj !== null && typeof obj === 'object') {
      return Object.keys(obj).reduce((acc, key) => {
        const camelKey = key.replace(/_([a-z])/g, (_, letter) =>
          letter.toUpperCase(),
        );
        acc[camelKey] = this.convertKeysToCamel((obj as JSONObject)[key]);
        return acc;
      }, {} as JSONObject);
    }
    return obj;
  }

  // 核心请求方法
  public async request<T = unknown>(config: RequestConfig): Promise<T> {
    try {
      // 这里未来如果需要SSR可以将前面替换为SSR的instance
      const instance = config.isSSR ? this.instance : this.instance;
      const response = await instance.request<ResponseData<T>>(config);
      return response.data.data;
    } catch (error) {
      return this.handleError(error as object);
    }
  }

  private handleError(error: object): never {
    if (axios.isCancel(error)) {
      throw { code: -2, message: 'Request canceled', data: null };
    }
    throw error;
  }

  // 快捷方法
  public get<T = unknown>(
    url: string,
    params?: object,
    config?: RequestConfig,
  ) {
    return this.request<T>({ method: 'get', url, params, ...config });
  }

  public post<T = unknown>(url: string, data?: object, config?: RequestConfig) {
    return this.request<T>({ method: 'post', url, data, ...config });
  }

  public put<T = unknown>(url: string, data?: object, config?: RequestConfig) {
    return this.request<T>({ method: 'put', url, data, ...config });
  }

  public delete<T = unknown>(url: string, config?: RequestConfig) {
    return this.request<T>({ method: 'delete', url, ...config });
  }

  // real api request implementation
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

  public togglePlugin(
    author: string,
    name: string,
    target_enabled: boolean,
  ): Promise<object> {
    return this.put(`/api/v1/plugins/${author}/${name}/toggle`, {
      target_enabled,
    });
  }

  public reorderPlugins(plugins: PluginReorderElement[]): Promise<object> {
    return this.put('/api/v1/plugins/reorder', { plugins });
  }

  public updatePlugin(
    author: string,
    name: string,
  ): Promise<AsyncTaskCreatedResp> {
    return this.post(`/api/v1/plugins/${author}/${name}/update`);
  }

  public getMarketPlugins(
    page: number,
    page_size: number,
    query: string,
    sort_by: string = 'stars',
    sort_order: string = 'DESC',
  ): Promise<MarketPluginResponse> {
    return this.post(`/api/v1/market/plugins`, {
      page,
      page_size,
      query,
      sort_by,
      sort_order,
    });
  }

  public installPluginFromGithub(
    source: string,
  ): Promise<AsyncTaskCreatedResp> {
    return this.post('/api/v1/plugins/install/github', { source });
  }

  public removePlugin(
    author: string,
    name: string,
  ): Promise<AsyncTaskCreatedResp> {
    return this.delete(`/api/v1/plugins/${author}/${name}`);
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
}

const getBaseURL = (): string => {
  if (typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }

  return '/';
};

export const httpClient = new HttpClient(getBaseURL());

// 临时写法，未来两种Client都继承自HttpClient父类，不允许共享方法
export const spaceClient = new HttpClient('https://space.langbot.app');
