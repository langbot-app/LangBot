# LangBot Host 与 SDK 基础设施设计

本文档描述 LangBot 和 SDK 为插件化 AgentRunner 共同提供的基础设施。它不以 Pipeline 为中心，也不以官方 local-agent 的实现方式为前提。

## 1. 目标

LangBot 要转为 agent host，而不是内置 runner 容器：

- 接收 IM、WebUI、API 和未来 EventRouter 产生的事件。
- 根据事件、bot、workspace、scope 解析应该调用的 agent binding。
- 发现、校验和调用插件提供的 AgentRunner。
- 为每次 run 提供受限资源、状态、存储、上下文引用和生命周期控制。
- 接收 AgentRunner 返回的事件流，并投递到 IM、WebUI 或其他 output surface。

SDK 要提供稳定协议：

- `AgentRunner` 组件定义。
- runner manifest / capabilities / permissions / config schema。
- `AgentRunContext` 输入 envelope。
- `AgentRunResult` 输出事件流。
- `AgentRunAPIProxy` 运行期受限 API。

## 2. 非目标

- 不把 Pipeline 当作长期架构中心。
- 不要求所有 AgentRunner 依赖 LangBot 的上下文管理。
- 不要求官方 local-agent 的旧行为反向塑造 host 协议。
- 不在 host 中实现通用 agentic prompt assembler。
- 不强制 runner 使用 LangBot state / storage；LangBot 只提供可选、受控的寄宿能力。
- **不实现 EventGateway**：EventGateway 是 future integration point，由外部 event branch 提供。本分支只定义 host-side envelope/binding models 和 `run(event, binding)` 入口。

## 3. 分层架构

目标结构：

```text
IM / WebUI / API / EventRouter (future)
        |
        v
Event Gateway (future - external event branch)
        |
        v
AgentBindingResolver
        |
        v
AgentRunOrchestrator
        |-- AgentRunnerRegistry
        |-- AgentResourceBuilder
        |-- AgentContextBuilder
        |-- AgentRunSessionRegistry
        |-- PersistentStateStore / EventLogStore / TranscriptStore / ArtifactStore
        v
Plugin Runtime / AgentRunner
        |
        v
AgentRunResult stream
        |
        v
Delivery / Renderer / Platform API
```

**当前状态**：
- `PipelineAdapter` 作为当前入口 adapter，将 Pipeline Query 转换为 `AgentEventEnvelope` + `AgentBinding`
- `run_from_query()` 内部委托到 `run(event, binding)`
- EventLog / Transcript / ArtifactStore / PersistentStateStore 已落地
- `local-agent` 与 Claude Code runner 已通过本地 WebUI smoke，验证同一条 `run(event, binding)` path 可服务 host-infra runner 与外部 harness runner
- EventGateway 由外部 event branch 实现

当前 Pipeline 只应接入在 Pipeline adapter 位置。它可以继续产生 `message.received`，但不应继续拥有 runner 选择、上下文裁剪和业务 agent 执行的核心语义。

## 4. LangBot 侧能力

### 4.1 Event Gateway（Future Integration Point）

> **注意**：EventGateway 由外部 event branch 实现，不在本分支范围。本分支只预留 event-first 入口和 envelope/binding models。

Event Gateway 将负责把入口统一成 host event：

- IM 平台消息。
- WebUI debug chat 消息。
- API 触发。
- 后续非消息事件，例如入群、撤回、好友申请。

输出应是稳定 envelope，而不是 Pipeline Query 私有结构：

```python
class AgentEventEnvelope(BaseModel):
    event_id: str
    event_type: str
    event_time: int | None
    source: str
    bot_id: str | None
    workspace_id: str | None
    conversation_id: str | None
    thread_id: str | None
    actor: ActorRef | None
    subject: SubjectRef | None
    input: AgentInput
    delivery: DeliveryContext
    raw_ref: RawEventRef | None
```

**当前 adapter source**：`PipelineAdapter.query_to_event(query)` 从 Pipeline Query 生成 `AgentEventEnvelope`。

原始平台 payload 可以存为 raw event 或 artifact ref；不要把平台私有字段直接扩散到 AgentRunner 顶层协议。

### 4.2 Agent Binding

Agent binding 是”什么事件调用哪个 runner、带什么绑定配置”的持久配置。它替代长期依赖 Pipeline runner config 的角色。

建议模型：

```python
class AgentBinding(BaseModel):
    binding_id: str
    scope: BindingScope
    event_types: list[str]
    runner_id: str
    runner_config: dict[str, Any]
    resource_policy: ResourcePolicy
    state_policy: StatePolicy
    delivery_policy: DeliveryPolicy
    enabled: bool
```

