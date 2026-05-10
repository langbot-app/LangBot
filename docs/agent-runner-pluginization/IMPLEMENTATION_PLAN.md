# Agent Runner 插件化最终实现计划

本文档面向实现 agent，用来把当前 PoC 分支直接推进到最终架构。这个分支不按线上渐进发布节奏处理，因此可以接受一次性破坏内部 runner 实现和 Pipeline AI 配置结构；但最终必须提供历史配置迁移。

## 1. 最终状态

LangBot 最终只保留 Agent Runner 的宿主能力：

- 发现 runner：`AgentRunnerRegistry`
- 选择 runner：Pipeline 配置和未来事件绑定配置
- 构造上下文：`AgentRunContext`
- 裁剪资源：模型、工具、知识库、文件、存储、平台能力
- 调度执行：`AgentRunOrchestrator`
- 归一结果：`AgentRunResult` -> 当前 Pipeline 的 `Message` / `MessageChunk`
- 隔离错误：插件异常、协议错误、超时、结果过大不能破坏主流程
- 迁移旧配置：把旧内置 runner 配置迁到官方 AgentRunner 插件配置

LangBot 不再长期维护内置业务 runner 分支。`local-agent`、Dify、n8n、Coze、DashScope、Langflow、Tbox 等都迁到官方 AgentRunner 插件。

## 2. 高层架构

```text
Pipeline MessageProcessor / future EventRouter
        |
        v
AgentRunOrchestrator
        |
        +--> AgentRunnerRegistry
        |       +--> plugin runtime LIST_AGENT_RUNNERS
        |       +--> descriptor cache / validation
        |
        +--> AgentRunContextBuilder
        +--> AgentResourceBuilder
        +--> AgentResultNormalizer
        |
        v
PluginRuntimeConnector.run_agent()
        |
        v
SDK Runtime RUN_AGENT -> plugin AgentRunner.run()
```

关键约束：

- `ChatMessageHandler` 不解析 `plugin:*`，不实例化 wrapper，不知道 runner 组件细节。
- `PipelineService.get_pipeline_metadata()` 不直接访问插件 runtime，而是读取 registry。
- 旧 `RequestRunner` 只作为迁移参考，不作为最终运行路径。
- EBA 只做字段预留，不在本轮实现 EventBus、EventRouter、平台动作执行。

## 3. 新增 LangBot 模块

建议新增：

```text
src/langbot/pkg/agent/
  __init__.py
  runner/
    __init__.py
    descriptor.py
    errors.py
    id.py
    registry.py
    context_builder.py
    resource_builder.py
    orchestrator.py
    result_normalizer.py
    config_migration.py
```

### 3.1 descriptor.py

定义 LangBot 内部使用的 descriptor：

```python
class AgentRunnerDescriptor(BaseModel):
    id: str
    source: Literal["plugin"]
    label: dict[str, str]
    description: dict[str, str] | None = None
    plugin_author: str
    plugin_name: str
    runner_name: str
    plugin_version: str | None = None
    protocol_version: str = "1"
    config_schema: list[dict[str, Any]] = []
    capabilities: dict[str, bool] = {}
    permissions: dict[str, list[str]] = {}
    raw_manifest: dict[str, Any] = {}
```

`source == "builtin"` 不作为最终目标。如果实现阶段需要临时 adapter，必须标记为测试过渡代码，并在官方插件跑通后删除。

### 3.2 id.py

统一 runner id 解析和生成：

- 插件 runner id：`plugin:{author}/{plugin_name}/{runner_name}`
- `parse_runner_id(id)` 返回结构化对象
- 禁止业务代码手写字符串 split
- PoC 已存在的 `plugin:author/name/runner` 继续作为合法 id

### 3.3 registry.py

职责：

- 调用 `ap.plugin_connector.list_agent_runners(bound_plugins=None)` 拉取插件 runner
- 校验 manifest：
  - `kind == AgentRunner`
  - `metadata.name` 存在
  - `metadata.label` 存在
  - `spec.protocol_version` 兼容，默认 `1`
  - `spec.config` 是 list，默认空
  - `spec.capabilities` 是 dict，默认空
  - `spec.permissions` 是 dict，默认空
- 输出 `AgentRunnerDescriptor`
- 缓存 discovery 结果，提供 `refresh()`
- 单个插件 manifest 失败只记录 warning，不影响其它 runner

刷新触发点：

- 插件安装、卸载、升级、重启后
- Pipeline metadata 请求时发现缓存为空
- 可选 TTL，优先保证正确性

### 3.4 context_builder.py

把当前 Pipeline query 直接转换成 SDK v1 `AgentRunContext`。

