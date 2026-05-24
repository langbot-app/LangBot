# Agent Runner 插件化当前实现与收尾计划

本文档面向实现 agent，用来把当前 AgentRunner 插件化实现推进到可迁移状态。

当前代码已经不是从零开始的 PoC。LangBot 已经具备 registry、orchestrator、context/resource builder、result normalizer 和插件 runtime action。本计划重点描述剩余工作：补齐宿主通用能力、对齐旧内置 runner 行为、完成官方 runner 插件迁移验收。

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
- 转发调用：插件 runtime 只维护已安装插件本身的运行实例，Pipeline 不创建插件实例或 runner 实例

LangBot 不再长期维护内置业务 runner 分支。`local-agent`、Dify、n8n、Coze、DashScope、Langflow、Tbox 等都迁到官方 AgentRunner 插件。

迁移期间允许旧 `RequestRunner` 文件继续存在，作为行为对齐基准和回退分析材料。它们不影响当前进度；真正的最终条件是主聊天执行路径不再依赖旧 runner。

## 1.1 当前状态快照

已完成或基本完成：

- `AgentRunnerDescriptor`、runner id 解析、registry。
- `AgentRunOrchestrator` 替换 `ChatMessageHandler` 内部 runner 调度。
- `AgentRunContextBuilder`、`AgentResourceBuilder`、`AgentResultNormalizer`。
- `ai.runner.id` + `ai.runner_config[id]` 的读取与旧配置映射。
- AgentRunner runtime action：`LIST_AGENT_RUNNERS`、`RUN_AGENT`。
- run-scoped proxy authorization：模型、工具、知识库、存储、文件。

仍需收尾：

- `AgentRunContext` 暴露宿主处理后的有效 prompt、结构化输入和 runtime metadata。
- AgentRun proxy action 通过 `run_id/query_id` 找回当前 Query，保留旧 runner 行为所需上下文。
- `AgentResourceBuilder` 按 DynamicForm schema 泛化模型/rerank/知识库/文件授权。
- 官方 `local-agent` 插件完成旧内置 local-agent parity。
- timeout/deadline、取消、插件无输出、协议错误的端到端保护。
- 官方 runner 插件安装/预装/迁移缺失处理。

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
- `AgentRunOrchestrator` 是 LangBot 侧运行编排层：负责 runner 绑定解析、资源授权、context envelope provisioning、run scope 注册、插件调用和结果归一化；不负责决定 Agent 的最终 prompt/window/压缩策略。
- 插件是无状态执行单元：多个 Pipeline 可以绑定同一个 runner id，并分别保存自己的 `ai.runner_config[id]`；运行时 LangBot 只把当前绑定配置放入 `ctx.config` 转发给同一个插件 runner。
- 禁止按 Pipeline 或 runner config 创建多个插件实例。需要跨请求持久化的状态必须走明确授权的 plugin storage / workspace storage / 外部服务，不能隐式保存在 per-pipeline 插件对象里。
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

把当前 Pipeline query 转换成 SDK v1 `AgentRunContext` envelope。这里做协议字段组装、Host-owned 状态快照、授权资源挂载和默认工作窗口 provisioning，不承担 Agent 的最终 prompt 组装或长期记忆/压缩策略。

当前消息 Pipeline 的最小字段：

- `run_id`: 新 UUID，不使用 query id 作为全局 run id
- `trigger.type`: `message.received`
- `conversation`: launcher、sender、bot、pipeline、历史消息
- `event`: message event envelope 子集，`event_type` 使用稳定协议名，平台/SDK 原始事件名放入 `event_data.source_event_type`
- `actor`: sender
- `subject`: 当前消息或 launcher
- `prompt`: 宿主已处理的有效 prompt，即 `query.prompt.messages`
- `messages`: `query.messages` 进入 AgentRunner context packaging 后的历史窗口。插件化 AgentRunner 路径不再由 Pipeline `msgtrun` 截断
- `runtime.metadata.context_packaging`: Host 本次实际下发的历史窗口元数据，例如来源、策略、下发消息数、完整性；未来可扩展 cursor 和 host-side history API
- `input`: 从 `query.user_message` 和 `query.message_chain` 构造
- `params`: 过滤后的公开业务变量
- `resources`: 由 `resource_builder` 注入
- `state`: host-managed scoped state snapshot
- `runtime`: host/version/workspace/bot/pipeline/query/trace/deadline
- `config`: 当前 Pipeline 对该 runner id 的绑定配置，即 `ai.runner_config[runner_id]`