**当前 adapter source**：`PipelineAdapter.pipeline_config_to_binding(query, runner_id)` 从 Pipeline config 生成临时 `AgentBinding`。

Pipeline 当前可以被迁移为一种 binding source：

- Pipeline AI runner config -> `AgentBinding`
- Pipeline extension preference -> `resource_policy`
- Pipeline output settings -> `delivery_policy`

但新设计不应再把这些字段命名为 Pipeline 专属概念。

### 4.3 AgentRunnerRegistry

Registry 负责收集 runner descriptor：

- 插件 runtime 提供的 `AgentRunner`。
- 可能存在的 host adapter runner。
- 开发期本地插件 runner。

Descriptor 必须包含：

```python
class AgentRunnerDescriptor(BaseModel):
    id: str
    source: Literal["plugin", "host_adapter"]
    label: I18nObject
    description: I18nObject | None = None
    capabilities: AgentRunnerCapabilities
    permissions: AgentRunnerPermissions
    config_schema: list[DynamicFormItemSchema]
    plugin: PluginRef | None = None
```

`plugin:author/name/runner` 仍可作为稳定 id 格式。多个 binding 指向同一个 runner id 时，不创建多个插件实例。

### 4.4 AgentRunOrchestrator

Orchestrator 是唯一运行入口：

```text
run(event, binding)
  -> resolve runner descriptor
  -> build resources
  -> build context
  -> register run session
  -> call plugin runtime
  -> normalize result stream
  -> update state
  -> unregister run session
```

它负责：

- `run_id` 生成和生命周期。
- timeout / deadline / cancellation。
- 插件异常隔离。
- result schema 校验和大小限制。
- state.updated 处理。
- delivery backpressure 和 telemetry。

`run_from_query()` 这类 API 可以保留为 Pipeline adapter 入口，但内部应转换成 event + binding 后走统一 `run()`。

### 4.5 Resource Authorization

LangBot 在每次 run 前生成 `ctx.resources`。资源来自三层约束：

- runner manifest 声明的 permissions。
- binding/resource policy 允许的资源范围。
- 当前 event / actor / bot / workspace 的实际权限。

资源类型包括：

- models
- tools
- knowledge bases
- files / artifacts
- storage
- platform capabilities
- history / transcript access

运行期 action 必须再次通过 `run_id` 校验。SDK 侧本地校验只用于开发体验，host 侧校验才是安全边界。

### 4.6 State 与 Storage

LangBot 可以提供 host-owned state，让 AgentRunner 把状态寄宿在 LangBot：

- conversation state
- actor state
- subject state
- runner/binding state
- workspace state

但这不是强制。外部 agent runtime 可以维护自己的 session 和 memory。LangBot 只需要提供：

- 授权开关。
- scope key。
- get/set/list/delete API。
- 持久化 backend。
- 审计和清理策略。

当前进程内 state store 只能作为过渡实现，不能作为正式生产语义。

### 4.7 EventLog / Transcript / Artifact

LangBot 应提供事实源能力：

- `EventLog`: 保存原始事件、系统事件、工具调用、投递结果、错误。
- `Transcript`: 面向对话 UI / agent history 的消息投影。
- `ArtifactStore`: 保存大文件、多模态输入、工具大结果、平台附件。

AgentRunner 可以读取这些能力，但不能被迫使用 LangBot 作为唯一记忆系统。

### 4.8 External harness resource projection

Claude Code、Codex、Kimi Code 等外部 harness runner 可能不会直接调用 LangBot 的 model/tool loop，而是把 LangBot 事件和授权资源投影到自己的 harness 中执行。Host 侧仍要保持统一边界：

- Host 负责构造 event-first context、资源授权、state/storage、EventLog/Transcript/ArtifactStore 和审计。
- Host 或 binding policy 负责决定哪些 MCP server、skill、artifact、history/state 句柄可以投影给 runner。
- Runner plugin 负责把 scoped projection 转成目标 harness 可消费的形式，例如 context JSON/Markdown、MCP config、skill 目录、环境变量或 CLI 参数。
- 外部 harness 负责自己的 native session、tool loop、压缩、权限模式和 resume 机制。

当前 Claude Code runner MVP 已验证：

- LangBot event-first context 可以写入 `agent-context.json` / `LANGBOT_CONTEXT.md`。
- binding 中的 skill / MCP 配置可以投影到 Claude Code 原生目录和 CLI 参数。
- `external.session_id` 与 `external.working_directory` 可以通过 Host state 保存并用于 resume。

发布级路径隔离、secret 过滤、MCP allowlist、工具白名单、资源配额和 workspace 清理不属于当前协议闭环，详见 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md)。

## 5. SDK 侧协议

### 5.1 AgentRunner 组件

