# Agent-owned Context 协议设计

本文档描述插件化 AgentRunner 场景下的上下文边界。结论先行：LangBot 不应成为最终 agentic context manager；LangBot 应提供 context substrate，AgentRunner 或其背后的 agent runtime 自己决定如何管理历史、压缩、召回和 KV cache。

## 当前状态

**当前分支已落地**：

- ✅ `AgentRunContext` — event-first context 模型
- ✅ `ContextAccess` — cursor、inline policy、available APIs
- ✅ `AgentRunAPIProxy.history` — page/search API
- ✅ `AgentRunAPIProxy.events` — get/page API
- ✅ `AgentRunAPIProxy.artifacts` — metadata/read_range API
- ✅ `AgentRunAPIProxy.state` — get/set/delete API
- ✅ EventLog / Transcript / ArtifactStore — host 事实源
- ✅ PersistentStateStore — 持久化状态存储
- ✅ Host-side history window 已从 LangBot Host 语义中移除；runner 自己管理 working context
- ✅ 外部 harness context projection 已用 Claude Code runner 做 MVP 验证：context 文件、skill 投影、MCP 配置和 host-owned resume state

## 1. 设计原则

### 1.1 Agent 拥有上下文策略

不同 runner 背后的 runtime 差异很大：

- 官方 local-agent 可能依赖 LangBot 的模型、工具、知识库和存储。
- Claude Code SDK / Codex 类 runtime 可能有自己的 session、transcript、tool loop 和上下文压缩。
- Pi Agent SDK 或外部 agent 平台可能只需要当前事件和一个外部 conversation key。

因此 LangBot 不应强行决定最终传给模型的历史窗口。Host 只提供：

- 当前事件的完整结构化信息。
- 稳定身份和会话引用。
- 可授权读取的 history / event / artifact / state API。
- 可投影给外部 harness 的 scoped context、MCP、skill 和 resource refs。
- payload hard cap 和权限 guardrail。

### 1.2 Host 不定义通用历史窗口

历史窗口策略不应继续作为 AgentRunner 协议或 Pipeline adapter 的核心概念。
Host 只提供 history pull API、cursor、hard cap 和权限边界；runner 自己决定是否读取、读取多少、如何截断和压缩。

当前 official local-agent 方向是通过 Host history API 拉取 transcript，并由 runner 自己管理模型上下文。它不依赖 Pipeline adapter 下发历史窗口。

新协议不应该问“LangBot 每轮裁几轮历史给 agent”，而应该问：

- 这类 runner 是否自管 context？
- 事件到来时 host 应 inline 哪些最小信息？
- agent 需要更多上下文时通过什么 API 拉取？
- host 如何保证安全、可审计和可分页？

### 1.3 Host 保存事实源，Agent 管理 working context

三类数据要分开：

- `EventLog`: Host 保存原始事件、工具调用、投递结果、错误和系统事件。
- `Transcript`: Host 从 EventLog 投影出的对话视图，用于 UI、审计和按需历史读取。
- `Working context`: Agent 本轮实际送进模型或 runtime 的上下文，由 AgentRunner 决定。

LangBot 不再提供 host-side bootstrap window。简单 runner 如果需要历史窗口，应在 runner 内部通过 Host history API 拉取并裁剪。

## 2. Event 到来时传什么

默认 `AgentRunContext` 应尽量小且稳定：

```python
class AgentRunContext(BaseModel):
    run_id: str
    trigger: AgentTrigger
    event: AgentEventContext
    conversation: ConversationContext | None
    actor: ActorContext | None
    subject: SubjectContext | None
    input: AgentInput
    delivery: DeliveryContext
    resources: AgentResources
    context: ContextAccess
    state: AgentRunState
    runtime: AgentRuntimeContext
    config: dict[str, Any]
```

默认规则：

- Host MUST NOT inline full history by default.
- Host SHOULD inline only current event / input and context handles.
- Runner owns working-context assembly.
- Runner MAY use Host history / event / artifact / state / storage APIs when authorized.
- Official runners MUST consume Host infrastructure through the same public APIs as third-party runners.

### 2.1 必须 inline 的内容

每次 run 必须 inline：

- 当前 event 的稳定类型、id、时间、source。
- 当前输入文本和结构化内容。
- 附件 / 文件 / 图片的 metadata 和 artifact ref。
- actor、subject、conversation、thread、bot、workspace。
- delivery 能力，例如是否支持 streaming、reply target、平台限制。
- 已授权资源列表。
- context cursors 和可用 API 能力。
- Agent/runner config。

这些是 agent 决定下一步需要的最低信息。

### 2.2 默认不 inline 的内容