保留 SDK legacy helper 是 SDK 的责任，LangBot 不再构造 PoC 的 `query_id/session/messages/user_message/extra_config` 上下文。

`prompt` 的语义必须明确：它不是静态配置 `config["prompt"]`，而是 LangBot PreProcessor 和 `PromptPreProcessing` 插件事件之后的有效 prompt。旧内置 local-agent 请求模型时使用：

```python
query.prompt.messages + query.messages + [query.user_message]
```

插件化 runner 要保持行为一致，应消费：

```python
ctx.prompt + ctx.messages + [current_user_message_from_ctx.input]
```

现阶段不要优化裁剪算法，也不要把新的压缩或 token-budget 裁剪塞回 Pipeline stage。
插件化 AgentRunner 路径应跳过 Pipeline `msgtrun` 的破坏性截断，然后由
`AgentContextPackager` 在 AgentRunner 边界执行同一套 max-round user-round 规则。
当前 SDK v1 还没有顶层 context packaging 字段，LangBot 先把本次 packaging
元数据放在 `ctx.runtime.metadata.context_packaging`。这是实际下发结果说明，不是 LangBot 侧的长期策略控制面。
后续 LiteLLM 接入后再把真实 context window、token 预算和摘要策略接到这个边界上。

### 3.4.1 Agentic context plan

本轮只落地 `AgentContextPackager` 的 `max_round` working window，不改变 user-round 选择规则。
下面的 `ConversationStore` / `EventLog`、`ContextCompressor` 和 host history API 仍是设计预留。
目标是让 Pipeline 逐步退化为入口 adapter，让 AgentRunner 层拥有上下文打包职责。

建议最终拆成四个 host-side 服务：

```text
ConversationStore / EventLog
  -> durable append-only raw messages, events, tool results, artifact refs
ConversationProjection
  -> converts events into agent-readable conversation history
AgentContextPackager
  -> builds the bounded working context for one run
ContextCompressor
  -> creates and updates summaries/checkpoints when thresholds are exceeded
```

关键原则：

- 完整历史属于 LangBot host，不属于插件实例。插件仍是 singleton/stateless。
- `ctx.messages` 是 working context window，不是完整 conversation dump。
- 每轮不能全量复制/序列化完整历史给插件 runtime；否则长会话会产生 O(n) 成本和跨进程 payload 膨胀。
- `max-round` 的 user-round 规则可以先搬到 `AgentContextPackager`，作为 `max_round` adapter 策略。
- LiteLLM 接入后，`AgentContextPackager` 再读取模型 context window，升级为 token budget 策略。
- `ContextCompressor` 生成的是派生 summary/checkpoint，不能覆盖或删除 raw history。
- 重启恢复依赖持久化 store 和 summary checkpoint，不依赖 `SessionManager` 里的进程内 conversation list。

后续 `AgentRunContext` 可增加：

```python
context_request: AgentContextRequest | None
context_packaging: ContextPackagingMetadata
```

建议语义：

- `context_request.mode`: AgentRunner manifest / binding config 请求的 `max_round`、`token_budget`、`summary_hybrid`、`external_session`
- `context_request.budget`: 模型窗口、预留输出 token、工具/RAG 预算等偏好
- `context_packaging.policy`: Host 本次实际采用的打包策略
- `context_packaging.delivered_count`: 本次下发的历史消息数
- `context_packaging.source_total_count`: packager 可见的原始历史消息数
- `context_packaging.messages_complete`: 本窗口是否已经包含完整历史
- `context_packaging.cursor_before`: 未来通过 host API 读取更早历史的 cursor

未来需要的受限 API：

```python
api.get_conversation_messages(cursor: str | None, limit: int) -> HistoryPage
api.get_context_summary(scope: str = "conversation") -> ContextSummary | None
api.request_context_compaction(policy: dict) -> CompactionResult
```