```python
class AgentRunner(BaseComponent):
    __kind__ = "AgentRunner"

    @classmethod
    def get_capabilities(cls) -> AgentRunnerCapabilities:
        ...

    @classmethod
    def get_config_schema(cls) -> list[dict]:
        ...

    async def run(self, ctx: AgentRunContext) -> AsyncGenerator[AgentRunResult, None]:
        ...
```

### 5.2 Capabilities

建议能力声明：

```yaml
capabilities:
  streaming: true
  tool_calling: true
  knowledge_retrieval: true
  multimodal_input: true
  event_context: true
  platform_api: false
  interrupt: true
  stateful_session: true
  self_managed_context: true
  host_state: optional
```

`self_managed_context` 表示 runner 或外部 runtime 自己管理上下文。Host 不应给它强塞历史窗口，只提供当前事件和 context handles。

### 5.3 Permissions

```yaml
permissions:
  models: ["invoke", "stream", "rerank"]
  tools: ["detail", "call"]
  knowledge_bases: ["list", "retrieve"]
  history: ["page", "search"]
  artifacts: ["metadata", "read"]
  storage: ["plugin", "workspace", "binding"]
  platform_api: []
```

权限声明是 runner 需要的最大能力，实际可用资源仍由 binding 和当前运行上下文裁剪。

### 5.4 AgentRunContext

Context 顶层应是 event-first，而不是 Query-first：

```python
class AgentRunContext(BaseModel):
    run_id: str
    trigger: AgentTrigger
    event: AgentEventContext
    conversation: ConversationContext | None = None
    actor: ActorContext | None = None
    subject: SubjectContext | None = None
    input: AgentInput
    resources: AgentResources
    context: ContextAccess
    state: AgentRunState
    runtime: AgentRuntimeContext
    config: dict[str, Any]
```

`messages` 可以作为兼容字段或 bootstrap 字段，但不应继续是协议核心。

### 5.5 AgentRunResult

输出应是事件流：

```python
class AgentRunResult(BaseModel):
    type: Literal[
        "message.delta",
        "message.completed",
        "tool.call.started",
        "tool.call.completed",
        "state.updated",
        "artifact.created",
        "action.requested",
        "run.completed",
        "run.failed",
    ]
    data: dict[str, Any] = {}
```

当前消息回复只消费 `message.delta` / `message.completed` / `run.failed`。平台动作执行等 EBA 和 platform API 权限落地后再启用。

### 5.6 AgentRunAPIProxy

Proxy 是 runner 访问 host 能力的唯一入口：

- model APIs
- tool APIs
- knowledge APIs
- state / storage APIs
- history / event APIs
- artifact APIs
- platform APIs

所有请求必须带 `run_id`，host 侧按 active run session 验证 runner identity 和 resource ACL。

## 6. 当前实现与目标差距

**已落地（当前分支）**：

- ✅ `AgentRunnerRegistry`
- ✅ `AgentRunOrchestrator` — event-first `run(event, binding)`
- ✅ `AgentRunContextBuilder` — event-first context
- ✅ `AgentResourceBuilder`
- ✅ `AgentRunSessionRegistry`
- ✅ `AgentRunAPIProxy` — model / tool / knowledge / history / event / artifact / state APIs
- ✅ `PipelineAdapter` — Query → Event + Binding
- ✅ `AgentBinding` 抽象
- ✅ `AgentEventEnvelope` 抽象
- ✅ `max-round` 从目标设计中移除，只在 Pipeline adapter 中处理
- ✅ `PersistentStateStore` — 持久化状态存储
- ✅ `EventLogStore` / `TranscriptStore` / `ArtifactStore`
- ✅ history / artifact / event 的受限拉取 API
- ✅ Claude Code external harness MVP：context/resource projection 与 host-owned resume state smoke

**其他分支负责（非本分支范围）**：

- EventGateway 实现
- EventRouter 实现
- AgentBinding 持久化 UI
- platform API 动作执行
- 发布级 security hardening

## 7. 落地顺序

**已完成**：

1. ✅ 固化 README 路由和专题文档边界。
2. ✅ 在 Host 中抽象 `AgentBinding`，由 Pipeline adapter 生成。
3. ✅ 将 `AgentRunContextBuilder` 改为 event-first。
4. ✅ 增加持久 transcript/event log/artifact/state 存储模型。
5. ✅ 扩展 `AgentRunAPIProxy` 的 history / artifact / state API。
6. ✅ 将 Pipeline-only 字段下沉到 Pipeline adapter。
7. ✅ 官方 runner 插件迁移完成（7 个插件）。
8. ✅ Claude Code runner MVP smoke：外部 harness context 投影和 state handoff。

**后续工作（其他分支）**：

- EventGateway 实现
- EventRouter 与 BindingResolver 集成
- 平台动作执行器
