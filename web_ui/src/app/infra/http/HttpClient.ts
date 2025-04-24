import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios'
import {
    ApiResponse, ApiRespProviderRequesters, ApiRespProviderRequester, ApiRespProviderLLMModels,
    ApiRespProviderLLMModel, LLMModel, ApiRespPipelines, ApiRespPipeline, Pipeline, ApiRespPlatformAdapters,
    ApiRespPlatformAdapter, ApiRespPlatformBots, ApiRespPlatformBot, Bot, ApiRespPlugins, ApiRespPlugin, Plugin,
    ApiRespPluginConfig, PluginReorderElement, AsyncTaskCreatedResp, ApiRespSystemInfo, ApiRespAsyncTasks, AsyncTask,
    ApiRespAsyncTask, ApiRespUserToken
} from '../api/api-types'

type JSONValue = string | number | boolean | JSONObject | JSONArray | null
interface JSONObject { [key: string]: JSONValue }
interface JSONArray extends Array<JSONValue> { }

export interface ResponseData<T = unknown> {
    code: number
    message: string
    data: T
    timestamp: number
}

export interface RequestConfig extends AxiosRequestConfig {
    isSSR?: boolean  // 服务端渲染标识
    retry?: number   // 重试次数
}

class HttpClient {
    private instance: AxiosInstance
    // 暂不需要SSR
    // private ssrInstance: AxiosInstance | null = null

    constructor(baseURL?: string) {
        this.instance = axios.create({
            baseURL: baseURL || this.getBaseUrl(),
            timeout: 15000,
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        })

        this.initInterceptors()
    }

    // 兜底URL，如果使用未配置会走到这里
    private getBaseUrl(): string {
        // NOT IMPLEMENT
        if (typeof window === 'undefined') {
            // 服务端环境
            return ""
        }
        // 客户端环境
        return ""
    }

    // 获取Session
    private async getSession() {
        // NOT IMPLEMENT
        return ""
    }

    // 同步获取Session
    private getSessionSync() {
        // NOT IMPLEMENT
        return ""
    }

    // 拦截器配置
    private initInterceptors() {
        // 请求拦截
        this.instance.interceptors.request.use(
            async (config) => {
                // 服务端请求自动携带 cookie, Langbot暂时用不到SSR相关
                // if (typeof window === 'undefined' && config.isSSR) { }
                const { cookies } = await import('next/headers')
                config.headers.Cookie = cookies().toString()

                // 客户端添加认证头
                if (typeof window !== 'undefined') {
                    // NOT IMPLEMENT 从本地取Session，为空跳转到登陆页
                    // const session = await this.getSession()
                    const session = this.getSessionSync()
                    config.headers.Authorization = `Bearer ${session}`
                }

                return config
            },
            (error) => Promise.reject(error)
        )

        // 响应拦截
        this.instance.interceptors.response.use(
            (response: AxiosResponse<ResponseData>) => {
                // 响应拦截处理写在这里，暂无业务需要

                return response
            },
            (error: AxiosError<ResponseData>) => {
                // 统一错误处理
                if (error.response) {
                    const { status, data } = error.response
                    const errMessage = data?.message || error.message

                    switch (status) {
                        case 401:
                            // 401 处理
                            break
                        case 403:
                            console.error('Permission denied:', errMessage)
                            break
                        case 500:
                            // TODO 弹Toast窗
                            console.error('Server error:', errMessage)
                            break
                    }

                    return Promise.reject({
                        code: data?.code || status,
                        message: errMessage,
                        data: data?.data || null
                    })
                }

                return Promise.reject({
                    code: -1,
                    message: error.message || 'Network Error',
                    data: null
                })
            }
        )
    }


