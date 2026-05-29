# LangBot AgentRunner Protocol v1

本文档定义 LangBot Host 与插件 SDK / Runtime / AgentRunner 之间的协议合同。它优先描述”稳定接口应是什么”，不描述具体落地任务。

## 当前状态

**Protocol v1 已在当前分支落地**：

- ✅ SDK 定义 `AgentRunnerManifest`、`AgentRunContext`、`AgentRunResult`、`AgentRunAPIProxy`
- ✅ Runtime 支持 `LIST_AGENT_RUNNERS` 和 `RUN_AGENT`
- ✅ Host 支持 `run_id` session authorization
- ✅ Host 能从当前 Pipeline 入口生成 event-first context
- ✅ `messages` 降级为 optional bootstrap
- ✅ `max-round` 不出现在协议实体中（只在 Pipeline adapter 中处理）
- ✅ Proxy 覆盖 model、tool、knowledge、state/storage
- ✅ History / Event / Artifact / State API 已落地
- ✅ EventLog / Transcript / ArtifactStore / PersistentStateStore 已落地
- ✅ `local-agent` 与 Claude Code runner 已通过本地 WebUI smoke，验证 host-infra runner 与外部 harness runner 共享同一协议路径

## 1. 协议目标

Protocol v1 要解决四件事：

- LangBot 如何发现插件提供的 AgentRunner。
- LangBot 如何把一次事件调用封装成 `AgentRunContext`。
- AgentRunner 如何以事件流形式返回运行结果。
- AgentRunner 如何通过受限 API 访问 LangBot host 能力。

Protocol v1 不定义：

- LangBot 内部如何持久化 AgentBinding。
- AgentRunner 内部如何组装 prompt、压缩历史、管理 memory。
- 官方 local-agent 的具体实现。
- Pipeline 的长期配置模型。
- 发布级安全 hardening 的完整实现；当前只定义 Host 侧资源、权限、状态和审计边界，release gate 见 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md)。

## 2. 参与方

| 名称 | 职责 |
| --- | --- |
| LangBot Host | 事件入口、绑定解析、权限、资源、存储、生命周期、结果投递。 |
| Plugin Runtime | 加载插件，响应 Host 的 runner discovery 和 run 调用。 |
| AgentRunner | 插件提供的 agent 执行组件。 |
| AgentRunAPIProxy | AgentRunner 访问 Host 能力的受限 API。 |
| AgentBinding | Host 内部的事件到 runner 绑定配置，不直接暴露给 SDK。 |

`AgentBinding` 只影响 Host 构造出的 `ctx.config`、`ctx.resources`、`ctx.context` 和 `ctx.delivery`。SDK 不需要知道 binding 的持久化形态。

外部 harness runner（Claude Code、Codex、Kimi Code 等）仍然是 `AgentRunner`。Protocol v1 只要求它们消费 event-first `AgentRunContext`、返回 `AgentRunResult`，并通过 Host 授权的 state/storage/artifact APIs 保存跨轮次指针。它们内部可以继续使用自己的 session、tool loop、MCP、上下文压缩和权限模型。

## 3. Discovery 协议

### 3.1 LIST_AGENT_RUNNERS

Host 调用 Plugin Runtime 获取当前插件暴露的 runner 列表。该请求不需要额外 payload。

Runtime 返回：

```python
class ListAgentRunnersResponse(BaseModel):
    runners: list[AgentRunnerManifest]
```

### 3.2 AgentRunnerManifest

```python
class AgentRunnerManifest(BaseModel):
    id: str
    name: str
    label: I18nObject
    description: I18nObject | None = None
    capabilities: AgentRunnerCapabilities
    permissions: AgentRunnerPermissions
    context: AgentRunnerContextPolicy
    config_schema: list[DynamicFormItemSchema] = []
    metadata: dict[str, Any] = {}
```

字段要求：

