# FastGPTConnector

使用 FastGPT API 从 FastGPT 知识库中检索知识。

## 关于 FastGPT

FastGPT 是一个基于 LLM 大语言模型的开源知识库问答系统。它提供开箱即用的数据处理和模型调用能力，适用于复杂的问答场景。

## 功能特性

- 从 FastGPT 数据集/知识库中搜索和检索知识
- 支持多种搜索模式（向量搜索、全文检索、混合检索）
- 可配置的相似度阈值和 token 限制
- 可选的重排序功能以获得更好的结果
- 使用扩展模型进行查询优化

## 配置

本插件需要以下配置参数：

### 必填参数

- **api_base_url**：FastGPT API 的基础 URL
  - 本地部署：`http://localhost:3000`（默认）
  - 远程服务器：您的服务器 URL（例如 `https://your-domain.com`）
- **api_key**：您的 FastGPT API 密钥
  - 格式：`fastgpt-xxxxx`
- **dataset_id**：您的 FastGPT 知识库/数据集的 ID

### 可选参数

- **limit**（默认：5000）：返回的最大 token 数量
- **similarity**（默认：0.0）：最低相似度分数（0-1）
- **search_mode**（默认：embedding）：使用的搜索方法
  - `embedding`：语义向量搜索
  - `fullTextRecall`：全文关键词搜索
  - `mixedRecall`：混合搜索，结合两种方法
- **using_rerank**（默认：false）：是否使用重排序
- **dataset_search_using_extension_query**（默认：false）：是否使用查询优化
- **dataset_search_extension_model**（可选）：查询优化使用的模型
- **dataset_search_extension_bg**（可选）：查询优化的背景描述

## 如何获取配置值

### 获取您的 FastGPT API 密钥

1. 访问您的 FastGPT 实例（例如 `http://localhost:3000`）
2. 导航到 API 管理或设置部分
3. 创建或复制您的 API 密钥（格式：`fastgpt-xxxxx`）

### 获取您的数据集 ID

1. 在 FastGPT 中，进入您的知识库列表
2. 点击知识库查看其详细信息
3. 数据集 ID 可以在 URL 或数据集详情页面中找到

## API 参考

本插件使用 FastGPT 数据集搜索测试 API：
- 端点：`POST /api/core/dataset/searchTest`
- 文档：https://doc.fastgpt.io/docs/introduction/development/openapi/dataset

## 搜索方法

### 向量搜索（Embedding Search）
使用基于向量嵌入的语义相似度。最适合理解查询意图并找到语义相关的内容。

### 全文检索（Full-Text Recall）
传统的基于关键词的全文搜索。最适合查找精确匹配和特定术语。

### 混合检索（Mixed Recall）
结合向量搜索和全文搜索两种方法。提供兼具语义理解和关键词匹配的平衡结果。