当前消息 Pipeline 的最小字段：

- `run_id`: 新 UUID，不使用 query id 作为全局 run id
- `trigger.type`: `message.received`
- `conversation`: launcher、sender、bot、pipeline、历史消息
- `event`: message event envelope 子集
- `actor`: sender
- `subject`: 当前消息或 launcher
- `messages`: `query.messages`
- `input`: 从 `query.user_message` 和 `query.message_chain` 构造
- `resources`: 由 `resource_builder` 注入
- `runtime`: host/version/workspace/bot/pipeline/query/trace/deadline
- `config`: 当前 runner id 对应的实例配置

保留 SDK legacy helper 是 SDK 的责任，LangBot 不再构造 PoC 的 `query_id/session/messages/user_message/extra_config` 上下文。

### 3.5 resource_builder.py

执行前做三层裁剪：

1. runner manifest 声明的 `spec.permissions`
2. Pipeline 的 `extensions_preferences`
3. runner 实例配置中选择的资源范围

输出写入 `ctx.resources`，至少覆盖：

- models：可调用模型 UUID、类型、能力摘要
- tools：可见工具 manifest，使用当前 bound plugins / MCP server 范围
- knowledge_bases：可检索知识库列表
- storage：plugin storage / workspace storage 权限摘要
- files：允许读取的配置文件、知识文件摘要
- platform_capabilities：本阶段只声明，不执行平台动作

注意：旧的 unrestricted proxy action 必须在 Phase 2 被二次校验，不能只靠 context 声明。

### 3.6 result_normalizer.py

只接受 SDK v1 result：

- `message.delta`
- `message.completed`
- `tool.call.started`
- `tool.call.completed`
- `state.updated`
- `run.completed`
- `run.failed`
- `action.requested` 允许实验性返回，但本阶段只记录 telemetry，不执行

映射：

- `message.delta.data.chunk` -> `provider_message.MessageChunk`
- `message.completed.data.message` -> `provider_message.Message`
- `run.completed.data.message` -> `provider_message.Message`
- `run.failed` -> 抛出受控异常，让 `ChatMessageHandler` 使用现有错误策略
- 工具和状态事件默认不 yield 到 Pipeline，只记录 debug/telemetry

防护：

- 未知 type warning 后忽略
- 单 result 序列化大小限制
- provider message schema 校验失败转 `run.failed`
- 插件没有输出任何消息时，按 runner failed 处理

### 3.7 orchestrator.py

核心入口：

```python
async def run_from_query(query: pipeline_query.Query) -> AsyncGenerator[Message | MessageChunk, None]:
    runner_id = resolve_runner_id(query.pipeline_config)
    descriptor = await registry.get(runner_id, bound_plugins=query.variables.get("_pipeline_bound_plugins"))
    ctx = await context_builder.from_query(query, descriptor)
    async for raw in plugin_connector.run_agent(...):
        async for message in result_normalizer.normalize(raw):
            yield message
```

必须覆盖：

- runner id 不存在
- 插件系统关闭
- runner 不在 bound plugins 范围内
- 插件 runtime 断连
- runner 协议版本不兼容
- run 超时
- task cancellation

## 4. 配置模型直接切换

目标格式：

```json
{
  "ai": {
    "runner": {
      "id": "plugin:langbot/local-agent/default",
      "expire-time": 0
    },
    "runner_config": {
      "plugin:langbot/local-agent/default": {}
    }
  }
}
```

兼容读取：

- 优先读 `ai.runner.id`
- 没有 `id` 时读旧 `ai.runner.runner`
- 旧内置 runner 名通过迁移表映射：
  - `local-agent` -> `plugin:langbot/local-agent/default`
  - `dify-service-api` -> `plugin:langbot/dify-agent/default`
  - `n8n-service-api` -> `plugin:langbot/n8n-agent/default`
  - `coze-api` -> `plugin:langbot/coze-agent/default`
  - `dashscope-app-api` -> `plugin:langbot/dashscope-agent/default`
  - `langflow-api` -> `plugin:langbot/langflow-agent/default`
  - `tbox-app-api` -> `plugin:langbot/tbox-agent/default`

写入策略：

- 新 UI 只写 `ai.runner.id` 和 `ai.runner_config`
- 后端 update 接口接受旧字段，但保存时归一成新格式
- migration 最后统一落库

## 5. 需要修改的 LangBot 范围

必须修改：

- `src/langbot/pkg/core/app.py`
  - 增加 `agent_runner_registry` / `agent_run_orchestrator` 属性
- `src/langbot/pkg/core/stages/build_app.py`
  - 初始化 Agent 子系统