    // 转换下划线为驼峰
    private convertKeysToCamel(obj: JSONValue): JSONValue {
        if (Array.isArray(obj)) {
            return obj.map(v => this.convertKeysToCamel(v))
        } else if (obj !== null && typeof obj === 'object') {
            return Object.keys(obj).reduce((acc, key) => {
                const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
                acc[camelKey] = this.convertKeysToCamel((obj as JSONObject)[key])
                return acc
            }, {} as JSONObject)
        }
        return obj
    }

    // 核心请求方法
    public async request<T = unknown>(config: RequestConfig): Promise<T> {
        try {
            // 这里未来如果需要SSR可以将前面替换为SSR的instance
            const instance = config.isSSR ? this.instance : this.instance
            const response = await instance.request<ResponseData<T>>(config)
            return response.data.data
        } catch (error) {
            return this.handleError(error)
        }
    }

    private handleError(error: any): never {
        if (axios.isCancel(error)) {
            throw { code: -2, message: 'Request canceled', data: null }
        }
        throw error
    }

    // 快捷方法
    public get<T = unknown>(url: string, params?: object, config?: RequestConfig) {
        return this.request<T>({ method: 'get', url, params, ...config })
    }

    public post<T = unknown>(url: string, data?: object, config?: RequestConfig) {
        return this.request<T>({ method: 'post', url, data, ...config })
    }

    public put<T = unknown>(url: string, data?: object, config?: RequestConfig) {
        return this.request<T>({ method: 'put', url, data, ...config })
    }

    public delete<T = unknown>(url: string, config?: RequestConfig) {
        return this.request<T>({ method: 'delete', url, ...config })
    }

    // real api request implementation
    // ============ Provider API ============
    public getProviderRequesters(): Promise<ApiResponse<ApiRespProviderRequesters>> {
        return this.get('/api/v1/provider/requesters')
    }

    public getProviderRequester(name: string): Promise<ApiResponse<ApiRespProviderRequester>> {
        return this.get(`/api/v1/provider/requesters/${name}`)
    }

    public getProviderRequesterIconURL(name: string): string {
        return `/api/v1/provider/requesters/${name}/icon`
    }

    // ============ Provider Model LLM ============
    public getProviderLLMModels(): Promise<ApiResponse<ApiRespProviderLLMModels>> {
        return this.get('/api/v1/provider/models/llm')
    }

    public getProviderLLMModel(uuid: string): Promise<ApiResponse<ApiRespProviderLLMModel>> {
        return this.get(`/api/v1/provider/models/llm/${uuid}`)
    }

    public createProviderLLMModel(model: LLMModel): Promise<ApiResponse<object>> {
        return this.post('/api/v1/provider/models/llm', model)
    }

    public deleteProviderLLMModel(uuid: string): Promise<ApiResponse<object>> {
        return this.delete(`/api/v1/provider/models/llm/${uuid}`)
    }

    // ============ Pipeline API ============
    public getGeneralPipelineMetadata(): Promise<ApiResponse<object>> {  // as designed, this method will be deprecated, and only for developer to check the prefered config schema
        return this.get('/api/v1/pipelines/_/metadata')
    }

    public getPipelines(): Promise<ApiResponse<ApiRespPipelines>> {
        return this.get('/api/v1/pipelines')
    }

    public getPipeline(uuid: string): Promise<ApiResponse<ApiRespPipeline>> {
        return this.get(`/api/v1/pipelines/${uuid}`)
    }

    public createPipeline(pipeline: Pipeline): Promise<ApiResponse<object>> {
        return this.post('/api/v1/pipelines', pipeline)
    }

    public updatePipeline(uuid: string, pipeline: Pipeline): Promise<ApiResponse<object>> {
        return this.put(`/api/v1/pipelines/${uuid}`, pipeline)
    }

    public deletePipeline(uuid: string): Promise<ApiResponse<object>> {
        return this.delete(`/api/v1/pipelines/${uuid}`)
    }

    // ============ Platform API ============
    public getAdapters(): Promise<ApiResponse<ApiRespPlatformAdapters>> {
        return this.get('/api/v1/platform/adapters')
    }