这些 API 必须绑定 `run_id`、runner id、actor/subject scope 和资源权限；Host 需要限制
page size、总字节数、deadline 和可访问 conversation。

### 3.4.2 Large artifacts and tool collaboration

大文件、多模态输入和工具产物不要内联进 `ctx.messages` 或 tool result。后续统一用
artifact/resource ref 协作：

- message/content 里只放小文本和必要摘要。
- 大文件、图片、音频、长工具输出返回 `artifact_id`、`mime_type`、`size`、`digest`、
  `summary`、`expires_at`、`permissions`。
- `/tmp` 只能作为单次 run 的临时 staging，用于插件或工具短时间读写；它不是 durable store，
  也不能作为重启恢复依据。
- box/object storage 是长期 artifact 的目标位置。当前分支尚未合并 box 能力，因此本轮只写文档预留，不实现 API。
- 工具之间传递大结果时应传 artifact ref，不传完整 blob。Agent 需要读取时走受限 proxy。

未来建议 API：

```python
api.get_artifact_metadata(artifact_id: str) -> ArtifactMetadata
api.open_artifact_stream(artifact_id: str) -> AsyncIterator[bytes]
api.read_artifact_range(artifact_id: str, offset: int, length: int) -> bytes
api.create_temp_artifact(name: str, content_type: str, ttl_seconds: int) -> ArtifactWriter
```

安全约束：

- Host 校验 artifact 是否属于当前 run、conversation、actor/subject scope 或授权资源。
- 默认不允许插件直接读任意本地路径，包括 `/tmp` 任意路径。
- 临时文件应有 TTL 和清理机制；box artifact 应有 retention policy。
- 多模态文件进入模型前，由 runner/context packager 决定传引用、摘要、缩略图还是实际 bytes。

### 3.5 resource_builder.py

执行前做三层裁剪：

1. runner manifest 声明的 `spec.permissions`
2. Pipeline 的 `extensions_preferences`
3. 当前 Pipeline runner 绑定配置中选择的资源范围

输出写入 `ctx.resources`，至少覆盖：

- models：可调用模型 UUID、类型、能力摘要。包括 LLM、fallback LLM、rerank 等 runner config schema 中选择的模型类资源。
- tools：可见工具 manifest，使用当前 bound plugins / MCP server 范围
- knowledge_bases：可检索知识库列表
- storage：plugin storage / workspace storage 权限摘要
- files：允许读取的配置文件、知识文件摘要
- platform_capabilities：本阶段只声明，不执行平台动作

注意：旧的 unrestricted proxy action 必须二次校验，不能只靠 context 声明。AgentRunner 可用资源应来自 `ctx.resources`，不是插件 runtime 的全局能力。

资源裁剪要尽量通用，不应只写死 local-agent：

- `model-fallback-selector` 授权 primary/fallback LLM。
- `llm-model-selector` 授权 LLM。
- `rerank-model-selector` 授权 rerank 模型。
- `knowledge-base-multi-selector` 授权知识库。
- 后续新增 selector 时应在 resource builder 中统一扩展。

### 3.5.1 future EventRouter 预留

当前分支不实现 EBA EventRouter，但 AgentRunner 协议必须从现在开始兼容非消息事件。未来不要为消息撤回、群成员加入、好友申请各写一套 runner wrapper；统一入口应是：

```text
EventRouter -> AgentRunOrchestrator.run_from_event(event_request)
```

EBA 落地后，`ConversationStore` 不应只保存聊天消息，而应从 `EventLog` 投影生成：

```text
Platform Adapter
  -> EventLog append raw event
  -> ConversationProjection update message/history view when applicable
  -> EventRouter resolve binding
  -> AgentRunOrchestrator.run_from_event(event_request)
  -> AgentContextPackager build working context from projection + state + artifacts
```

这样消息事件、工具事件、群成员事件、好友申请事件可以共用同一套 run/session/state/resource
边界；非消息事件也不需要伪造成一条用户文本消息。

`event_request` 至少需要包含：