- `id` 必须稳定，推荐 `plugin:author/name/runner`。
- `name` 是插件内 runner 名称，例如 `default`。
- `config_schema` 只描述绑定配置表单，不代表插件实例状态。
- `metadata` 只能放展示、诊断、非稳定扩展信息。

### 3.3 Capabilities

```python
class AgentRunnerCapabilities(BaseModel):
    streaming: bool = False
    tool_calling: bool = False
    knowledge_retrieval: bool = False
    multimodal_input: bool = False
    event_context: bool = True
    platform_api: bool = False
    interrupt: bool = False
    stateful_session: bool = False
    self_managed_context: bool = True
```

语义：

- `streaming`: runner 可以返回 `message.delta`。
- `tool_calling`: runner 可能调用 Host tool APIs。
- `knowledge_retrieval`: runner 可能调用 Host knowledge APIs。
- `multimodal_input`: runner 可以处理非纯文本 input / artifact。
- `event_context`: runner 理解 event-first 输入。
- `platform_api`: runner 可能请求平台动作。
- `interrupt`: runner 支持取消或中断。
- `stateful_session`: runner 可能维护跨 run 会话状态。
- `self_managed_context`: runner 自己管理 working context，Host 不应默认 inline 历史。

### 3.4 Permissions

```python
class AgentRunnerPermissions(BaseModel):
    models: list[Literal["invoke", "stream", "rerank"]] = []
    tools: list[Literal["detail", "call"]] = []
    knowledge_bases: list[Literal["list", "retrieve"]] = []
    history: list[Literal["page", "search"]] = []
    events: list[Literal["get", "page"]] = []
    artifacts: list[Literal["metadata", "read"]] = []
    storage: list[Literal["plugin", "workspace", "binding"]] = []
    platform_api: list[str] = []
```

Manifest permissions 是 runner 需要的最大能力。实际可用资源还要经过 Host binding policy 和当前 run scope 裁剪。

### 3.5 Context Policy

```python
class AgentRunnerContextPolicy(BaseModel):
    ownership: Literal["self_managed", "host_bootstrap", "hybrid"] = "self_managed"
    bootstrap: Literal["none", "current_event", "recent_tail", "summary_tail"] = "current_event"
    max_inline_events: int = 0
    max_inline_bytes: int = 0
    supports_history_pull: bool = True
    supports_history_search: bool = False
    supports_artifact_pull: bool = True
    owns_compaction: bool = True
    wants_static_context_refs: bool = True
```

Host 使用该声明决定是否给 runner inline bootstrap history。默认原则：

- Host 不得默认 inline 全量历史。
- Host 默认只 inline 当前 event / input 和 context handles。
- Runner 拥有 working context assembly。
- Runner 可在授权后通过 Host history / event / artifact / state APIs 拉取更多上下文。
- `max-round` 不属于 Protocol v1 字段。

## 4. Run 协议

### 4.1 RUN_AGENT

Host 调用 Runtime：

```python
class AgentRunRequest(BaseModel):
    runner_id: str
    runner_name: str
    context: AgentRunContext
```

Runtime 返回 `AgentRunResult` 异步流。

插件运行时可以继续在底层 transport 中使用 `plugin_author`、`plugin_name`、`runner_name` 定位组件，但协议语义以 `runner_id` 和 `context` 为准。

### 4.2 AgentRunContext

```python
class AgentRunContext(BaseModel):
    run_id: str
    trigger: AgentTrigger
    event: AgentEventContext
    conversation: ConversationContext | None = None
    actor: ActorContext | None = None
    subject: SubjectContext | None = None
    input: AgentInput
    delivery: DeliveryContext
    resources: AgentResources
    context: ContextAccess
    state: AgentRunState
    runtime: AgentRuntimeContext
    config: dict[str, Any] = {}
    bootstrap: BootstrapContext | None = None
    adapter: AdapterContext | None = None
    metadata: dict[str, Any] = {}
```

核心约束：

