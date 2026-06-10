# LangBot AgentRunner Protocol v1

本文档是 LangBot Host 与插件 SDK / Runtime / AgentRunner 之间协议合同的**唯一规范来源（single source of truth）**。

- 本文件描述"稳定接口应是什么"，是 normative spec，不混入实现进度。实现状态见 [PROGRESS.md](./PROGRESS.md)。
- 本文件之外的任何文档**不得重新定义这里的数据结构**，只能引用，例如"见 PROTOCOL_V1 §4.2"。
- Host 内部模型（`AgentEventEnvelope`、`AgentBinding`、Descriptor、各 Store）不属于 SDK 协议，定义在 [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md)。

## 1. 协议目标

Protocol v1 只解决四件事：

- LangBot 如何发现插件提供的 AgentRunner。
- LangBot 如何把一次事件调用封装成 `AgentRunContext`。
- AgentRunner 如何以事件流形式返回运行结果。
- AgentRunner 如何通过受限 API 访问 LangBot host 能力。

Protocol v1 **不定义**：

- LangBot 内部如何持久化 `AgentBinding`（见 HOST_SDK）。
- AgentRunner 内部如何组装 prompt、压缩历史、管理 memory（见 [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md)）。
- 官方 runner 的具体实现（见 [OFFICIAL_RUNNER_PLUGINS.md](./OFFICIAL_RUNNER_PLUGINS.md)）。
- Pipeline 的长期配置模型。
- 发布级安全 hardening 的完整实现（见 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md)）。

## 2. 参与方

| 名称 | 职责 |
| --- | --- |
| LangBot Host | 事件入口、绑定解析、权限、资源、存储、生命周期、结果投递。 |
| Plugin Runtime | 加载插件，响应 Host 的 runner discovery 和 run 调用。 |
| AgentRunner | 插件提供的 agent 执行组件。 |
| AgentRunAPIProxy | AgentRunner 访问 Host 能力的受限 API。 |
| AgentBinding | Host 内部的事件到 runner 绑定配置，不直接暴露给 SDK（见 HOST_SDK §4.2）。 |

产品层的 `Agent` 替代旧 Pipeline 承载 agent 配置：bot / IM channel
绑定一个 Agent，一个 Agent 可以被多个 bot / channel 复用。Host 内部的
`AgentBinding` 是一次事件运行前解析出的有效绑定，只影响 Host 构造出的
`ctx.config`、`ctx.resources`、`ctx.context` 和 `ctx.delivery`。SDK 不需要知道
Agent / binding 的持久化形态。

外部 harness runner（Claude Code、Codex、Kimi Code 等）也是 `AgentRunner`：它们消费 event-first `AgentRunContext`、返回 `AgentRunResult`，并通过 Host 授权的 state/storage/artifact API 保存跨轮次指针。它们内部可以继续使用自己的 session、tool loop、MCP、上下文压缩和权限模型。

## 3. 协议演进

当前 AgentRunner 合同不暴露显式 `protocol_version` 字段。协议演进先按字段级兼容规则处理：

- 新增可选字段保持向后兼容。
- 删除字段或改变既有字段语义，需要在 SDK 发布前完成；发布后应走新的显式兼容方案。
- 结果流演进：Host **必须忽略未知 result type 并记录 warning**（除非该 type 明确要求强校验）。新增 result type 不提升大版本。

## 4. Discovery 协议

### 4.1 LIST_AGENT_RUNNERS

Host 调用 Plugin Runtime 获取当前插件暴露的 runner 列表，请求无额外 payload。返回：

```python
class ListAgentRunnersResponse(BaseModel):
    runners: list[AgentRunnerManifest]
```

### 4.2 AgentRunnerManifest

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

- `id` 必须稳定，格式 `plugin:author/name/runner`。
- `name` 是插件内 runner 名称，例如 `default`。
- `config_schema` 只描述绑定配置表单，不代表插件实例状态。
- `metadata` 只放展示、诊断、非稳定扩展信息。

### 4.3 Capabilities

```python
class AgentRunnerCapabilities(BaseModel):
    streaming: bool = False
    tool_calling: bool = False
    knowledge_retrieval: bool = False
    multimodal_input: bool = False
    skill_authoring: bool = False
    event_context: bool = True
    platform_api: bool = False
    interrupt: bool = False
    stateful_session: bool = False
    self_managed_context: bool = True
```