- `event_type`: 稳定协议名，例如 `message.recalled`、`group.member_joined`、`friend.request_received`
- `event_id` / `event_timestamp`
- `event_data`: 平台原始 payload 摘要和 source event type
- `actor`: 触发者，例如撤回操作者、新成员、好友申请人
- `subject`: 事件作用对象，例如被撤回消息、群/成员关系、好友申请
- `conversation`: 可选。群事件有 launcher 语义，好友申请可能还没有 conversation
- `input`: 可选结构化输入。非消息事件允许 `text=None`、`contents=[]`
- `binding`: 事件绑定解析出的 runner id、runner config、资源范围

先保留的稳定事件名：

- `message.received`
- `message.recalled`
- `group.member_joined`
- `friend.request_received`

这些事件名应作为插件协议的一部分保持稳定。平台原始事件名只能进入 `event_data`，不能成为 `ctx.event.event_type` 的公共契约。

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

配置模型表达的是 Pipeline 到 runner id 的绑定，不表达插件实例。插件安装后由 plugin runtime 管理单个插件运行实例；不同 Pipeline 选择同一个 runner id 时，只是保存不同的 `runner_config[id]`，调用时随 `AgentRunContext.config` 传入。

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

## 6. 收尾实现顺序

### Step 1：补齐宿主上下文

- SDK `AgentRunContext` 增加 `prompt`，并保持向后兼容默认空列表。
- LangBot context builder 写入 `ctx.prompt`、`ctx.input.contents`、`ctx.runtime.metadata.streaming_supported`、`ctx.runtime.metadata.remove_think`。
- 保持 `ctx.config` 只表达静态绑定配置。

### Step 2：增强宿主 AgentRun proxy action

- `invoke_llm` / `invoke_llm_stream` 通过 `run_id/query_id` 找回当前 Query。
- 自动合并 model persisted `extra_args` 与 action-level override。
- 自动应用 pipeline `remove-think`，并允许 action 显式 override。
- `call_tool` 传回当前 Query，恢复旧工具调用上下文。
- `retrieve_knowledge` 保持 `bot_uuid`、`sender_id`、`session_name` 等 settings。
- `invoke_rerank` 使用 run-scoped model authorization。

### Step 3：泛化资源构建

- 按 manifest permissions + bound plugins/MCP + runner config schema 构造资源。
- 支持 primary/fallback LLM、rerank model、KB selector。
- 不把 local-agent 特例扩散到通用资源层。

### Step 4：local-agent parity

- 使用 `ctx.prompt` 而不是重新读取 `ctx.config["prompt"]`。
- 当前 user message 从 `ctx.input.contents` 构造，保留多模态内容。
- RAG 只替换/插入文本部分，不丢图片/文件。
- streaming/non-streaming 默认跟随 `runtime.metadata.streaming_supported`。
- 首轮 fallback 成功后，tool loop 固定使用 committed model。
- tool loop 继续传可用 tools，支持多步工具调用。
- rerank 通过授权模型资源调用。

### Step 5：端到端保护和测试

- 插件无输出时按 runner failed 处理。
- timeout/deadline 覆盖 plugin runtime、模型调用和外部 runner 调用。
- runner 协议错误转受控错误。
- 覆盖旧 local-agent 行为 parity：普通回复、流式、工具、多步工具、KB、rerank、多模态、PromptPreProcessing。

### Step 6：官方 runner 迁移

- 官方插件 ready 后移除内置 runner registry
- 删除或隔离 provider runners 的运行引用
- 测试旧 runner 名只能通过 migration 映射到插件 id

### Step 7：历史配置迁移

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
- 插件 runtime 不为每个 Pipeline 或 runner 配置创建插件实例；`runner_config` 只作为绑定配置随 `ctx.config` 传入。
- 主聊天路径不再通过旧内置 runner 执行业务 runner。迁移期间旧文件可以保留。
- 插件只能访问 `ctx.resources` 授权的模型、工具、知识库和文件。
- 宿主 action 能为 AgentRunner 调用恢复必要 Query 语义，插件不需要拿裸 Query。
- 官方 `local-agent` 插件对外行为与旧内置 local-agent 对齐。
- EBA 相关字段只作为 context/result 预留，不执行平台动作。