- `src/langbot/pkg/pipeline/process/handlers/chat.py`
  - 删除 `PluginAgentRunnerWrapper`
  - 删除内置 runner 查找逻辑
  - 调用 orchestrator
- `src/langbot/pkg/api/http/service/pipeline.py`
  - metadata 从 registry 生成
- `src/langbot/pkg/plugin/connector.py`
  - `list_agent_runners()` / `run_agent()` 增加协议校验和 bound plugin 参数
- `src/langbot/pkg/plugin/handler.py`
  - proxy action 二次权限校验
- `src/langbot/pkg/pipeline/preproc/preproc.py`
  - 不再只为 `local-agent` 构造工具、知识库、模型
  - 对所有 agent runner 保留 multimodal input
- `src/langbot/pkg/pipeline/pipelinemgr.py`
  - runner name 监控改读 `runner.id`
- `src/langbot/templates/metadata/pipeline/ai.yaml`
  - runner 字段从 `runner` 迁到 `id`
- `src/langbot/templates/default-pipeline-config.json`
  - 默认 runner 改为官方 local-agent 插件 id
- `web/src/app/home/pipelines/components/pipeline-form/PipelineFormComponent.tsx`
  - 当前 runner 改读 `ai.runner.id`
  - runner 配置区改写入 `ai.runner_config[id]`

最终删除或停用：

- `src/langbot/pkg/provider/runner.py` 的业务注册路径
- `src/langbot/pkg/provider/runners/*` 的运行入口

可以暂时保留文件作为官方插件迁移参考，但不应被运行时引用。

## 6. 实现顺序

### Step 1：接入新版 SDK

- 更新 LangBot 依赖到包含 SDK v1 AgentRunner 协议的版本
- 删除 LangBot 中对旧 `AgentRunReturn` 类型名的依赖
- 确认 `langbot_plugin` 的本地 editable / lockfile 指向正确 SDK

### Step 2：Agent 子系统骨架

- 新增 descriptor/id/errors
- 新增 registry，先只 list plugin runner
- 为 registry 加单测，使用 fake connector

### Step 3：Pipeline metadata 切 registry

- `get_pipeline_metadata()` 只通过 registry 输出 runner option
- 插件 runner config stage 从 descriptor.config_schema 生成
- schema 错误不影响 metadata 返回

### Step 4：Orchestrator 替换 ChatMessageHandler

- 新增 context builder / result normalizer / orchestrator
- `chat.py` 删除 wrapper 和 runner 查找
- 维持现有流式卡片和 resp_messages 行为

### Step 5：新配置读写

- 后端 resolve runner id 支持新旧配置
- 前端表单改 `runner.id` + `runner_config`
- 默认配置改官方 local-agent 插件 id

### Step 6：权限和资源裁剪

- resource builder 根据 manifest / pipeline / instance config 裁剪
- proxy action 校验 resource scope
- 禁止插件用 unrestricted API 访问未授权知识库、工具、模型

### Step 7：删除内置 runner 运行分支

- 官方插件 ready 后移除内置 runner registry
- 删除或隔离 provider runners 的运行引用
- 测试旧 runner 名只能通过 migration 映射到插件 id

### Step 8：历史配置迁移

- 写 persistence migration
- 更新 default pipeline config
- 对已存在 Pipeline 执行旧字段到新字段迁移
- 对监控/日志里的 runner 字段改用新 id

## 7. 测试要求

单测：

- runner id parse / format
- registry manifest 校验、失败隔离、bound plugins 过滤
- context builder 从 query 生成完整 v1 context
- resource builder 三层裁剪
- result normalizer 对每种 result type 的映射
- 旧配置 resolve 和 migration

集成测试：

- fake AgentRunner 插件可被 Pipeline 选择
- streaming 输出仍能更新 message card
- 插件异常返回用户可理解错误，不中断 runtime
- runner 不在 bound plugins 时不可执行
- 未授权工具 / 知识库 / 模型 proxy 调用被拒绝
- 旧 `local-agent` Pipeline 配置迁到官方插件 id

## 8. 验收标准

- LangBot Pipeline 可以选择插件 AgentRunner 并完成非流式和流式回复。
- `ChatMessageHandler` 不包含插件 runner 解析和 wrapper。
- `PipelineService` 不直接拼插件 runner metadata。
- 所有 runner 配置使用 `ai.runner.id` + `ai.runner_config`。
- 旧内置 runner 不再作为 LangBot 内部运行分支执行。
- 插件只能访问 `ctx.resources` 授权的模型、工具、知识库和文件。
- EBA 相关字段只作为 context/result 预留，不执行平台动作。