语义：

- `streaming`: runner 可以返回 `message.delta`。
- `tool_calling`: runner 可能调用 Host tool API。
- `knowledge_retrieval`: runner 可能调用 Host knowledge API。
- `multimodal_input`: runner 可以处理非纯文本 input / artifact。
- `skill_authoring`: runner 需要 Host 提供 skill facts 以及 skill authoring tools，例如 `activate` / `register_skill`。
- `event_context`: runner 理解 event-first 输入。
- `platform_api`: runner 可能请求平台动作。
- `interrupt`: runner 支持取消或中断。
- `stateful_session`: runner 可能维护跨 run 会话状态。
- `self_managed_context`: runner 自己管理 working context，Host 不应默认 inline 历史。

> Capabilities 字段全部是 `bool`。runner 是否寄宿 host-owned state **不在 capabilities 表达**，而通过 `permissions.storage` 声明（见 §4.4），避免出现非 bool 取值。

### 4.4 Permissions

```python
class AgentRunnerPermissions(BaseModel):
    models: list[Literal["invoke", "stream", "rerank"]] = []
    tools: list[Literal["detail", "call"]] = []
    knowledge_bases: list[Literal["list", "retrieve"]] = []
    history: list[Literal["page", "search"]] = []
    events: list[Literal["get", "page"]] = []
    artifacts: list[Literal["metadata", "read"]] = []
    storage: list[Literal["plugin", "workspace", "binding"]] = []
    files: list[Literal["config", "knowledge"]] = []
    platform_api: list[str] = []
```

Manifest permissions 是 runner 需要的**最大能力**。实际可用资源还要经过 Host binding policy 和当前 run scope 裁剪（三层裁剪见 HOST_SDK §4.5）。

### 4.5 Context Policy

```python
class AgentRunnerContextPolicy(BaseModel):
    supports_history_pull: bool = True
    supports_history_search: bool = False
    supports_artifact_pull: bool = True
    owns_compaction: bool = True
    wants_static_context_refs: bool = True
```

Host 不使用该声明给 runner inline 历史窗口。默认原则：

- Host 不得默认 inline 全量历史。
- Host 只 inline 当前 event / input 和 context handles。
- Runner 拥有 working context assembly。
- Runner 可在授权后通过 Host history / event / artifact / state API 拉取更多上下文。
- 历史窗口策略不属于 Protocol v1 字段，也不属于 Host 通用语义。

context 边界的设计理由见 [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md)。

## 5. Run 协议

### 5.1 RUN_AGENT

Host 调用 Runtime：

```python
class AgentRunRequest(BaseModel):
    runner_id: str
    runner_name: str
    context: AgentRunContext
```

Runtime 返回 `AgentRunResult` 异步流。底层 transport 可继续用 `plugin_author` / `plugin_name` / `runner_name` 定位组件，但协议语义以 `runner_id` 和 `context` 为准。

### 5.2 AgentRunContext

这是 SDK 看到的**唯一权威 context 定义**。

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
    adapter: AdapterContext | None = None
    metadata: dict[str, Any] = {}
```

核心约束：

- `event` 是必选字段，Protocol v1 是 event-first。
- `input` 表示当前事件的主输入，不等于历史消息。
- `bootstrap` / `messages` **不是协议字段**；Host 不内联历史窗口。
- `adapter` 只放入口 adapter 的非核心元数据，runner 不应依赖它做长期能力。
- `config` 是 Agent/runner config，不是插件实例状态。

### 5.3 AgentTrigger

```python
class AgentTrigger(BaseModel):
    type: str
    source: Literal["platform", "webui", "api", "scheduler", "system", "host_adapter"]
    timestamp: int | None = None