- `event` 是必选字段，Protocol v1 是 event-first。
- `input` 表示当前事件的主输入，不等于历史消息。
- `bootstrap` 是可选字段，不是完整 history。
- `adapter` 只放 Pipeline adapter 字段，runner 不应依赖它做长期能力。
- `config` 是 Host binding config，不是插件实例状态。

### 4.3 AgentTrigger

```python
class AgentTrigger(BaseModel):
    type: str
    source: Literal["platform", "webui", "api", "scheduler", "system", "pipeline_adapter"]
    timestamp: int | None = None
```

`trigger.type` 应与 `event.event_type` 一致或更粗粒度。例如 Pipeline 兼容入口触发消息时：

```json
{
  "type": "message.received",
  "source": "pipeline_adapter"
}
```

### 4.4 AgentEventContext

```python
class AgentEventContext(BaseModel):
    event_id: str
    event_type: str
    event_time: int | None = None
    source: str
    source_event_type: str | None = None
    raw_ref: RawEventRef | None = None
    data: dict[str, Any] = {}
```

要求：

- `event_type` 使用 LangBot 稳定协议名，例如 `message.received`。
- 平台原始事件名放入 `source_event_type`。
- 大型原始 payload 必须放入 `raw_ref` 或 artifact，不应直接塞入 `data`。

### 4.5 Actor / Subject / Conversation

```python
class ConversationContext(BaseModel):
    conversation_id: str | None = None
    thread_id: str | None = None
    launcher_type: str | None = None
    launcher_id: str | None = None
    bot_id: str | None = None
    workspace_id: str | None = None

class ActorContext(BaseModel):
    actor_type: str
    actor_id: str | None = None
    actor_name: str | None = None
    metadata: dict[str, Any] = {}

class SubjectContext(BaseModel):
    subject_type: str
    subject_id: str | None = None
    data: dict[str, Any] = {}
```

示例：

- 消息事件：actor 是发消息的人，subject 是当前消息。
- 入群事件：actor 是新成员或邀请人，subject 是群/成员关系。
- 定时事件：actor 可以是 system，subject 是 schedule。

### 4.6 AgentInput

```python
class AgentInput(BaseModel):
    text: str | None = None
    contents: list[ContentElement] = []
    attachments: list[ArtifactRef] = []
    message_chain: dict[str, Any] | None = None
```

要求：

- 文本、多模态、附件都属于当前 event input。
- 大文件、图片、音频、工具大结果应以 artifact ref 传递。
- `message_chain` 是平台兼容字段，不应成为长期稳定依赖。

### 4.7 DeliveryContext

```python
class DeliveryContext(BaseModel):
    surface: str
    reply_target: dict[str, Any] | None = None
    supports_streaming: bool = False
    supports_edit: bool = False
    supports_reaction: bool = False
    max_message_size: int | None = None
    platform_capabilities: dict[str, Any] = {}
```

Runner 可以参考 delivery 能力决定返回 `message.delta`、`message.completed` 或 `action.requested`。

### 4.8 ContextAccess

```python
class ContextAccess(BaseModel):
    conversation_id: str | None = None
    thread_id: str | None = None
    latest_cursor: str | None = None
    event_seq: int | None = None
    transcript_seq: int | None = None
    has_history_before: bool = False
    inline_policy: InlineContextPolicy
    available_apis: ContextAPICapabilities
```

`ContextAccess` 告诉 runner：Host inline 了什么、没有 inline 什么、如果需要更多上下文应该通过哪些 API 拉取。
它不是 Host 的业务上下文编排策略，而是 runner 按需读取上下文的入口说明。

```python
class InlineContextPolicy(BaseModel):
    mode: Literal["none", "current_event", "recent_tail", "summary_tail"]
    delivered_count: int = 0
    source_total_count: int | None = None
    messages_complete: bool = False
    reason: str | None = None

class ContextAPICapabilities(BaseModel):
    history_page: bool = False
    history_search: bool = False
    event_get: bool = False
    event_page: bool = False
    artifact_metadata: bool = False
    artifact_read: bool = False
    state: bool = False
    storage: bool = False
```

