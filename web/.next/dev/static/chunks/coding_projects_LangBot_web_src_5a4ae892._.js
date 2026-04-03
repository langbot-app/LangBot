(globalThis.TURBOPACK || (globalThis.TURBOPACK = [])).push([typeof document === "object" ? document.currentScript : undefined,
"[project]/coding/projects/LangBot/web/src/app/infra/http/BaseHttpClient.ts [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "BaseHttpClient",
    ()=>BaseHttpClient
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$axios$2f$lib$2f$axios$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/axios/lib/axios.js [app-client] (ecmascript)");
;
class BaseHttpClient {
    instance;
    disableToken = false;
    baseURL;
    constructor(baseURL, disableToken){
        this.baseURL = baseURL;
        this.disableToken = disableToken || false;
        this.instance = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$axios$2f$lib$2f$axios$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].create({
            baseURL: baseURL,
            timeout: 30000,
            headers: {
                'Content-Type': 'application/json'
            }
        });
        this.initInterceptors();
    }
    // 外部获取baseURL的方法
    getBaseUrl() {
        return this.baseURL;
    }
    // 更新 baseURL
    updateBaseURL(newBaseURL) {
        this.baseURL = newBaseURL;
        this.instance.defaults.baseURL = newBaseURL;
    }
    // 同步获取Session
    getSessionSync() {
        if ("TURBOPACK compile-time truthy", 1) {
            return localStorage.getItem('token');
        }
        //TURBOPACK unreachable
        ;
    }
    // 拦截器配置
    initInterceptors() {
        // 请求拦截
        this.instance.interceptors.request.use(async (config)=>{
            // 客户端添加认证头
            if (("TURBOPACK compile-time value", "object") !== 'undefined' && !this.disableToken) {
                const session = this.getSessionSync();
                if (session) {
                    config.headers.Authorization = `Bearer ${session}`;
                }
            }
            return config;
        }, (error)=>Promise.reject(error));
        // 响应拦截
        this.instance.interceptors.response.use((response)=>{
            return response;
        }, (error)=>{
            // 统一错误处理
            if (error.response) {
                const { status, data } = error.response;
                const errMsg = data?.msg || error.message;
                switch(status){
                    case 401:
                        if ("TURBOPACK compile-time truthy", 1) {
                            localStorage.removeItem('token');
                            if (!error.request.responseURL.includes('/check-token')) {
                                window.location.href = '/login';
                            }
                        }
                        break;
                    case 403:
                        console.error('Permission denied:', errMsg);
                        break;
                    case 500:
                        console.error('Server error:', errMsg);
                        break;
                }
                return Promise.reject({
                    code: data?.code || status,
                    msg: errMsg,
                    data: data?.data || null
                });
            }
            return Promise.reject({
                code: -1,
                msg: error.message || 'Network Error',
                data: null
            });
        });
    }
    // 转换下划线为驼峰
    convertKeysToCamel(obj) {
        if (Array.isArray(obj)) {
            return obj.map((v)=>this.convertKeysToCamel(v));
        } else if (obj !== null && typeof obj === 'object') {
            return Object.keys(obj).reduce((acc, key)=>{
                const camelKey = key.replace(/_([a-z])/g, (_, letter)=>letter.toUpperCase());
                acc[camelKey] = this.convertKeysToCamel(obj[key]);
                return acc;
            }, {});
        }
        return obj;
    }
    // 错误处理
    handleError(error) {
        if (__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$axios$2f$lib$2f$axios$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].isCancel(error)) {
            throw {
                code: -2,
                msg: 'Request canceled',
                data: null
            };
        }
        throw error;
    }
    // 核心请求方法
    async request(config) {
        try {
            const response = await this.instance.request(config);
            return response.data.data;
        } catch (error) {
            return this.handleError(error);
        }
    }
    // 快捷方法
    get(url, params, config) {
        return this.request({
            method: 'get',
            url,
            params,
            ...config
        });
    }
    post(url, data, config) {
        return this.request({
            method: 'post',
            url,
            data,
            ...config
        });
    }
    put(url, data, config) {
        return this.request({
            method: 'put',
            url,
            data,
            ...config
        });
    }
    delete(url, config) {
        return this.request({
            method: 'delete',
            url,
            ...config
        });
    }
    postFile(url, formData, config) {
        return this.request({
            method: 'post',
            url,
            data: formData,
            headers: {
                'Content-Type': 'multipart/form-data'
            },
            ...config
        });
    }
    async downloadFile(url, config) {
        try {
            const response = await this.instance.get(url, {
                responseType: 'blob',
                ...config
            });
            return response;
        } catch (error) {
            return this.handleError(error);
        }
    }
}
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/infra/http/BackendClient.ts [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "BackendClient",
    ()=>BackendClient
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$BaseHttpClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/BaseHttpClient.ts [app-client] (ecmascript)");
;
class BackendClient extends __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$BaseHttpClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["BaseHttpClient"] {
    constructor(baseURL){
        super(baseURL, false);
    }
    // ============ Provider API ============
    getProviderRequesters(model_type) {
        return this.get('/api/v1/provider/requesters', {
            type: model_type
        });
    }
    getProviderRequester(name) {
        return this.get(`/api/v1/provider/requesters/${name}`);
    }
    getProviderRequesterIconURL(name) {
        if (this.instance.defaults.baseURL === '/') {
            const url = window.location.href;
            const baseURL = url.split('/').slice(0, 3).join('/');
            return `${baseURL}/api/v1/provider/requesters/${name}/icon`;
        }
        return this.instance.defaults.baseURL + `/api/v1/provider/requesters/${name}/icon`;
    }
    // ============ Model Providers ============
    getModelProviders() {
        return this.get('/api/v1/provider/providers');
    }
    getModelProvider(uuid) {
        return this.get(`/api/v1/provider/providers/${uuid}`);
    }
    createModelProvider(provider) {
        return this.post('/api/v1/provider/providers', provider);
    }
    updateModelProvider(uuid, provider) {
        return this.put(`/api/v1/provider/providers/${uuid}`, provider);
    }
    deleteModelProvider(uuid) {
        return this.delete(`/api/v1/provider/providers/${uuid}`);
    }
    // ============ Provider Model LLM ============
    getProviderLLMModels(providerUuid) {
        const params = providerUuid ? {
            provider_uuid: providerUuid
        } : {};
        return this.get('/api/v1/provider/models/llm', params);
    }
    getProviderLLMModel(uuid) {
        return this.get(`/api/v1/provider/models/llm/${uuid}`);
    }
    createProviderLLMModel(model) {
        return this.post('/api/v1/provider/models/llm', model);
    }
    deleteProviderLLMModel(uuid) {
        return this.delete(`/api/v1/provider/models/llm/${uuid}`);
    }
    updateProviderLLMModel(uuid, model) {
        return this.put(`/api/v1/provider/models/llm/${uuid}`, model);
    }
    testLLMModel(uuid, model) {
        return this.post(`/api/v1/provider/models/llm/${uuid}/test`, model);
    }
    // ============ Provider Model Embedding ============
    getProviderEmbeddingModels(providerUuid) {
        const params = providerUuid ? {
            provider_uuid: providerUuid
        } : {};
        return this.get('/api/v1/provider/models/embedding', params);
    }
    getProviderEmbeddingModel(uuid) {
        return this.get(`/api/v1/provider/models/embedding/${uuid}`);
    }
    createProviderEmbeddingModel(model) {
        return this.post('/api/v1/provider/models/embedding', model);
    }
    deleteProviderEmbeddingModel(uuid) {
        return this.delete(`/api/v1/provider/models/embedding/${uuid}`);
    }
    updateProviderEmbeddingModel(uuid, model) {
        return this.put(`/api/v1/provider/models/embedding/${uuid}`, model);
    }
    testEmbeddingModel(uuid, model) {
        return this.post(`/api/v1/provider/models/embedding/${uuid}/test`, model);
    }
    // ============ Pipeline API ============
    getGeneralPipelineMetadata() {
        // as designed, this method will be deprecated, and only for developer to check the prefered config schema
        return this.get('/api/v1/pipelines/_/metadata');
    }
    getPipelines(sortBy, sortOrder) {
        const params = new URLSearchParams();
        if (sortBy) params.append('sort_by', sortBy);
        if (sortOrder) params.append('sort_order', sortOrder);
        const queryString = params.toString();
        return this.get(`/api/v1/pipelines${queryString ? `?${queryString}` : ''}`);
    }
    getPipeline(uuid) {
        return this.get(`/api/v1/pipelines/${uuid}`);
    }
    createPipeline(pipeline) {
        return this.post('/api/v1/pipelines', pipeline);
    }
    updatePipeline(uuid, pipeline) {
        return this.put(`/api/v1/pipelines/${uuid}`, pipeline);
    }
    deletePipeline(uuid) {
        return this.delete(`/api/v1/pipelines/${uuid}`);
    }
    copyPipeline(uuid) {
        return this.post(`/api/v1/pipelines/${uuid}/copy`);
    }
    getPipelineExtensions(uuid) {
        return this.get(`/api/v1/pipelines/${uuid}/extensions`);
    }
    updatePipelineExtensions(uuid, bound_plugins, bound_mcp_servers, enable_all_plugins = true, enable_all_mcp_servers = true) {
        return this.put(`/api/v1/pipelines/${uuid}/extensions`, {
            bound_plugins,
            bound_mcp_servers,
            enable_all_plugins,
            enable_all_mcp_servers
        });
    }
    // ============ WebSocket Chat API ============
    getWebSocketHistoryMessages(pipelineId, sessionType) {
        return this.get(`/api/v1/pipelines/${pipelineId}/ws/messages/${sessionType}`);
    }
    async uploadWebSocketImage(pipelineId, imageFile) {
        const formData = new FormData();
        formData.append('file', imageFile);
        return this.postFile(`/api/v1/files/images`, formData);
    }
    resetWebSocketSession(pipelineId, sessionType) {
        return this.post(`/api/v1/pipelines/${pipelineId}/ws/reset/${sessionType}`);
    }
    getWebSocketConnections(pipelineId) {
        return this.get(`/api/v1/pipelines/${pipelineId}/ws/connections`);
    }
    broadcastWebSocketMessage(pipelineId, message) {
        return this.post(`/api/v1/pipelines/${pipelineId}/ws/broadcast`, {
            message
        });
    }
    // ============ Platform API ============
    getAdapters() {
        return this.get('/api/v1/platform/adapters');
    }
    getAdapter(name) {
        return this.get(`/api/v1/platform/adapters/${name}`);
    }
    getAdapterIconURL(name) {
        if (this.instance.defaults.baseURL === '/') {
            // 获取用户访问的URL
            const url = window.location.href;
            const baseURL = url.split('/').slice(0, 3).join('/');
            return `${baseURL}/api/v1/platform/adapters/${name}/icon`;
        }
        return this.instance.defaults.baseURL + `/api/v1/platform/adapters/${name}/icon`;
    }
    // ============ Platform Bots ============
    getBots() {
        return this.get('/api/v1/platform/bots');
    }
    getBot(uuid) {
        return this.get(`/api/v1/platform/bots/${uuid}`);
    }
    createBot(bot) {
        return this.post('/api/v1/platform/bots', bot);
    }
    updateBot(uuid, bot) {
        return this.put(`/api/v1/platform/bots/${uuid}`, bot);
    }
    deleteBot(uuid) {
        return this.delete(`/api/v1/platform/bots/${uuid}`);
    }
    getBotLogs(botId, request) {
        return this.post(`/api/v1/platform/bots/${botId}/logs`, request);
    }
    getBotSessions(botId, limit = 100, offset = 0) {
        const queryParams = new URLSearchParams();
        queryParams.append('botId', botId);
        queryParams.append('limit', limit.toString());
        queryParams.append('offset', offset.toString());
        return this.get(`/api/v1/monitoring/sessions?${queryParams.toString()}`);
    }
    getSessionMessages(sessionId, limit = 200, offset = 0) {
        const queryParams = new URLSearchParams();
        queryParams.append('sessionId', sessionId);
        queryParams.append('limit', limit.toString());
        queryParams.append('offset', offset.toString());
        return this.get(`/api/v1/monitoring/messages?${queryParams.toString()}`);
    }
    // ============ File management API ============
    uploadDocumentFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request({
            method: 'post',
            url: '/api/v1/files/documents',
            data: formData,
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });
    }
    // ============ Knowledge Base API ============
    getKnowledgeBases() {
        return this.get('/api/v1/knowledge/bases');
    }
    getKnowledgeBase(uuid) {
        return this.get(`/api/v1/knowledge/bases/${uuid}`);
    }
    createKnowledgeBase(base) {
        return this.post('/api/v1/knowledge/bases', base);
    }
    updateKnowledgeBase(uuid, base) {
        return this.put(`/api/v1/knowledge/bases/${uuid}`, base);
    }
    uploadKnowledgeBaseFile(uuid, file_id, parserPluginId) {
        return this.post(`/api/v1/knowledge/bases/${uuid}/files`, {
            file_id,
            parser_plugin_id: parserPluginId
        });
    }
    getKnowledgeBaseFiles(uuid) {
        return this.get(`/api/v1/knowledge/bases/${uuid}/files`);
    }
    deleteKnowledgeBaseFile(uuid, file_id) {
        return this.delete(`/api/v1/knowledge/bases/${uuid}/files/${file_id}`);
    }
    deleteKnowledgeBase(uuid) {
        return this.delete(`/api/v1/knowledge/bases/${uuid}`);
    }
    retrieveKnowledgeBase(uuid, query, retrievalSettings) {
        return this.post(`/api/v1/knowledge/bases/${uuid}/retrieve`, {
            query,
            retrieval_settings: retrievalSettings ?? {}
        });
    }
    // ============ Knowledge Engines API ============
    getKnowledgeEngines() {
        return this.get('/api/v1/knowledge/engines');
    }
    // ============ Parsers API ============
    listParsers(mimeType) {
        const params = mimeType ? `?mime_type=${encodeURIComponent(mimeType)}` : '';
        return this.get(`/api/v1/knowledge/parsers${params}`);
    }
    // ============ Plugins API ============
    getPlugins() {
        return this.get('/api/v1/plugins');
    }
    getPlugin(author, name) {
        return this.get(`/api/v1/plugins/${author}/${name}`);
    }
    getPluginConfig(author, name) {
        return this.get(`/api/v1/plugins/${author}/${name}/config`);
    }
    updatePluginConfig(author, name, config) {
        return this.put(`/api/v1/plugins/${author}/${name}/config`, config);
    }
    uploadPluginConfigFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request({
            method: 'post',
            url: '/api/v1/plugins/config-files',
            data: formData,
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });
    }
    deletePluginConfigFile(fileKey) {
        return this.delete(`/api/v1/plugins/config-files/${fileKey}`);
    }
    getPluginReadme(author, name, language = 'en') {
        return this.get(`/api/v1/plugins/${author}/${name}/readme?language=${language}`);
    }
    getPluginAssetURL(author, name, filepath) {
        return this.instance.defaults.baseURL + `/api/v1/plugins/${author}/${name}/assets/${filepath}`;
    }
    getPluginIconURL(author, name) {
        if (this.instance.defaults.baseURL === '/') {
            const url = window.location.href;
            const baseURL = url.split('/').slice(0, 3).join('/');
            return `${baseURL}/api/v1/plugins/${author}/${name}/icon`;
        }
        return this.instance.defaults.baseURL + `/api/v1/plugins/${author}/${name}/icon`;
    }
    installPluginFromGithub(assetUrl, owner, repo, releaseTag) {
        return this.post('/api/v1/plugins/install/github', {
            asset_url: assetUrl,
            owner,
            repo,
            release_tag: releaseTag
        });
    }
    getGithubReleases(repoUrl) {
        return this.post('/api/v1/plugins/github/releases', {
            repo_url: repoUrl
        });
    }
    getGithubReleaseAssets(owner, repo, releaseId) {
        return this.post('/api/v1/plugins/github/release-assets', {
            owner,
            repo,
            release_id: releaseId
        });
    }
    installPluginFromLocal(file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.postFile('/api/v1/plugins/install/local', formData);
    }
    installPluginFromMarketplace(author, name, version) {
        return this.post('/api/v1/plugins/install/marketplace', {
            plugin_author: author,
            plugin_name: name,
            plugin_version: version
        });
    }
    removePlugin(author, name, deleteData = false) {
        return this.delete(`/api/v1/plugins/${author}/${name}?delete_data=${deleteData}`);
    }
    upgradePlugin(author, name) {
        return this.post(`/api/v1/plugins/${author}/${name}/upgrade`);
    }
    // ============ MCP API ============
    getMCPServers() {
        return this.get('/api/v1/mcp/servers');
    }
    getMCPServer(serverName) {
        return this.get(`/api/v1/mcp/servers/${serverName}`);
    }
    createMCPServer(server) {
        return this.post('/api/v1/mcp/servers', server);
    }
    updateMCPServer(serverName, server) {
        return this.put(`/api/v1/mcp/servers/${serverName}`, server);
    }
    deleteMCPServer(serverName) {
        return this.delete(`/api/v1/mcp/servers/${serverName}`);
    }
    toggleMCPServer(serverName, target_enabled) {
        return this.put(`/api/v1/mcp/servers/${serverName}`, {
            enable: target_enabled
        });
    }
    testMCPServer(serverName, serverData) {
        return this.post(`/api/v1/mcp/servers/${serverName}/test`, serverData);
    }
    installMCPServerFromGithub(source) {
        return this.post('/api/v1/mcp/install/github', {
            source
        });
    }
    installMCPServerFromSSE(source) {
        return this.post('/api/v1/mcp/servers', {
            source
        });
    }
    // ============ System API ============
    getSystemInfo() {
        return this.get('/api/v1/system/info');
    }
    getAsyncTasks() {
        return this.get('/api/v1/system/tasks');
    }
    getAsyncTask(id) {
        return this.get(`/api/v1/system/tasks/${id}`);
    }
    getPluginSystemStatus() {
        return this.get('/api/v1/system/status/plugin-system');
    }
    // ============ RAG Migration API ============
    getRagMigrationStatus() {
        return this.get('/api/v1/knowledge/migration/status');
    }
    executeRagMigration(installPlugin = true) {
        return this.post('/api/v1/knowledge/migration/execute', {
            install_plugin: installPlugin
        });
    }
    dismissRagMigration() {
        return this.post('/api/v1/knowledge/migration/dismiss');
    }
    getPluginDebugInfo() {
        return this.get('/api/v1/plugins/debug-info');
    }
    // ============ User API ============
    checkIfInited() {
        return this.get('/api/v1/user/init');
    }
    initUser(user, password) {
        return this.post('/api/v1/user/init', {
            user,
            password
        });
    }
    authUser(user, password) {
        return this.post('/api/v1/user/auth', {
            user,
            password
        });
    }
    checkUserToken() {
        return this.get('/api/v1/user/check-token');
    }
    resetPassword(user, recoveryKey, newPassword) {
        return this.post('/api/v1/user/reset-password', {
            user,
            recovery_key: recoveryKey,
            new_password: newPassword
        });
    }
    changePassword(currentPassword, newPassword) {
        return this.post('/api/v1/user/change-password', {
            current_password: currentPassword,
            new_password: newPassword
        });
    }
    getUserInfo() {
        return this.get('/api/v1/user/info');
    }
    getSpaceCredits() {
        return this.get('/api/v1/user/space-credits');
    }
    getAccountInfo() {
        return this.get('/api/v1/user/account-info');
    }
    setPassword(newPassword, currentPassword) {
        return this.post('/api/v1/user/set-password', {
            new_password: newPassword,
            current_password: currentPassword
        });
    }
    async bindSpaceAccount(code, state) {
        const response = await this.instance.post('/api/v1/user/bind-space', {
            code,
            state
        });
        if (response.data.code !== 0) {
            throw {
                code: response.data.code,
                msg: response.data.msg || 'Unknown error'
            };
        }
        return response.data.data;
    }
    // ============ Space OAuth API (Redirect Flow) ============
    getSpaceAuthorizeUrl(redirectUri, state) {
        const params = {
            redirect_uri: redirectUri
        };
        if (state) {
            params.state = state;
        }
        return this.get('/api/v1/user/space/authorize-url', params);
    }
    async exchangeSpaceOAuthCode(code) {
        const response = await this.instance.post('/api/v1/user/space/callback', {
            code
        });
        if (response.data.code !== 0) {
            throw {
                code: response.data.code,
                msg: response.data.msg || 'Unknown error'
            };
        }
        return response.data.data;
    }
    // ============ Monitoring API ============
    getMonitoringData(params) {
        const queryParams = new URLSearchParams();
        if (params.botId) {
            params.botId.forEach((id)=>queryParams.append('botId', id));
        }
        if (params.pipelineId) {
            params.pipelineId.forEach((id)=>queryParams.append('pipelineId', id));
        }
        if (params.startTime) {
            queryParams.append('startTime', params.startTime);
        }
        if (params.endTime) {
            queryParams.append('endTime', params.endTime);
        }
        if (params.limit) {
            queryParams.append('limit', params.limit.toString());
        }
        return this.get(`/api/v1/monitoring/data?${queryParams.toString()}`);
    }
    getMonitoringOverview(params) {
        const queryParams = new URLSearchParams();
        if (params.botId) {
            params.botId.forEach((id)=>queryParams.append('botId', id));
        }
        if (params.pipelineId) {
            params.pipelineId.forEach((id)=>queryParams.append('pipelineId', id));
        }
        if (params.startTime) {
            queryParams.append('startTime', params.startTime);
        }
        if (params.endTime) {
            queryParams.append('endTime', params.endTime);
        }
        return this.get(`/api/v1/monitoring/overview?${queryParams.toString()}`);
    }
    // ============ Survey API ============
    getSurveyPending() {
        return this.get('/api/v1/survey/pending');
    }
    submitSurveyResponse(surveyId, answers, completed = true) {
        return this.post('/api/v1/survey/respond', {
            survey_id: surveyId,
            answers,
            completed
        });
    }
    dismissSurvey(surveyId) {
        return this.post('/api/v1/survey/dismiss', {
            survey_id: surveyId
        });
    }
}
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/infra/http/CloudServiceClient.ts [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CloudServiceClient",
    ()=>CloudServiceClient
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$BaseHttpClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/BaseHttpClient.ts [app-client] (ecmascript)");
;
class CloudServiceClient extends __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$BaseHttpClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["BaseHttpClient"] {
    constructor(baseURL = ''){
        // cloud service 不需要 token 认证
        super(baseURL, true);
    }
    getMarketplacePlugins(page, page_size, sort_by, sort_order) {
        return this.get('/api/v1/marketplace/plugins', {
            page,
            page_size,
            sort_by,
            sort_order
        });
    }
    searchMarketplacePlugins(query, page, page_size, sort_by, sort_order, component_filter, tags_filter) {
        return this.post('/api/v1/marketplace/plugins/search', {
            query,
            page,
            page_size,
            sort_by,
            sort_order,
            component_filter,
            tags_filter
        });
    }
    getPluginDetail(author, pluginName) {
        return this.get(`/api/v1/marketplace/plugins/${author}/${pluginName}`);
    }
    getPluginREADME(author, pluginName, language) {
        return this.get(`/api/v1/marketplace/plugins/${author}/${pluginName}/resources/README`, language ? {
            language
        } : undefined);
    }
    getPluginIconURL(author, name) {
        return `${this.baseURL}/api/v1/marketplace/plugins/${author}/${name}/resources/icon`;
    }
    getPluginAssetURL(author, pluginName, filepath) {
        return `${this.baseURL}/api/v1/marketplace/plugins/${author}/${pluginName}/resources/assets/${filepath}`;
    }
    getPluginMarketplaceURL(cloud_service_url, author, name) {
        return `${cloud_service_url}/market/${author}/${name}`;
    }
    getLangBotReleases() {
        return this.get('/api/v1/dist/info/releases');
    }
    getAllTags() {
        return this.get('/api/v1/marketplace/tags');
    }
    getRecommendationLists() {
        return this.get('/api/v1/marketplace/recommendation-lists');
    }
}
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-client] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "backendClient",
    ()=>backendClient,
    "clearUserInfo",
    ()=>clearUserInfo,
    "cloudServiceClient",
    ()=>cloudServiceClient,
    "getCloudServiceClient",
    ()=>getCloudServiceClient,
    "getCloudServiceClientSync",
    ()=>getCloudServiceClientSync,
    "httpClient",
    ()=>httpClient,
    "initializeSystemInfo",
    ()=>initializeSystemInfo,
    "initializeUserInfo",
    ()=>initializeUserInfo,
    "systemInfo",
    ()=>systemInfo,
    "userInfo",
    ()=>userInfo
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$BackendClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/BackendClient.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$CloudServiceClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/CloudServiceClient.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$BaseHttpClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/BaseHttpClient.ts [app-client] (ecmascript)");
;
;
let systemInfo = {
    debug: false,
    version: '',
    edition: 'community',
    enable_marketplace: true,
    cloud_service_url: '',
    allow_modify_login_info: true,
    disable_models_service: false,
    limitation: {
        max_bots: -1,
        max_pipelines: -1,
        max_extensions: -1
    }
};
let userInfo = null;
/**
 * 获取基础 URL
 */ const getBaseURL = ()=>{
    if ("TURBOPACK compile-time truthy", 1) {
        return "TURBOPACK compile-time value", "http://us-ca-cloudcone-03.rockchin.top:5300";
    }
    //TURBOPACK unreachable
    ;
};
const backendClient = new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$BackendClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["BackendClient"](getBaseURL());
const httpClient = backendClient;
const cloudServiceClient = new __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$CloudServiceClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CloudServiceClient"]('https://space.langbot.app');
// 应用启动时自动初始化系统信息
if (("TURBOPACK compile-time value", "object") !== 'undefined' && systemInfo.cloud_service_url === '') {
    backendClient.getSystemInfo().then((info)=>{
        systemInfo = info;
        cloudServiceClient.updateBaseURL(info.cloud_service_url);
    }).catch((error)=>{
        console.error('Failed to initialize system info on startup:', error);
    });
}
const getCloudServiceClient = async ()=>{
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
const getCloudServiceClientSync = ()=>{
    return cloudServiceClient;
};
const initializeSystemInfo = async ()=>{
    try {
        systemInfo = await backendClient.getSystemInfo();
        cloudServiceClient.updateBaseURL(systemInfo.cloud_service_url);
    } catch (error) {
        console.error('Failed to initialize system info:', error);
    }
};
const initializeUserInfo = async ()=>{
    try {
        userInfo = await backendClient.getUserInfo();
    } catch (error) {
        console.error('Failed to initialize user info:', error);
        userInfo = null;
    }
};
const clearUserInfo = ()=>{
    userInfo = null;
};
;
;
;
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-client] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "HttpClient",
    ()=>HttpClient
]);
/**
 * @deprecated 此文件仅用于向后兼容。请使用新的 client：
 * - import { backendClient } from '@/app/infra/http'
 * - import { getCloudServiceClient } from '@/app/infra/http'
 */ // 重新导出新的客户端实现，保持向后兼容
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-client] (ecmascript) <locals>");
// 为了兼容性，重新导出 BackendClient 作为 HttpClient
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$BackendClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/BackendClient.ts [app-client] (ecmascript)");
;
;
const HttpClient = __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$BackendClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["BackendClient"];
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-client] (ecmascript) <locals> <export backendClient as httpClient>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "httpClient",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["backendClient"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-client] (ecmascript) <locals>");
}),
"[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "cn",
    ()=>cn
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/clsx/dist/clsx.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$tailwind$2d$merge$2f$dist$2f$bundle$2d$mjs$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/tailwind-merge/dist/bundle-mjs.mjs [app-client] (ecmascript)");
;
;
function cn(...inputs) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$tailwind$2d$merge$2f$dist$2f$bundle$2d$mjs$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["twMerge"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["clsx"])(inputs));
}
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/components/ui/card.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Card",
    ()=>Card,
    "CardAction",
    ()=>CardAction,
    "CardContent",
    ()=>CardContent,
    "CardDescription",
    ()=>CardDescription,
    "CardFooter",
    ()=>CardFooter,
    "CardHeader",
    ()=>CardHeader,
    "CardTitle",
    ()=>CardTitle
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-client] (ecmascript)");
;
;
function Card({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "card",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('bg-card text-card-foreground flex flex-col gap-6 rounded-xl border py-6 shadow-sm', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/card.tsx",
        lineNumber: 7,
        columnNumber: 5
    }, this);
}
_c = Card;
function CardHeader({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "card-header",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('@container/card-header grid auto-rows-min grid-rows-[auto_auto] items-start gap-1.5 px-6 has-data-[slot=card-action]:grid-cols-[1fr_auto] [.border-b]:pb-6', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/card.tsx",
        lineNumber: 20,
        columnNumber: 5
    }, this);
}
_c1 = CardHeader;
function CardTitle({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "card-title",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('leading-none font-semibold', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/card.tsx",
        lineNumber: 33,
        columnNumber: 5
    }, this);
}
_c2 = CardTitle;
function CardDescription({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "card-description",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('text-muted-foreground text-sm', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/card.tsx",
        lineNumber: 43,
        columnNumber: 5
    }, this);
}
_c3 = CardDescription;
function CardAction({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "card-action",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('col-start-2 row-span-2 row-start-1 self-start justify-self-end', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/card.tsx",
        lineNumber: 53,
        columnNumber: 5
    }, this);
}
_c4 = CardAction;
function CardContent({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "card-content",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('px-6', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/card.tsx",
        lineNumber: 66,
        columnNumber: 5
    }, this);
}
_c5 = CardContent;
function CardFooter({ className, ...props }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        "data-slot": "card-footer",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('flex items-center px-6 [.border-t]:pt-6', className),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/card.tsx",
        lineNumber: 76,
        columnNumber: 5
    }, this);
}
_c6 = CardFooter;
;
var _c, _c1, _c2, _c3, _c4, _c5, _c6;
__turbopack_context__.k.register(_c, "Card");
__turbopack_context__.k.register(_c1, "CardHeader");
__turbopack_context__.k.register(_c2, "CardTitle");
__turbopack_context__.k.register(_c3, "CardDescription");
__turbopack_context__.k.register(_c4, "CardAction");
__turbopack_context__.k.register(_c5, "CardContent");
__turbopack_context__.k.register(_c6, "CardFooter");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Button",
    ()=>Button,
    "buttonVariants",
    ()=>buttonVariants
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/@radix-ui/react-slot/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$class$2d$variance$2d$authority$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/class-variance-authority/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-client] (ecmascript)");
;
;
;
;
const buttonVariants = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$class$2d$variance$2d$authority$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cva"])("cursor-pointer inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive", {
    variants: {
        variant: {
            default: 'bg-[#2288ee] text-primary-foreground shadow-xs hover:bg-[#2277e0]',
            destructive: 'bg-destructive text-white shadow-xs hover:bg-destructive/90 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 dark:bg-destructive/60',
            outline: 'border bg-background shadow-xs hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50',
            secondary: 'bg-secondary text-secondary-foreground shadow-xs hover:bg-secondary/80',
            ghost: 'hover:bg-accent hover:text-accent-foreground dark:hover:bg-accent/100',
            link: 'text-primary underline-offset-4 hover:underline'
        },
        size: {
            default: 'h-9 px-4 py-2 has-[>svg]:px-3',
            sm: 'h-8 rounded-md gap-1.5 px-3 has-[>svg]:px-2.5',
            lg: 'h-10 rounded-md px-6 has-[>svg]:px-4',
            icon: 'size-9'
        }
    },
    defaultVariants: {
        variant: 'default',
        size: 'default'
    }
});
function Button({ className, variant, size, asChild = false, ...props }) {
    const Comp = asChild ? __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f40$radix$2d$ui$2f$react$2d$slot$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Slot"] : 'button';
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Comp, {
        "data-slot": "button",
        className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])(buttonVariants({
            variant,
            size,
            className
        })),
        ...props
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/button.tsx",
        lineNumber: 51,
        columnNumber: 5
    }, this);
}
_c = Button;
;
var _c;
__turbopack_context__.k.register(_c, "Button");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LoadingInline",
    ()=>LoadingInline,
    "LoadingPage",
    ()=>LoadingPage,
    "LoadingSpinner",
    ()=>LoadingSpinner
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$loader$2d$circle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Loader2$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/loader-circle.js [app-client] (ecmascript) <export default as Loader2>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/lib/utils.ts [app-client] (ecmascript)");
;
;
;
const sizeMap = {
    sm: 'h-4 w-4',
    default: 'h-8 w-8',
    lg: 'h-12 w-12'
};
const textSizeMap = {
    sm: 'text-xs',
    default: 'text-sm',
    lg: 'text-base'
};
function LoadingSpinner({ size = 'default', className, text = '加载中...', fullPage = false }) {
    const spinner = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "flex flex-col items-center gap-4",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$loader$2d$circle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Loader2$3e$__["Loader2"], {
                className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('animate-spin text-primary', sizeMap[size], className)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
                lineNumber: 45,
                columnNumber: 7
            }, this),
            text && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                className: (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$lib$2f$utils$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["cn"])('text-muted-foreground', textSizeMap[size]),
                children: text
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
                lineNumber: 49,
                columnNumber: 9
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
        lineNumber: 44,
        columnNumber: 5
    }, this);
    if (fullPage) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "fixed inset-0 flex items-center justify-center bg-background",
            children: spinner
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
            lineNumber: 56,
            columnNumber: 7
        }, this);
    }
    return spinner;
}
_c = LoadingSpinner;
function LoadingPage({ text }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(LoadingSpinner, {
        fullPage: true,
        text: text
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
        lineNumber: 69,
        columnNumber: 10
    }, this);
}
_c1 = LoadingPage;
function LoadingInline({ size, text }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(LoadingSpinner, {
        size: size,
        text: text
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx",
        lineNumber: 82,
        columnNumber: 10
    }, this);
}
_c2 = LoadingInline;
var _c, _c1, _c2;
__turbopack_context__.k.register(_c, "LoadingSpinner");
__turbopack_context__.k.register(_c1, "LoadingPage");
__turbopack_context__.k.register(_c2, "LoadingInline");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/assets/langbot-logo.webp (static in ecmascript, tag client)", ((__turbopack_context__) => {