```

`trigger.type` 应与 `event.event_type` 一致或更粗粒度。例如入口适配器触发消息时：

```json
{ "type": "message.received", "source": "host_adapter" }
```

### 5.4 AgentEventContext

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

- `event_type` 使用 LangBot 稳定协议名，例如 `message.received`。稳定事件名清单见 [EVENT_BASED_AGENT.md](./EVENT_BASED_AGENT.md)。
- 平台原始事件名放入 `source_event_type`。
- 大型原始 payload 必须放入 `raw_ref` 或 artifact，不应直接塞入 `data`。

### 5.5 Conversation / Actor / Subject

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

### 5.6 AgentInput

```python
class AgentInput(BaseModel):
    text: str | None = None
    contents: list[ContentElement] = []
    attachments: list[ArtifactRef] = []
    message_chain: dict[str, Any] | None = None
```

- 文本、多模态、附件都属于当前 event input。
- 大文件、图片、音频、工具大结果应以 artifact ref 传递。
- `message_chain` 是平台兼容字段，不应成为长期稳定依赖。

### 5.7 DeliveryContext

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

Runner 可参考 delivery 能力决定返回 `message.delta`、`message.completed` 或 `action.requested`。

### 5.8 ContextAccess

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

`ContextAccess` 告诉 runner：Host inline 了什么、没 inline 什么、需要更多上下文时走哪些 API。它是 runner 按需读取上下文的入口说明，不是 Host 的业务上下文编排策略。

### 5.9 AgentRuntimeContext

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

`static_refs` 用于 KV cache 友好的静态上下文引用（system policy、tool schema、resource manifest 的 hash/version）。理由见 AGENT_CONTEXT_PROTOCOL §6。

### 5.10 AgentRunState

```python
class AgentRunState(BaseModel):
    conversation: dict[str, Any] = {}
    actor: dict[str, Any] = {}
    subject: dict[str, Any] = {}
    runner: dict[str, Any] = {}
```

State 是可选 host-owned snapshot。Runner 也可以完全自管状态。

## 6. Resources

```python
class SkillResource(BaseModel):
    skill_name: str
    display_name: str | None = None
    description: str | None = None

class AgentResources(BaseModel):
    models: list[ModelResource] = []
    tools: list[ToolResource] = []
    knowledge_bases: list[KnowledgeBaseResource] = []
    skills: list[SkillResource] = []
    files: list[FileResource] = []
    storage: StorageResource = StorageResource()
    platform_capabilities: dict[str, Any] = {}
```

`skills` 只包含本次 run 中 pipeline-visible 的 skill facts，例如 `skill_name`、`display_name` 和 `description`。Host 不把这些 facts 追加到 system prompt，也不把它们编排进工具描述；runner 可以自行决定是否放入 model prompt、转换成 MCP surface，或只在自己的策略层使用。

资源列表是本次 run 的授权结果。History / Event / Artifact 访问通过 permissions、`ctx.context.available_apis` 和 Host 侧 run session 校验控制，不作为可枚举 resource list 暴露。Runner 只能通过 `AgentRunAPIProxy` 访问这些能力。

## 7. Result Stream

### 7.1 AgentRunResult envelope

```python
JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]

ResultType = Literal[
    "message.delta",
    "message.completed",
    "tool.call.started",
    "tool.call.completed",
    "artifact.created",
    "state.updated",
    "action.requested",
    "run.completed",
    "run.failed",
]

class AgentRunResultBase(BaseModel):
    run_id: str
    sequence: int | None = None
    timestamp: int | None = None
    metadata: dict[str, Any] = {}