### 4.9 BootstrapContext

```python
class BootstrapContext(BaseModel):
    messages: list[Message] = []
    summary: str | None = None
    artifacts: list[ArtifactRef] = []
    metadata: dict[str, Any] = {}
```

约束：

- `bootstrap.messages` 是 host convenience，不是协议核心。
- 自管 context runner 默认应收到空 bootstrap 或只收到当前 event。
- Host 不应为了”帮 agent 更聪明”而自动拼接完整 transcript。
- Pipeline adapter 的 `max-round` 配置只影响 adapter 如何生成 `bootstrap.messages`，不能成为 Protocol v1 字段。

### 4.10 RuntimeContext

```python
class AgentRuntimeContext(BaseModel):
    host: str = "langbot"
    langbot_version: str | None = None
    trace_id: str
    deadline_at: float | None = None
    locale: str | None = None
    timezone: str | None = None
    static_refs: dict[str, StaticContextRef] = {}
    metadata: dict[str, Any] = {}
```

`static_refs` 用于 KV cache 友好的静态上下文引用，例如 system policy、tool schema、resource manifest 的 hash/version。

### 4.11 State

```python
class AgentRunState(BaseModel):
    conversation: dict[str, Any] = {}
    actor: dict[str, Any] = {}
    subject: dict[str, Any] = {}
    runner: dict[str, Any] = {}
    binding: dict[str, Any] = {}
```

State 是可选 host-owned snapshot。Runner 也可以完全自管状态。

## 5. Resources

```python
class AgentResources(BaseModel):
    models: list[ModelResource] = []
    tools: list[ToolResource] = []
    knowledge_bases: list[KnowledgeBaseResource] = []
    artifacts: list[ArtifactResource] = []
    storage: StorageResource = StorageResource()
    history: HistoryResource = HistoryResource()
    platform_capabilities: dict[str, Any] = {}
```

资源列表是本次 run 的授权结果。Runner 只能通过 `AgentRunAPIProxy` 访问这些资源。

## 6. Result Stream

### 6.1 AgentRunResult

```python
class AgentRunResult(BaseModel):
    run_id: str
    type: str
    data: dict[str, Any] = {}
    sequence: int | None = None
    timestamp: int | None = None
```

### 6.2 稳定 result types

| type | 说明 |
| --- | --- |
| `message.delta` | 流式消息片段。 |
| `message.completed` | 完整消息。 |
| `tool.call.started` | runner 开始工具调用的可观测事件。 |
| `tool.call.completed` | runner 完成工具调用的可观测事件。 |
| `artifact.created` | runner 生成 artifact。 |
| `state.updated` | runner 请求更新 host-owned state。 |
| `action.requested` | runner 请求 Host 执行平台动作。 |
| `run.completed` | run 正常结束。 |
| `run.failed` | run 失败。 |

Host 必须忽略未知 result type 并记录 warning，除非该 type 明确要求强校验。

### 6.3 message.delta

```json
{
  "type": "message.delta",
  "data": {
    "chunk": {
      "role": "assistant",
      "content": "hel"
    }
  }
}
```

### 6.4 message.completed

```json
{
  "type": "message.completed",
  "data": {
    "message": {
      "role": "assistant",
      "content": "hello"
    }
  }
}
```

### 6.5 state.updated

```json
{
  "type": "state.updated",
  "data": {
    "scope": "conversation",
    "key": "external.session_id",
    "value": "abc"
  }
}
```

Host 必须校验 scope、key、value 大小和 JSON 可序列化性。

### 6.6 action.requested

```json
{
  "type": "action.requested",
  "data": {
    "action": "message.edit",
    "target": {"message_id": "..."},
    "payload": {"text": "..."}
  }
}
```

Protocol v1 只定义表达方式。Host 是否执行 action 取决于 platform API 能力、binding policy、审批策略和实现阶段。

## 7. AgentRunAPIProxy

