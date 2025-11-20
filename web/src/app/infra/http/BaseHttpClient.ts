import axios, {
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  AxiosError,
} from 'axios';

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

/**
 * 基础 HTTP 客户端类
 * 提供通用的 HTTP 请求方法和拦截器配置
 */
export abstract class BaseHttpClient {
  protected instance: AxiosInstance;
  protected disableToken: boolean = false;
  protected baseURL: string;

  constructor(baseURL: string, disableToken?: boolean) {
    this.baseURL = baseURL;
    this.disableToken = disableToken || false;

    this.instance = axios.create({
      baseURL: baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.initInterceptors();
  }

  // 外部获取baseURL的方法
  public getBaseUrl(): string {
    return this.baseURL;
  }

  // 更新 baseURL
  public updateBaseURL(newBaseURL: string): void {
    this.baseURL = newBaseURL;
    this.instance.defaults.baseURL = newBaseURL;
  }

  // 同步获取Session
  protected getSessionSync(): string | null {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('token');
    }
    return null;
  }

  // 拦截器配置
  protected initInterceptors(): void {
    // 请求拦截
    this.instance.interceptors.request.use(
      async (config) => {
        // 客户端添加认证头
        if (typeof window !== 'undefined' && !this.disableToken) {
          const session = this.getSessionSync();
          if (session) {
            config.headers.Authorization = `Bearer ${session}`;
          }
        }

        return config;
      },
      (error) => Promise.reject(error),
    );

    // 响应拦截
    this.instance.interceptors.response.use(
      (response: AxiosResponse<ResponseData>) => {
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
              if (typeof window !== 'undefined') {
                localStorage.removeItem('token');
                if (!error.request.responseURL.includes('/check-token')) {
                  window.location.href = '/login';
                }
              }
              break;
            case 403:
              console.error('Permission denied:', errMessage);
              break;
            case 500:
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
  protected convertKeysToCamel(obj: JSONValue): JSONValue {
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

  // 错误处理
  protected handleError(error: object): never {
    if (axios.isCancel(error)) {
      throw { code: -2, message: 'Request canceled', data: null };
    }
    throw error;
  }

  // 核心请求方法
  public async request<T = unknown>(config: RequestConfig): Promise<T> {
    try {
      const response = await this.instance.request<ResponseData<T>>(config);
      return response.data.data;
    } catch (error) {
      return this.handleError(error as object);
    }
  }

  // 快捷方法
  public get<T = unknown>(
    url: string,
    params?: object,
    config?: RequestConfig,
  ): Promise<T> {
    return this.request<T>({ method: 'get', url, params, ...config });
  }

  public post<T = unknown>(
    url: string,
    data?: object,
    config?: RequestConfig,
  ): Promise<T> {
    return this.request<T>({ method: 'post', url, data, ...config });
  }

  public put<T = unknown>(
    url: string,
    data?: object,
    config?: RequestConfig,
  ): Promise<T> {
    return this.request<T>({ method: 'put', url, data, ...config });
  }

  public delete<T = unknown>(url: string, config?: RequestConfig): Promise<T> {
    return this.request<T>({ method: 'delete', url, ...config });
  }

  public postFile<T = unknown>(
    url: string,
    formData: FormData,
    config?: RequestConfig,
  ): Promise<T> {
    return this.request<T>({
      method: 'post',
      url,
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      ...config,
    });
  }
}
