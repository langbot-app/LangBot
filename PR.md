# 重排序模型支持

## 概述

本次 PR 为 LangBot 添加了完整的重排序（Rerank）模型支持，包括：

- 后端新增 rerank 模型类型和多个 rerank 供应商配置
- 前端新增 rerank 模型管理 UI 和流水线配置
- 修复模型查询方法的缓存问题
- 添加 rerank 额外参数的用户提示

## 变更详情

### 1. 新增 rerank 供应商支持 (43772cef)

**后端**

- 在 `chatcmpl.py` 中实现通用的 rerank 接口调用逻辑
- 新增三个 rerank 专用供应商配置：
  - `coherererank.yaml` - Cohere rerank API
  - `jinarerank.yaml` - Jina AI rerank API  
  - `voyageairerank.yaml` - Voyage AI rerank API
- 为现有供应商添加 rerank 支持类型：
  - 302ai、百炼、GiteeAI、接口AI、SiliconFlow、Ollama
- 新增供应商图标资源

### 2. 前端 rerank 模型管理 UI (2b30cbba)

**前端**

- `ModelsDialog.tsx` - 支持 rerank 模型列表展示和加载
- `AddModelPopover.tsx` - 新增 rerank tab，支持添加 rerank 模型
- `ProviderCard.tsx` - 展示 rerank 模型数量和列表
- `ModelItem.tsx` - rerank 模型项展示
- `BackendClient.ts` - 新增 rerank 模型相关 API 调用方法
- `DynamicFormItemComponent.tsx` - 流水线配置支持选择 rerank 模型
- 新增 `RerankModel` 类型定义和 API 响应类型
- i18n 新增 `rerank` 翻译

### 3. 修正 rerank 支持类型 (6fc9a635)

经验证后调整供应商的 rerank 支持状态：

- ✅ 新增 OpenRouter rerank 支持（确认有 `/api/v1/rerank` endpoint）
- ❌ 移除 Ollama rerank 支持（无原生支持，相关 PR #7219 未合并）
- ❌ 移除接口AI rerank 支持（未找到 rerank 文档，URL 路径不匹配）

### 4. 修复缓存问题并添加参数提示 (2dca5a08)

**后端**

移除 `ModelManager` 中的 `@alru_cache` 装饰器：
- `get_model_by_uuid()`
- `get_embedding_model_by_uuid()`
- `get_rerank_model_by_uuid()`

原因：缓存导致数据不一致（新增/删除模型后 5 分钟内状态滞后）

**前端**

- `ExtraArgsEditor.tsx` - rerank 模型时显示额外参数 tooltip 提示
- 提示内容：`rerank_url` 和 `rerank_path` 参数说明
- i18n 新增中英文翻译

## 新增供应商

| 供应商 | Base URL | Endpoint |
|--------|----------|----------|
| Cohere | `https://api.cohere.com/v2` | `/rerank` |
| Jina AI | `https://api.jina.ai/v1` | `/rerank` |
| Voyage AI | `https://api.voyageai.com/v1` | `/rerank` |

## 额外参数说明

Rerank 模型支持以下额外参数：

- `rerank_url` - 完整 URL 覆盖（如阿里云 DashScope: `https://dashscope.aliyuncs.com/compatible-api/v1/reranks`）
- `rerank_path` - 路径覆盖（默认 `rerank`，如某些平台使用 `reranks`）

## 测试计划

- [ ] 启动 LangBot 后端，验证 rerank 供应商加载正常
- [ ] 打开 WebUI 模型配置，验证 rerank tab 显示
- [ ] 添加 Cohere/Jina/Voyage rerank 模型，测试连接
- [ ] 在流水线配置中选择 rerank 模型
- [ ] 验证新增模型立即可用（无缓存延迟）
- [ ] 验证 tooltip 在中英文环境下显示正确