所有 proxy action 必须携带 `run_id`。Host 必须校验：

- active run session 存在。
- caller plugin identity 匹配。
- resource 在本次 `ctx.resources` 中授权。
- scope 不越界。
- payload size / rate limit / deadline 合法。

### 7.1 Model APIs

```python
await api.models.invoke(model_id, messages, tools=None, extra_args=None)
await api.models.stream(model_id, messages, tools=None, extra_args=None)
await api.models.rerank(model_id, query, documents, top_k=None)
```

### 7.2 Tool APIs

```python
await api.tools.get_detail(tool_name)
await api.tools.call(tool_name, parameters)
```

### 7.3 Knowledge APIs

```python
await api.knowledge.retrieve(kb_id, query_text, top_k=5, filters=None)
```

### 7.4 History APIs

```python
await api.history.page(
    conversation_id=None,
    before_cursor=None,
    after_cursor=None,
    limit=50,
    direction="backward",
    include_artifacts=False,
)

await api.history.search(
    query,
    filters=None,
    top_k=10,
)
```

History API 返回 Transcript projection，不返回原始平台 payload。

### 7.5 Event APIs

```python
await api.events.get(event_id)
await api.events.page(before_cursor=None, limit=50)
```

Event API 返回稳定 event envelope 或受限 raw ref，不默认返回大 payload。

### 7.6 Artifact APIs

```python
await api.artifacts.metadata(artifact_id)
await api.artifacts.read_range(artifact_id, offset=0, length=65536)
await api.artifacts.open_stream(artifact_id)
```

Artifact API 必须支持大小限制、MIME 校验、过期时间和授权范围。

### 7.7 State / Storage APIs

```python
await api.state.get(scope, key)
await api.state.set(scope, key, value)
await api.state.delete(scope, key)

await api.storage.get(area, key)
await api.storage.set(area, key, value)
await api.storage.delete(area, key)
await api.storage.list(area, prefix=None)
```

建议区分：

- `state`: 小型 JSON 状态，适合 conversation / actor / runner / binding。
- `storage`: blob 或较大数据，适合插件私有数据、workspace 数据、checkpoint。

### 7.8 Platform APIs

```python
await api.platform.request_action(action, target, payload)
```

平台 API 是受限能力。默认不开放。需要 runner manifest、binding policy、用户审批策略同时允许。

## 8. 错误模型

Host API 错误统一返回：

```python
class AgentAPIError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = {}
```

建议 code：

| code | 说明 |
| --- | --- |
| `unauthorized` | 未授权访问资源或 scope。 |
| `not_found` | 资源不存在或对当前 runner 不可见。 |
| `deadline_exceeded` | 超过 run deadline。 |
| `payload_too_large` | 请求或响应过大。 |
| `rate_limited` | Host 限流。 |
| `invalid_argument` | 参数错误。 |
| `runtime_error` | Host 或下游能力错误。 |

Runner 失败使用 `run.failed`：

```json
{
  "type": "run.failed",
  "data": {
    "code": "runner.error",
    "message": "failed to call external agent",
    "retryable": false
  }
}
```

## 9. Timeout 与 Cancellation

Host 在 `ctx.runtime.deadline_at` 中下发总 deadline。SDK proxy 必须用该 deadline 限制单次 action timeout。

取消语义：

- Host 可以取消 active run。
- Runtime 应尽力中断 runner。
- Runner 支持中断时应返回或触发 `run.failed`，code 为 `cancelled`。
- Host 必须 unregister active run session。

## 10. Security 与 Guardrail

Protocol v1 的安全边界在 Host：

- Runner 不能直接访问未授权 model/tool/kb/history/artifact/storage。
- SDK 本地校验只提升开发体验，不能替代 Host 校验。
- 所有 resource id 对 runner 来说都是 opaque。
- 默认只能访问当前 conversation / thread 的 history。
- 跨会话、workspace 级 history 或 storage 必须额外授权。
- 大 payload 必须 artifact 化。
- Host 必须记录 run_id、runner_id、action、resource、scope、result。