默认不要 inline：

- 完整历史消息。
- 大文件全文。
- 大工具结果。
- 全量知识库内容。
- 平台原始 payload 大对象。
- 每轮重新生成的大段 summary。

这些会破坏跨进程序列化成本、泄露范围、KV cache 稳定性，也会迫使 host 替 agent 做 context 策略。

### 2.3 不提供 Host Bootstrap Window

`AgentRunContext.bootstrap` 可以作为协议里的可选扩展字段保留，但 LangBot Host 默认不填历史窗口，也不通过 Pipeline 配置决定窗口大小。

如果 runner 需要类似 `recent_tail` 的策略，它应在自己的 manifest/config schema 中声明参数，并在 runner 内部通过 `history_page` / `history_search` 读取、裁剪和压缩历史。Host 只负责权限、分页、hard cap 和事实源。

## 3. ContextAccess

`ContextAccess` 是 host 交给 agent 的上下文读取入口描述：

```python
class ContextAccess(BaseModel):
    conversation_id: str | None
    thread_id: str | None
    latest_cursor: str | None
    event_seq: int | None
    transcript_seq: int | None
    has_history_before: bool
    inline_policy: InlineContextPolicy
    available_apis: ContextAPICapabilities
```

它告诉 agent：

- 当前事件位于哪条 conversation / thread。
- 若需要更多历史，从哪个 cursor 开始拉。
- host inline 了什么，没 inline 什么。
- 当前 run 有哪些 context API 权限。

## 4. Agent 如何获取更多上下文

所有 API 都必须走 `AgentRunAPIProxy`，并由 host 用 `run_id` 校验。

### 4.1 History API

```python
await api.history.page(
    conversation_id=ctx.context.conversation_id,
    before_cursor=ctx.context.latest_cursor,
    limit=50,
    direction="backward",
    include_artifacts=False,
)
```

返回：

```python
class HistoryPage(BaseModel):
    items: list[TranscriptItem]
    next_cursor: str | None
    prev_cursor: str | None
    has_more: bool
```

约束：

- `limit` 有 host hard cap。
- 默认只能读当前 conversation / thread。
- 跨会话读取必须有 manifest permission + binding policy。
- 返回 artifact ref，不默认返回大文件内容。

### 4.2 Search API

```python
await api.history.search(
    query="用户之前提到的数据库连接信息",
    filters={
        "conversation_id": ctx.context.conversation_id,
        "event_types": ["message.received"],
    },
    top_k=10,
)
```

Search 可以先用数据库全文索引，后续再接 embedding recall。它是 host 提供的检索能力，不等于 agent 的长期记忆策略。

### 4.3 Event API

```python
await api.events.get(event_id)
await api.events.page(before_cursor=..., limit=...)
```

Event API 用于读取非消息事件、工具事件、系统事件。Agent 不应把所有事件都当成 user/assistant message。

### 4.4 Artifact API

```python
await api.artifacts.metadata(artifact_id)
await api.artifacts.read_range(artifact_id, offset=0, length=65536)
await api.artifacts.open_stream(artifact_id)
```

约束：

- 校验 artifact 所属 conversation / run / binding。
- 校验 MIME、大小、过期时间和权限。
- 大文件按 range/stream 读取。
- 工具大结果也应 artifact 化。

### 4.5 State API

```python
await api.state.get(scope="conversation", key="external.session_id")
await api.state.set(scope="conversation", key="summary.checkpoint", value=...)
```

State 是可选寄宿能力。自管 runtime 可以完全不用；依附 LangBot 的官方 runner 可以使用。

### 4.6 External harness context projection

Claude Code、Codex、Kimi Code 这类 runtime 通常已经有自己的 session、工具 loop、MCP 加载、上下文压缩和工作目录。LangBot 不应把这类 runner 强行改造成“host prompt assembler”，而应提供可审计的事件和资源投影。

推荐 projection 形态：

- `agent-context.json`：结构化 JSON，包含 `run_id`、`event`、`actor`、`subject`、`input`、`delivery`、`resources`、`context`、`state`、`runtime`。
- `LANGBOT_CONTEXT.md`：人类可读摘要，用于 code-agent harness 快速理解当前 IM 事件。
- `resources`：只包含本次 run 授权后的模型、工具、知识库、artifact、state/storage 句柄，不暴露 Host 内部私有对象。
- `skills`：Host 或 binding 把已授权 skill 投影为目标 harness 可读目录，例如 Claude Code 的 `.claude/skills/<name>/SKILL.md`。
- `MCP config`：Host 或 binding 提供 scoped MCP 配置，runner adapter 转成目标 harness 的配置文件或 CLI 参数。
- `state pointers`：外部 session id、working directory、checkpoint 等小型 JSON 状态通过 Host state API 保存，例如 `external.session_id`、`external.working_directory`。

