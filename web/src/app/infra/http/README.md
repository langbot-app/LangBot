# HTTP Client 架构说明

## 概述

HTTP Client 已经重构为更清晰的架构，将通用方法与业务逻辑分离，并为不同的服务创建了独立的客户端。

## 文件结构

- **BaseHttpClient.ts** - 基础 HTTP 客户端类，包含所有通用的 HTTP 方法和拦截器配置
- **BackendClient.ts** - 后端服务客户端，处理与后端 API 的所有交互
- **CloudServiceClient.ts** - 云服务客户端，处理与 cloud service 的交互（如插件市场）
- **index.ts** - 主入口文件，管理客户端实例的创建和导出
- **HttpClient.ts** - 仅用于向后兼容的文件（已废弃）

## 使用方法

### 新的推荐用法

```typescript
// 使用后端客户端
import { backendClient } from '@/app/infra/http';

// 获取模型列表
const models = await backendClient.getProviderLLMModels();

// 使用云服务客户端（异步方式，确保 URL 已初始化）
import { getCloudServiceClient } from '@/app/infra/http';

const cloudClient = await getCloudServiceClient();
const marketPlugins = await cloudClient.getMarketPlugins(1, 10, 'search term');

// 使用云服务客户端（同步方式，可能使用默认 URL）
import { cloudServiceClient } from '@/app/infra/http';

const marketPlugins = await cloudServiceClient.getMarketPlugins(
  1,
  10,
  'search term',
);
```

### 向后兼容（不推荐）

```typescript
// 旧的用法仍然可以工作
import { httpClient, spaceClient } from '@/app/infra/http/HttpClient';

// httpClient 现在指向 backendClient
const models = await httpClient.getProviderLLMModels();

// spaceClient 现在指向 cloudServiceClient
const marketPlugins = await spaceClient.getMarketPlugins(1, 10, 'search term');
```

## 特点

1. **清晰的职责分离**
   - BaseHttpClient：通用 HTTP 功能
   - BackendClient：后端 API 业务逻辑
   - CloudServiceClient：云服务 API 业务逻辑

2. **自动初始化**
   - 应用启动时自动从后端获取 cloud service URL
   - 云服务客户端会自动更新 baseURL

3. **类型安全**
   - 所有方法都有完整的 TypeScript 类型定义
   - 请求和响应类型都从 `@/app/infra/entities/api` 导入

4. **向后兼容**
   - 旧代码无需修改即可继续工作
   - 逐步迁移到新的 API