对外部 harness runner，边界进一步拆分为：

- Host 在调用前完成 binding/resource policy 裁剪、路径策略、secret 过滤和审计记录。
- Runner plugin 把授权后的 context/resource projection 适配为目标 harness 的 context 文件、MCP 配置、skill 目录、环境变量或 CLI 参数。
- Claude Code / Codex / Kimi Code 等外部 harness 的 native permission mode、allowed/disallowed tools 和 sandbox 只是额外执行约束，不能替代 Host 侧授权。
- 外部 session id、working directory、checkpoint 等跨轮次指针应作为小型 JSON state 保存，例如 `external.session_id`、`external.working_directory`。

完整路径隔离、MCP allowlist、secret redaction、配额、workspace 清理和发布级安全测试不属于当前 Protocol v1 smoke 闭环，详见 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md)。

Host 不负责业务编排：

- 不拼接全量历史。
- 不替 runner 做业务 prompt assembly。
- 不内置 agent memory 策略。
- 不内置 tool loop 业务流程。
- 不内置上下文压缩策略。

这些能力可以由官方或第三方 AgentRunner 插件实现，并通过公开 Host APIs 消费 LangBot 的状态、历史、存储、artifact、模型、工具和知识库能力。

## 11. Pipeline Adapter

Pipeline 是当前入口 adapter，不是协议中心。

**当前分支已实现**：

- ✅ `PipelineAdapter.query_to_event(query)` — 从 `Query` 构造 `AgentEventEnvelope`
- ✅ `PipelineAdapter.pipeline_config_to_binding(query, runner_id)` — 从 Pipeline config 构造临时 AgentBinding
- ✅ `run_from_query()` 委托到 `run(event, binding)`
- ✅ `max-round` 在 Pipeline adapter 中处理，不进入协议实体
- ✅ Query-only 字段放入 `adapter` context

Pipeline adapter 负责：

- 从 `Query` 构造 `AgentEventContext`。
- 从 Pipeline config 构造临时 AgentBinding。
- 从旧 runner config 构造 `ctx.config`。
- 将 `max-round` 转换为 `bootstrap` policy。
- 将 Query-only 字段放入 `adapter`。

Runner 不应长期依赖 `adapter`。新 runner 应只依赖 event-first context 和 Host APIs。

## 12. 最小 v1 完成标准

Protocol v1 已在当前分支完成：

- ✅ SDK 定义 `AgentRunnerManifest`、`AgentRunContext`、`AgentRunResult`、`AgentRunAPIProxy`
- ✅ Runtime 支持 `LIST_AGENT_RUNNERS` 和 `RUN_AGENT`
- ✅ Host 支持 `run_id` session authorization
- ✅ Host 能从当前 Pipeline 入口生成 event-first context
- ✅ `messages` 降级为 optional bootstrap
- ✅ `max-round` 不出现在协议实体中
- ✅ Proxy 至少覆盖 model、tool、knowledge、state/storage
- ✅ History / event / artifact API 已落地
- ✅ EventLog / Transcript / ArtifactStore / PersistentStateStore 已落地
- ✅ 外部 harness runner 最小 smoke 已落地：Claude Code runner 能消费 event-first context、返回消息、写回 `external.session_id` / `external.working_directory`

## 13. 开放问题

- `AgentBinding` 是否需要进入 SDK 文档作为只读诊断信息，还是完全 Host 内部。
- `TranscriptItem` 的最小字段集如何定义。
- ArtifactStore 是否复用现有 BinaryStorage backend，还是引入独立实体。
- State 与 Storage 的边界是否需要更强类型。
- `platform_api` action 的审批模型如何表达。
- 多 runner 并发处理同一 event 时，result delivery 的冲突策略如何定义。
- Host 侧 scoped MCP / skill / workspace projection 是否需要从 runner config 上移为一等 resource projection API。