当前 Claude Code runner MVP 使用 schema `langbot.agent_runner.external_harness_context.v1`，并已通过 WebUI Debug Chat 验证 context 文件、skill 文件、MCP config 和 resume state 的基本链路。

这类 projection 是“把 LangBot 事实源和授权资源交给 harness”，不是“由 LangBot 决定最终模型上下文”。外部 harness 可以继续使用自己的 transcript、工具权限和压缩策略。

## 5. Runner manifest 中的上下文声明

建议增加：

```yaml
context:
  ownership: self_managed | host_bootstrap | hybrid
  bootstrap: none | current_event | recent_tail | summary_tail
  max_inline_events: 0
  max_inline_bytes: 0
  supports_history_pull: true
  supports_history_search: true
  supports_artifact_pull: true
  owns_compaction: true
  wants_static_context_refs: true
```

语义：

- `self_managed`: Host 不主动 inline 历史，只提供 event 和 handles。
- `host_bootstrap`: Host 为简单 runner inline 一个小窗口。
- `hybrid`: Host inline summary/tail，runner 仍可按需拉更多。
- `owns_compaction`: runner 负责压缩，host 不做语义摘要。
- `wants_static_context_refs`: host 用 ref/hash 描述静态内容，减少重复 payload。

## 6. KV cache 友好的上下文管理

如果目标是支持 Claude Code SDK、Codex、Pi Agent SDK 等 runtime，必须避免每轮由 LangBot 重组大块 prompt。

建议：

- 稳定 session key：`workspace/bot/binding/runner/conversation/thread`。
- 静态内容使用 `ref + version/hash`：system prompt、resource manifest、tool schema、platform policy。
- 每轮只传 delta：当前 event、artifact refs、少量 runtime metadata。
- 历史 append-only：不要每轮改写同一段 history 文本。
- Summary checkpoint 稳定：只有压缩发生时产生新 checkpoint，不要每轮微调。
- 大文件和工具结果 artifact 化。
- Tool/context API schema 稳定，数据通过 API 拉取，而不是塞入 prompt。
- 对自管 runtime，优先让它复用自身 session/cache，而不是强制 LangBot 每轮重放 transcript。

## 7. Host guardrail

Agent 自管 context 不代表无限制访问。LangBot 仍必须控制：

- 每次 run 的 active `run_id`。
- runner identity。
- 当前 binding 的 resource policy。
- conversation / actor / subject scope。
- page size、artifact read size、API rate limit。
- 跨会话读取权限。
- 数据脱敏和敏感变量过滤。
- 审计日志。

Host 不负责“最佳上下文策略”，但负责“不越权、不爆内存、不不可审计”。

## 8. 官方 runner 与业务编排边界

官方 runner 插件可以选择把状态寄宿在 LangBot，但它们必须和第三方 runner 一样通过公开 Host APIs 消费这些能力。

LangBot core 不应内置官方 agent 的业务流程：

- 不内置 prompt 组装策略。
- 不内置 tool loop。
- 不内置 RAG 编排策略。
- 不内置 summary / compaction 策略。
- 不内置“local-agent 专用”的状态字段。

官方 local-agent 应作为“依附 LangBot 基础设施的复杂 runner 参考实现”存在：

- transcript / history 通过 `api.history.page()` 或 `api.history.search()` 读取。
- summary、checkpoint、外部 session id、用户偏好通过 `api.state` 或 `api.storage` 保存。
- 图片、文件、工具大结果通过 `api.artifacts` 读取。
- 模型、工具、知识库通过 `api.models`、`api.tools`、`api.knowledge` 调用。

这样 LangBot 保持为通用 agent host，不变成内置 agent 框架。

## 9. 当前实现需要调整

**已完成（当前分支）**：

- ✅ Host 不再定义通用历史窗口字段或策略
- ✅ 新 runner 默认不收到历史窗口
- ✅ `AgentRunContext` 增加 `context` / cursor / access capabilities
- ✅ `AgentRunAPIProxy` 增加 history / events / artifacts / state API
- ✅ Host 增加持久 EventLog / Transcript / ArtifactStore / PersistentStateStore
- ✅ `run_from_query()` 委托到 event-first `run(event, binding)`
- ✅ Claude Code external harness smoke：context JSON / Markdown、skill、MCP config、`external.session_id` / `external.working_directory`

这样 LangBot 既能服务依附 host 基础设施的官方 runner，也能服务自带 memory/session/cache 的外部 agent runtime。