    public getAdapter(name: string): Promise<ApiResponse<ApiRespPlatformAdapter>> {
        return this.get(`/api/v1/platform/adapters/${name}`)
    }

    public getAdapterIconURL(name: string): string {
        return `/api/v1/platform/adapters/${name}/icon`
    }

    // ============ Platform Bots ============
    public getBots(): Promise<ApiResponse<ApiRespPlatformBots>> {
        return this.get('/api/v1/platform/bots')
    }

    public getBot(uuid: string): Promise<ApiResponse<ApiRespPlatformBot>> {
        return this.get(`/api/v1/platform/bots/${uuid}`)
    }

    public createBot(bot: Bot): Promise<ApiResponse<object>> {
        return this.post('/api/v1/platform/bots', bot)
    }

    public updateBot(uuid: string, bot: Bot): Promise<ApiResponse<object>> {
        return this.put(`/api/v1/platform/bots/${uuid}`, bot)
    }

    public deleteBot(uuid: string): Promise<ApiResponse<object>> {
        return this.delete(`/api/v1/platform/bots/${uuid}`)
    }

    // ============ Plugins API ============
    public getPlugins(): Promise<ApiResponse<ApiRespPlugins>> {
        return this.get('/api/v1/plugins')
    }

    public getPlugin(author: string, name: string): Promise<ApiResponse<ApiRespPlugin>> {
        return this.get(`/api/v1/plugins/${author}/${name}`)
    }

    public getPluginConfig(author: string, name: string): Promise<ApiResponse<ApiRespPluginConfig>> {
        return this.get(`/api/v1/plugins/${author}/${name}/config`)
    }

    public updatePluginConfig(author: string, name: string, config: object): Promise<ApiResponse<object>> {
        return this.put(`/api/v1/plugins/${author}/${name}/config`, config)
    }

    public togglePlugin(author: string, name: string, target_enabled: boolean): Promise<ApiResponse<object>> {
        return this.post(`/api/v1/plugins/${author}/${name}/toggle`, { target_enabled })
    }

    public reorderPlugins(plugins: PluginReorderElement[]): Promise<ApiResponse<object>> {
        return this.post('/api/v1/plugins/reorder', plugins)
    }

    public updatePlugin(author: string, name: string): Promise<ApiResponse<AsyncTaskCreatedResp>> {
        return this.post(`/api/v1/plugins/${author}/${name}/update`)
    }

    public installPluginFromGithub(source: string): Promise<ApiResponse<AsyncTaskCreatedResp>> {
        return this.post('/api/v1/plugins/install/github', { source })
    }

    public removePlugin(author: string, name: string): Promise<ApiResponse<AsyncTaskCreatedResp>> {
        return this.delete(`/api/v1/plugins/${author}/${name}`)
    }

    // ============ System API ============
    public getSystemInfo(): Promise<ApiResponse<ApiRespSystemInfo>> {
        return this.get('/api/v1/system/info')
    }

    public getAsyncTasks(): Promise<ApiResponse<ApiRespAsyncTasks>> {
        return this.get('/api/v1/system/tasks')
    }

    public getAsyncTask(id: number): Promise<ApiResponse<ApiRespAsyncTask>> {
        return this.get(`/api/v1/system/tasks/${id}`)
    }

    // ============ User API ============
    public checkIfInited(): Promise<ApiResponse<object>> {
        return this.get('/api/v1/user/init')
    }

    public initUser(user: string, password: string): Promise<ApiResponse<object>> {
        return this.post('/api/v1/user/init', { user, password })
    }

    public authUser(user: string, password: string): Promise<ApiResponse<ApiRespUserToken>> {
        return this.post('/api/v1/user/auth', { user, password })
    }

    public checkUserToken(): Promise<ApiResponse<ApiRespUserToken>> {
        return this.get('/api/v1/user/check-token')
    }
}

export const httpClient = new HttpClient()