```

`AgentRunResult` 是以下 typed result 的 discriminated union。Host 必须按 `type` 校验对应 `data` 结构；未知 `type` 按 §3 版本演进规则忽略并记录 warning。

### 7.2 稳定 result payloads

```python
class AssistantMessageChunk(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    contents: list[ContentElement] = []
    metadata: dict[str, Any] = {}

class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    contents: list[ContentElement] = []
    artifacts: list[ArtifactRef] = []
    metadata: dict[str, Any] = {}

class MessageDeltaData(BaseModel):
    chunk: AssistantMessageChunk

class MessageCompletedData(BaseModel):
    message: AssistantMessage

class ToolCallStartedData(BaseModel):
    tool_call_id: str
    tool_name: str
    parameters: dict[str, Any] = {}

class ToolCallCompletedData(BaseModel):
    tool_call_id: str
    tool_name: str
    result_preview: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None

class ArtifactCreatedData(BaseModel):
    artifact: ArtifactRef

class StateUpdatedData(BaseModel):
    scope: Literal["conversation", "actor", "subject", "runner", "binding", "workspace"]
    key: str
    value: JSONValue

class ActionRequestedData(BaseModel):
    action: str
    target: dict[str, Any]
    payload: dict[str, Any] = {}
    idempotency_key: str | None = None
    approval_hint: str | None = None

class RunCompletedData(BaseModel):
    finish_reason: str = "stop"
    message: AssistantMessage | None = None
    usage: dict[str, Any] = {}

class RunFailedData(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = {}

class MessageDeltaResult(AgentRunResultBase):
    type: Literal["message.delta"]
    data: MessageDeltaData

class MessageCompletedResult(AgentRunResultBase):
    type: Literal["message.completed"]
    data: MessageCompletedData

class ToolCallStartedResult(AgentRunResultBase):
    type: Literal["tool.call.started"]
    data: ToolCallStartedData

class ToolCallCompletedResult(AgentRunResultBase):
    type: Literal["tool.call.completed"]
    data: ToolCallCompletedData

class ArtifactCreatedResult(AgentRunResultBase):
    type: Literal["artifact.created"]
    data: ArtifactCreatedData

class StateUpdatedResult(AgentRunResultBase):
    type: Literal["state.updated"]
    data: StateUpdatedData

class ActionRequestedResult(AgentRunResultBase):
    type: Literal["action.requested"]
    data: ActionRequestedData

class RunCompletedResult(AgentRunResultBase):
    type: Literal["run.completed"]
    data: RunCompletedData

class RunFailedResult(AgentRunResultBase):
    type: Literal["run.failed"]
    data: RunFailedData

AgentRunResult = (
    MessageDeltaResult
    | MessageCompletedResult
    | ToolCallStartedResult
    | ToolCallCompletedResult
    | ArtifactCreatedResult
    | StateUpdatedResult
    | ActionRequestedResult
    | RunCompletedResult
    | RunFailedResult
)
```

### 7.3 稳定 result types

| type | 说明 | 当前消费 |
| --- | --- | --- |
| `message.delta` | 流式消息片段。 | ✅ |
| `message.completed` | 完整消息。 | ✅ |
| `tool.call.started` | 工具调用开始的可观测事件。 | telemetry |
| `tool.call.completed` | 工具调用完成的可观测事件。 | telemetry |
| `artifact.created` | runner 生成 artifact。 | ✅ |
| `state.updated` | runner 请求更新 host-owned state。 | ✅ |
| `action.requested` | runner 请求 Host 执行平台动作。 | **reserved / 仅 telemetry，不执行** |
| `run.completed` | run 正常结束。 | ✅ |
| `run.failed` | run 失败。 | ✅ |

`action.requested` 是为 EBA 和 platform API 保留的协议表面：本分支 Host 收到后只记 telemetry，**不执行**，runner 作者不应在当前 Host 底座中依赖其副作用。真实执行器由外部 EBA / platform action 分支接入；执行模型见 EVENT_BASED_AGENT §6。

Host 必须校验 `state.updated` 的 scope、key、value 大小和 JSON 可序列化性。`action.requested` 如果请求未来会产生外部副作用，runner 必须提供稳定 `idempotency_key`；本分支 Host 仍只记录 telemetry。

### 7.4 Stream delivery semantics

- Host 按 Runtime stream 顺序消费 result。当前 v1 不定义跨连接 replay，也不承诺 at-least-once；从 Host 视角，收到的 result 最多应用一次。
- `sequence` 是单个 `run_id` 内的结果序号。in-process / stdio 这类天然有序的在线 stream 可以省略；任何会缓冲、重放、跨进程队列或 runtime-managed task 的 transport 必须提供从 1 开始严格递增的 `sequence`。
- Host 看到已提供 `sequence` 的 result 时，应按 `(run_id, sequence)` 做重复检测，并在缺号或乱序时记录 warning；除非 transport 明确声明 replay 语义，Host 不应自行等待缺失序号重排用户可见输出。
- `run.failed.data.retryable` 只表示整次 run 理论上可由上层重试；Protocol v1 不自动重试 run，也不自动重试 proxy action。任何未来自动重试的 side-effecting action 必须依赖 `idempotency_key` 或等价 Host-owned 去重键。
- History / Event / Transcript cursor 是 opaque token。runner 不得解析 cursor，也不得假设 cursor 在不同 API、conversation、thread 或 retention window 之间可比较；当前实现即使返回数字字符串，也只是实现细节。

### 7.5 示例

```json
{ "type": "message.delta",     "data": { "chunk": { "role": "assistant", "content": "hel" } } }
{ "type": "message.completed", "data": { "message": { "role": "assistant", "content": "hello" } } }
{ "type": "state.updated",     "data": { "scope": "conversation", "key": "external.session_id", "value": "abc" } }
{ "type": "action.requested",  "data": { "action": "message.edit", "target": {"message_id": "..."}, "payload": {"text": "..."}, "idempotency_key": "run_1:edit:msg_1" } }
```

## 8. AgentRunAPIProxy

所有 proxy action 必须携带 `run_id`。Host 必须校验：active run session 存在、caller plugin identity 匹配、resource 在本次 `ctx.resources` 中授权、scope 不越界、payload size / rate limit / deadline 合法。

```python
# Model
await api.invoke_llm(model_id, messages, funcs=None, extra_args=None)
async for chunk in api.invoke_llm_stream(model_id, messages, funcs=None, extra_args=None):
    ...
await api.invoke_rerank(rerank_model_id, query, documents, top_k=None)

# Tool
await api.get_tool_detail(tool_name)
await api.call_tool(tool_name, parameters)

# Knowledge
await api.retrieve_knowledge(kb_id, query_text, top_k=5, filters=None)

# History（返回 Transcript projection，不返回原始平台 payload）
await api.history_page(conversation_id=None, before_cursor=None, after_cursor=None,
                       limit=50, direction="backward", include_artifacts=False)
await api.history_search(query, filters=None, top_k=10)

# Event（返回稳定 event envelope 或受限 raw ref，不默认返回大 payload）
await api.event_get(event_id)
await api.event_page(before_cursor=None, limit=50)

# Artifact（必须支持大小限制、MIME 校验、过期时间和授权范围）
await api.artifact_metadata(artifact_id)
await api.artifact_read_range(artifact_id, offset=0, length=65536)

# State / Storage
await api.state_get(scope, key);   await api.state_set(scope, key, value);   await api.state_delete(scope, key)
await api.state_list(scope, prefix=None)
await api.get_plugin_storage(key); await api.set_plugin_storage(key, value); await api.delete_plugin_storage(key)
await api.get_workspace_storage(key); await api.set_workspace_storage(key, value); await api.delete_workspace_storage(key)
```

`state` 与 `storage` 的建议边界：`state` 放小型 JSON（conversation / actor / runner / binding），`storage` 放 blob 或较大数据（插件私有数据、workspace 数据、checkpoint）。

返回数据结构（如 `HistoryPage`、artifact metadata）见 AGENT_CONTEXT_PROTOCOL §4。

## 9. 错误模型

```python
class AgentAPIError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = {}
```

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
{ "type": "run.failed", "data": { "code": "runner.error", "message": "failed to call external agent", "retryable": false } }
```

## 10. Timeout 与 Cancellation

- Host 在 `ctx.runtime.deadline_at` 下发总 deadline；SDK proxy 必须用该 deadline 限制单次 action timeout。
- Host 可以取消 active run；Runtime 应尽力中断 runner。
- Protocol v1 的 run 绑定当前 Host 进程和当前 runtime channel，不保证跨 Host 重启恢复。Host 重启、runtime channel 断开或 run session 丢失时，Runtime / remote daemon 必须 fail-fast 并尽力取消仍在执行的 runner，不得继续使用旧 `run_id` 调用 Host API。
- Runner 支持中断时应返回或触发 `run.failed`，code 为 `cancelled`。
- Host 必须 unregister active run session。

## 11. Security 与 Guardrail（协议层）

Protocol v1 的安全边界在 Host：

- Runner 不能直接访问未授权 model/tool/kb/history/artifact/storage。
- SDK 本地校验只提升开发体验，不能替代 Host 校验。
- 所有 resource id 对 runner 来说都是 opaque。
- 默认只能访问当前 conversation / thread 的 history；跨会话、workspace 级访问必须额外授权。
- 大 payload 必须 artifact 化。
- Host 必须记录 run_id、runner_id、action、resource、scope、result。

Host 不负责业务编排：不拼接全量历史、不替 runner 做 prompt assembly、不内置 agent memory / tool loop / 上下文压缩策略。这些由官方或第三方 AgentRunner 插件实现。

对外部 harness runner，Host 在调用前完成 binding/resource policy 裁剪、路径策略、secret 过滤和审计；runner plugin 把授权后的 context/resource projection 适配为目标 harness 的形式；harness 的 native permission mode、allowed/disallowed tools 只是额外执行约束，不能替代 Host 授权。

> 发布级路径隔离、MCP allowlist、secret redaction、配额、workspace 清理等**不属于** v1 协议闭环，是生产默认启用前的 release gate，见 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md)。

## 12. Pipeline Adapter 边界

Pipeline 是当前入口 adapter，不是协议中心。目标产品模型中 Agent 会替代
Pipeline 承载 runner config、resource policy 和 delivery policy；当前 Query
entry adapter 只是迁移桥。它负责：

- 从 `Query` 构造 `AgentEventContext` 和临时 `AgentBinding`（见 HOST_SDK §4.2）。
- 从当前 Agent/runner config 构造 `ctx.config`。
- 将 Query-only 字段放入 `ctx.adapter`，例如 filtered params 放 `ctx.adapter.extra["params"]`。

约束：

- adapter **不**定义历史窗口、prompt 组装或 agentic context 策略。
- `ctx.adapter.extra` 只允许承载一次性、JSON-safe、入口相关的非核心元数据，例如 `params`；不得承载 `prompt`、history window、RAG 结果、tool schema 或授权资源。
- 静态绑定 prompt 属于 `ctx.config.prompt`。preprocessing / hook 后的动态有效指令不通过 `ctx.adapter.extra` 主动推送；后续如需要保留这类能力，应通过 Host prompt/instruction pull API 暴露（占位见 HOST_SDK §4.8）。
- 新 runner 不应长期依赖 `adapter`，应只依赖 event-first context 和 Host API。

## 13. 已确认约束

- v1 / EBA 主线是 `one event -> one AgentBinding -> one run_id -> one runner`。
- 一个 bot / IM channel 在同一时间只绑定一个负责 agentic 处理的 Agent；一个 Agent 可以被多个 bot / channel 复用。
- 如果配置层出现多个匹配 AgentBinding，BindingResolver 必须按明确规则选出一个或拒绝配置，不应默认 fan-out。
- observer agent、多 runner fan-out、并行裁决、result 合并等能力需要单独设计 delivery、state、platform action 和 audit 语义，不属于当前 v1 契约。
- `AgentRunnerDescriptor.source` 只允许 `plugin`；Host 内置 adapter 不能作为 runner source 绕过插件/runtime/proxy 权限链。
- `ctx.resources` 与 proxy action 校验必须来自同一个 run authorization snapshot；runtime handler 不应重新执行资源裁剪。
- v1 不要求 Agent、AgentRunner 插件实例或 runner id 全局串行。多个 bot / channel 可复用同一个 Agent；并发隔离依赖 `run_id`、binding、conversation / thread scope 和 Host authorization snapshot。
- 对 `stateful_session` runner，若外部 runtime 不支持同一 session 并发 turn，串行化粒度应是稳定的 external session key（例如 workspace / bot / binding / runner / conversation / thread / external session id），不是 Agent 或插件实例全局锁。
- 外部 harness runner 当前是 MVP / dev path，证明协议可接入，不代表发布级安全边界或 Docker 生产可用性完成。

## 14. 开放问题

- `AgentBinding` 是否需要进入 SDK 文档作为只读诊断信息，还是完全 Host 内部。
- `TranscriptItem` 的最小字段集如何定义。
- ArtifactStore 是否复用现有 BinaryStorage backend，还是引入独立实体。
- State 与 Storage 的边界是否需要更强类型。
- `platform_api` action 的审批模型如何表达。
- Host 侧 scoped MCP / skill / workspace projection 是否需要从 runner config 上移为一等 resource projection API。
