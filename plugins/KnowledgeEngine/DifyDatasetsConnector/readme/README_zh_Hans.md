# DifyDatasetsConnector

使用 Dify API 从 Dify 知识库中检索知识或向其中存入文件。

## 配置

请在 LangBot 中添加外部知识库，并选择"DifyDatasetsConnector"作为知识检索器类型。

### 创建设置（创建知识库时配置）

- **api_base_url**：Dify API 的基础 URL
  - Dify Cloud：`https://api.dify.ai/v1`（默认）
  - 自托管实例：您的服务器 URL（例如 `http://localhost/api` 或 `https://your-domain.com/api`）
- **dify_apikey**：您的 Dify 实例的 API 密钥
- **dataset_id**：您的 Dify 知识库/数据集的 ID

### 检索设置（每次查询可调整）

- **search_method**（默认：semantic_search）：使用的搜索方法
  - `keyword_search`：基于关键词的搜索
  - `semantic_search`：语义相似度搜索（默认）
  - `full_text_search`：全文搜索
  - `hybrid_search`：混合搜索，结合语义检索和全文检索
- **top_k**（默认：5）：返回的最大检索结果数量
- **score_threshold_enabled**（默认：关闭）：是否启用分数阈值过滤
- **score_threshold**（默认：0.5）：最低相关度分数（0-1），仅在启用分数阈值时显示
- **reranking_enable**（默认：关闭）：启用重排序以提升结果质量。重排序模型将自动从 Dify 数据集设置中获取，请先在 Dify 控制台中配置重排序模型

## 如何获取配置值

### 获取您的 Dify API 密钥

1. 访问 https://cloud.dify.ai/
2. 导航到您的知识库页面
3. 点击左侧边栏中的"API ACCESS"
4. 从"API Keys"部分创建或复制您的 API 密钥

### 获取您的数据集 ID

1. 在 Dify 知识库列表中，点击您的知识库
2. 数据集 ID 在 URL 中：`https://cloud.dify.ai/datasets/{dataset_id}`
3. 或者您可以在知识库的 API 文档页面中找到它

### 配置重排序

1. 在 Dify 控制台中，进入数据集设置
2. 启用重排序并选择重排序模型（如 `cohere/rerank-v3.5`）
3. 保存设置
4. 在 LangBot 中开启"启用重排序"开关，插件将自动使用 Dify 中配置的模型

## API 参考

本插件使用 Dify Dataset API：
- 检索：`POST /v1/datasets/{dataset_id}/retrieve`
- 数据集信息：`GET /v1/datasets/{dataset_id}`
- 文档上传：`POST /v1/datasets/{dataset_id}/document/create-by-file`
- 文档删除：`DELETE /v1/datasets/{dataset_id}/documents/{document_id}`
- 文档：https://docs.dify.ai/