__turbopack_context__.v("/_next/static/media/langbot-logo.41703e3d.webp");}),
"[project]/coding/projects/LangBot/web/src/app/assets/langbot-logo.webp.mjs { IMAGE => \"[project]/coding/projects/LangBot/web/src/app/assets/langbot-logo.webp (static in ecmascript, tag client)\" } [app-client] (structured image object with data url, ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$assets$2f$langbot$2d$logo$2e$webp__$28$static__in__ecmascript$2c$__tag__client$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/assets/langbot-logo.webp (static in ecmascript, tag client)");
;
const __TURBOPACK__default__export__ = {
    src: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$assets$2f$langbot$2d$logo$2e$webp__$28$static__in__ecmascript$2c$__tag__client$29$__["default"],
    width: 548,
    height: 548,
    blurWidth: 8,
    blurHeight: 8,
    blurDataURL: "data:image/webp;base64,UklGRkgBAABXRUJQVlA4TDwBAAAvB8ABEM1VICICHghADgIAAID9kaQyqoQRAgYAAAAAAAAAAgAAAAAAAAAAAAAAAAA8CEQq2ACp+X0AAIAHApCDAAAAcP73X1iZlvQiAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAi9FlrQzHkgaDkIAAAA579vFdLQshAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAARI60WJXS80AGDQAAAADOfwgAAAAAAAAAAA4AAAAAAAAAAAAAAADgCAAAAAAAAAAAQq7H/N7TgYqB84swNqv3dIDSDJdp2dhYkABUvKcDlW46uNVkSJ+yZV9U4QEqBAwpu54oU8IbpObN2wr6M3CUFHW4lf3rrTUAUGQIBOO8K7pPO55sLEIJUvNE2HEP7tzbr5Fu5+TMkYCxWePXLpbO8zf0qxUBY7MC"
};
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>SpaceOAuthCallback
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/next/navigation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$HttpClient$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/HttpClient.ts [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/app/infra/http/index.ts [app-client] (ecmascript) <locals> <export backendClient as httpClient>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/sonner/dist/index.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/react-i18next/dist/es/useTranslation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$loader$2d$circle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Loader2$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/loader-circle.js [app-client] (ecmascript) <export default as Loader2>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$circle$2d$alert$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__AlertCircle$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/circle-alert.js [app-client] (ecmascript) <export default as AlertCircle>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$circle$2d$check$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__CheckCircle2$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/circle-check.js [app-client] (ecmascript) <export default as CheckCircle2>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$triangle$2d$alert$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__AlertTriangle$3e$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/node_modules/lucide-react/dist/esm/icons/triangle-alert.js [app-client] (ecmascript) <export default as AlertTriangle>");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/card.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/button.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$loading$2d$spinner$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/coding/projects/LangBot/web/src/components/ui/loading-spinner.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$assets$2f$langbot$2d$logo$2e$webp$2e$mjs__$7b$__IMAGE__$3d3e$__$225b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$assets$2f$langbot$2d$logo$2e$webp__$28$static__in__ecmascript$2c$__tag__client$2922$__$7d$__$5b$app$2d$client$5d$__$28$structured__image__object__with__data__url$2c$__ecmascript$29$__ = __turbopack_context__.i('[project]/coding/projects/LangBot/web/src/app/assets/langbot-logo.webp.mjs { IMAGE => "[project]/coding/projects/LangBot/web/src/app/assets/langbot-logo.webp (static in ecmascript, tag client)" } [app-client] (structured image object with data url, ecmascript)');
;
var _s = __turbopack_context__.k.signature();
'use client';
;
;
;
;
;
;
;
;
;
;
function SpaceOAuthCallbackContent() {
    _s();
    const router = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRouter"])();
    const searchParams = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useSearchParams"])();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"])();
    const [status, setStatus] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('loading');
    const [errorMessage, setErrorMessage] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('');
    const [isBindMode, setIsBindMode] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [code, setCode] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [isProcessing, setIsProcessing] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [localEmail, setLocalEmail] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('');
    const handleOAuthCallback = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "SpaceOAuthCallbackContent.useCallback[handleOAuthCallback]": async (authCode)=>{
            try {
                const response = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].exchangeSpaceOAuthCode(authCode);
                localStorage.setItem('token', response.token);
                if (response.user) {
                    localStorage.setItem('userEmail', response.user);
                }
                setStatus('success');
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].success(t('common.spaceLoginSuccess'));
                setTimeout({
                    "SpaceOAuthCallbackContent.useCallback[handleOAuthCallback]": ()=>{
                        router.push('/home');
                    }
                }["SpaceOAuthCallbackContent.useCallback[handleOAuthCallback]"], 1000);
            } catch (err) {
                setStatus('error');
                const errorObj = err;
                const errMsg = (errorObj?.msg || '').toLowerCase();
                if (errMsg.includes('account email mismatch')) {
                    setErrorMessage(t('account.spaceEmailMismatch'));
                } else {
                    setErrorMessage(t('common.spaceLoginFailed'));
                }
            }
        }
    }["SpaceOAuthCallbackContent.useCallback[handleOAuthCallback]"], [
        router,
        t
    ]);
    const [bindState, setBindState] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const handleBindAccount = (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "SpaceOAuthCallbackContent.useCallback[handleBindAccount]": async (authCode, state)=>{
            setIsProcessing(true);
            try {
                const response = await __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$infra$2f$http$2f$index$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__$3c$export__backendClient__as__httpClient$3e$__["httpClient"].bindSpaceAccount(authCode, state);
                localStorage.setItem('token', response.token);
                if (response.user) {
                    localStorage.setItem('userEmail', response.user);
                }
                setStatus('success');
                __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$sonner$2f$dist$2f$index$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["toast"].success(t('account.bindSpaceSuccess'));
                setTimeout({
                    "SpaceOAuthCallbackContent.useCallback[handleBindAccount]": ()=>{
                        router.push('/home');
                    }
                }["SpaceOAuthCallbackContent.useCallback[handleBindAccount]"], 1000);
            } catch (err) {
                setStatus('error');
                const errorObj = err;
                const errMsg = (errorObj?.msg || '').toLowerCase();
                if (errMsg.includes('account email mismatch')) {
                    setErrorMessage(t('account.spaceEmailMismatch'));
                } else {
                    setErrorMessage(t('account.bindSpaceFailed'));
                }
            } finally{
                setIsProcessing(false);
            }
        }
    }["SpaceOAuthCallbackContent.useCallback[handleBindAccount]"], [
        router,
        t
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "SpaceOAuthCallbackContent.useEffect": ()=>{
            const authCode = searchParams.get('code');
            const error = searchParams.get('error');
            const errorDescription = searchParams.get('error_description');
            const mode = searchParams.get('mode');
            const state = searchParams.get('state');
            if (error) {
                setStatus('error');
                setErrorMessage(errorDescription || error || t('common.spaceLoginFailed'));
                return;
            }
            if (!authCode) {
                setStatus('error');
                setErrorMessage(t('common.spaceLoginNoCode'));
                return;
            }
            setCode(authCode);
            if (mode === 'bind') {
                // Bind mode - verify state (token) exists
                if (!state) {
                    setStatus('error');
                    setErrorMessage(t('account.bindSpaceInvalidState'));
                    return;
                }
                setBindState(state);
                setIsBindMode(true);
                setLocalEmail(localStorage.getItem('userEmail') || '');
                setStatus('confirm');
            } else {
                // Normal login/register mode
                handleOAuthCallback(authCode);
            }
        }
    }["SpaceOAuthCallbackContent.useEffect"], [
        searchParams,
        handleOAuthCallback,
        t
    ]);
    const handleConfirmBind = ()=>{
        if (code && bindState) {
            handleBindAccount(code, bindState);
        }
    };
    const handleCancelBind = ()=>{
        router.push('/home');
    };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "min-h-screen flex items-center justify-center bg-gray-50 dark:bg-neutral-900",
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Card"], {
            className: "w-[400px] shadow-lg dark:shadow-white/10",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CardHeader"], {
                    className: "text-center",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                            src: __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$assets$2f$langbot$2d$logo$2e$webp$2e$mjs__$7b$__IMAGE__$3d3e$__$225b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$app$2f$assets$2f$langbot$2d$logo$2e$webp__$28$static__in__ecmascript$2c$__tag__client$2922$__$7d$__$5b$app$2d$client$5d$__$28$structured__image__object__with__data__url$2c$__ecmascript$29$__["default"].src,
                            alt: "LangBot",
                            className: "w-16 h-16 mb-4 mx-auto"
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                            lineNumber: 152,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CardTitle"], {
                            className: "text-xl",
                            children: [
                                status === 'loading' && t('common.spaceLoginProcessing'),
                                status === 'confirm' && t('account.bindSpaceConfirmTitle'),
                                status === 'success' && (isBindMode ? t('account.bindSpaceSuccess') : t('common.spaceLoginSuccess')),
                                status === 'error' && (isBindMode ? t('account.bindSpaceFailed') : t('common.spaceLoginError'))
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                            lineNumber: 157,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CardDescription"], {
                            children: [
                                status === 'loading' && t('common.spaceLoginProcessingDescription'),
                                status === 'confirm' && t('account.bindSpaceConfirmDescription'),
                                status === 'success' && t('common.spaceLoginSuccessDescription'),
                                status === 'error' && errorMessage
                            ]
                        }, void 0, true, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                            lineNumber: 169,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                    lineNumber: 151,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CardContent"], {
                    className: "flex flex-col items-center space-y-4",
                    children: [
                        status === 'loading' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$loading$2d$spinner$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LoadingSpinner"], {
                            size: "lg",
                            text: ""
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                            lineNumber: 178,
                            columnNumber: 36
                        }, this),
                        status === 'confirm' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$triangle$2d$alert$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__AlertTriangle$3e$__["AlertTriangle"], {
                                    className: "h-12 w-12 text-yellow-500"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                                    lineNumber: 181,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    className: "text-sm text-center text-muted-foreground px-4",
                                    children: t('account.bindSpaceWarning', {
                                        localEmail: localEmail || '-'
                                    })
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                                    lineNumber: 182,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "flex gap-3 w-full",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                            variant: "outline",
                                            className: "flex-1",
                                            onClick: handleCancelBind,
                                            disabled: isProcessing,
                                            children: t('common.cancel')
                                        }, void 0, false, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                                            lineNumber: 188,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                            className: "flex-1",
                                            onClick: handleConfirmBind,
                                            disabled: isProcessing,
                                            children: [
                                                isProcessing ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$loader$2d$circle$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__Loader2$3e$__["Loader2"], {
                                                    className: "mr-2 h-4 w-4 animate-spin"
                                                }, void 0, false, {
                                                    fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                                                    lineNumber: 202,
                                                    columnNumber: 21
                                                }, this) : null,
                                                t('common.confirm')
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                                            lineNumber: 196,
                                            columnNumber: 17
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                                    lineNumber: 187,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true),
                        status === 'success' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$circle$2d$check$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__CheckCircle2$3e$__["CheckCircle2"], {
                            className: "h-12 w-12 text-green-500"
                        }, void 0, false, {
                            fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                            lineNumber: 210,
                            columnNumber: 13
                        }, this),
                        status === 'error' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$lucide$2d$react$2f$dist$2f$esm$2f$icons$2f$circle$2d$alert$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__AlertCircle$3e$__["AlertCircle"], {
                                    className: "h-12 w-12 text-red-500"
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                                    lineNumber: 214,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                                    onClick: ()=>router.push(isBindMode ? '/home' : '/login'),
                                    className: "w-full mt-4",
                                    children: isBindMode ? t('common.backToHome') : t('common.backToLogin')
                                }, void 0, false, {
                                    fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                                    lineNumber: 215,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true)
                    ]
                }, void 0, true, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                    lineNumber: 177,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
            lineNumber: 150,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
        lineNumber: 149,
        columnNumber: 5
    }, this);
}
_s(SpaceOAuthCallbackContent, "DEgKl9oW1qdJuvc00LbpVMWtEPI=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRouter"],
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useSearchParams"],
        __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$react$2d$i18next$2f$dist$2f$es$2f$useTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"]
    ];
});
_c = SpaceOAuthCallbackContent;
function LoadingFallback() {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "min-h-screen flex items-center justify-center bg-gray-50 dark:bg-neutral-900",
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Card"], {
            className: "w-[400px] shadow-lg dark:shadow-white/10",
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$card$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CardContent"], {
                className: "flex flex-col items-center py-12",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$src$2f$components$2f$ui$2f$loading$2d$spinner$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LoadingSpinner"], {
                    size: "lg",
                    text: ""
                }, void 0, false, {
                    fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                    lineNumber: 234,
                    columnNumber: 11
                }, this)
            }, void 0, false, {
                fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
                lineNumber: 233,
                columnNumber: 9
            }, this)
        }, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
            lineNumber: 232,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
        lineNumber: 231,
        columnNumber: 5
    }, this);
}
_c1 = LoadingFallback;
function SpaceOAuthCallback() {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Suspense"], {
        fallback: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(LoadingFallback, {}, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
            lineNumber: 243,
            columnNumber: 25
        }, void 0),
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$coding$2f$projects$2f$LangBot$2f$web$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(SpaceOAuthCallbackContent, {}, void 0, false, {
            fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
            lineNumber: 244,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/coding/projects/LangBot/web/src/app/auth/space/callback/page.tsx",
        lineNumber: 243,
        columnNumber: 5
    }, this);
}
_c2 = SpaceOAuthCallback;
var _c, _c1, _c2;
__turbopack_context__.k.register(_c, "SpaceOAuthCallbackContent");
__turbopack_context__.k.register(_c1, "LoadingFallback");
__turbopack_context__.k.register(_c2, "SpaceOAuthCallback");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
]);

//# sourceMappingURL=coding_projects_LangBot_web_src_5a4ae892._.js.map