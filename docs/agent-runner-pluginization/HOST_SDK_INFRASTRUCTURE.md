# LangBot Host 与 SDK 基础设施设计

本文档描述 LangBot 作为 agent host 的内部能力与分层架构，以及 Host 内部模型。

- SDK ↔ Host 的协议数据结构（`AgentRunContext`、`AgentRunnerManifest`、`AgentRunResult`、`AgentRunAPIProxy` 等）的**唯一定义在** [PROTOCOL_V1.md](./PROTOCOL_V1.md)；本文只引用，不重抄。
- 测试执行入口和 smoke 记录见 [AGENT_RUNNER_QA_GUIDE.md](./AGENT_RUNNER_QA_GUIDE.md)；安全发布门槛见 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md)。
- 本文定义的 Host 内部模型（`AgentEventEnvelope`、`AgentBinding`、`AgentRunnerDescriptor`）不属于 SDK 协议字段。

## 1. 目标

LangBot 要转为 agent host，而不是内置 runner 容器：

- 接收 IM、WebUI、API 和外部 EBA 分支 EventRouter 产生的事件。
- 根据事件、bot、workspace、scope 解析应该调用的 Agent / agent binding。
- 发现、校验和调用插件提供的 AgentRunner。
- 为每次 run 提供受限资源、状态、存储、上下文引用和生命周期控制。
- 接收 AgentRunner 返回的事件流，投递到 IM、WebUI 或其他 output surface。

## 2. 非目标

- 不把 Pipeline 当作长期架构中心。
- 不要求所有 AgentRunner 依赖 LangBot 的上下文管理。
- 不要求官方 local-agent 的旧行为反向塑造 host 协议。
- 不在 host 中实现通用 agentic prompt assembler。
- 不强制 runner 使用 LangBot state / storage；只提供可选、受控的寄宿能力。
- 不实现 EventGateway / EventRouter：它们由外部 EBA 分支提供并联调。本分支只定义 host-side envelope/binding models 和 `run(event, binding)` 入口。

## 3. 分层架构

```text
IM / WebUI / API / EventRouter (external EBA branch)
        |
        v
Event Gateway (external EBA branch)
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

目标产品模型、单绑定调度、Agent 复用、插件实例无状态和 fan-out 边界以 [PROTOCOL_V1.md](./PROTOCOL_V1.md) §13 为准。本文只说明 Host 如何把当前入口投影为内部模型。当前 Pipeline 只应接入在 Query entry adapter 位置：它可以继续产生 `message.received` 并投影出临时 `AgentConfig` / `AgentBinding`，但不应再拥有 runner 选择、上下文裁剪和业务 agent 执行的核心语义。EventGateway / EventRouter 由外部 EBA 分支实现并联调。

## 4. LangBot 侧能力

### 4.1 Event Gateway / EventRouter（External EBA Branch Integration Point）

> EventGateway / EventRouter 由外部 EBA 分支实现并联调，不在本分支范围。本分支只保留 event-first 入口和 envelope/binding models。

Event Gateway 将把入口统一成 host event（IM 平台消息、WebUI debug chat、API 触发、后续非消息事件），输出稳定的 `AgentEventEnvelope`（Host 内部模型）：

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
    input: AgentInput          # 见 PROTOCOL_V1 §5.6
    delivery: DeliveryContext  # 见 PROTOCOL_V1 §5.7
    raw_ref: RawEventRef | None
    metadata: dict[str, Any] = {}
```

`AgentEventEnvelope` 是 Host 内部入口模型；投影给 runner 的是 `ctx.event`（PROTOCOL_V1 §5.4）。原始平台 payload 存为 raw event 或 artifact ref，不扩散到 runner 协议顶层。

**当前 adapter source**：`QueryEntryAdapter.query_to_event(query)` 从 Query 生成 `AgentEventEnvelope`。

### 4.2 AgentConfig 与 AgentBinding

`AgentConfig` 是迁移期的 Host 内部 Agent 配置投影（不暴露给 SDK）。当前 Query entry adapter 从 Pipeline config 投影出它；未来持久 Agent 也应先投影成这个运行期配置，再由 BindingResolver 结合事件和 scope 解析为 `AgentBinding`。

```python
class AgentConfig(BaseModel):
    agent_id: str | None = None
    runner_id: str
    runner_config: dict[str, Any] = {}
    resource_policy: ResourcePolicy = ResourcePolicy()
    state_policy: StatePolicy = StatePolicy()
    delivery_policy: DeliveryPolicy = DeliveryPolicy()
    event_types: list[str] = ["message.received"]
    enabled: bool = True
    metadata: dict[str, Any] = {}
```

`AgentBinding` 是"什么事件调用哪个 AgentRunner、带什么 Agent 配置"的 Host 内部运行投影（不暴露给 SDK）。它是 EventRouter / 当前 QueryEntryAdapter 在一次运行前解析出的有效绑定。

```python
class AgentBinding(BaseModel):
    binding_id: str
    enabled: bool
    scope: BindingScope
    event_types: list[str]
    filters: list[EventFilter] = []   # EBA 阶段使用，见 EVENT_BASED_AGENT
    runner_id: str
    runner_config: dict[str, Any]
    resource_policy: ResourcePolicy
    state_policy: StatePolicy
    delivery_policy: DeliveryPolicy
```

BindingResolver 的基数、fan-out 和冲突处理约束见 PROTOCOL_V1 §13；本节只定义 Host 内部投影形态。

**当前 adapter source**：`QueryEntryAdapter.config_to_agent_config(query, runner_id)`
先把 current config 投影为迁移期 `AgentConfig`，再由
`AgentBindingResolver.resolve_one(event, [agent_config])` 解析出唯一
`AgentBinding`。Pipeline 当前只是迁移期 Agent config source（AI runner config
→ runner_config、extension preference → resource_policy、output settings →
delivery_policy），但新设计不再把这些字段命名为 Pipeline 专属概念。

### 4.3 AgentRunnerRegistry

Registry 收集 runner descriptor（来自插件 runtime、开发期本地插件）：

```python
class AgentRunnerDescriptor(BaseModel):
    id: str
    source: Literal["plugin"]
    label: I18nObject
    description: I18nObject | None = None
    plugin_author: str
    plugin_name: str
    runner_name: str
    capabilities: AgentRunnerCapabilities    # 见 PROTOCOL_V1 §4.3
    permissions: AgentRunnerPermissions      # 见 PROTOCOL_V1 §4.4
    config_schema: list[DynamicFormItemSchema]
    plugin_version: str | None = None
    raw_manifest: dict[str, Any] = {}
```

职责：调用 `plugin_connector.list_agent_runners()` 拉取 runner、校验 typed `AgentRunnerManifest`、输出 descriptor、缓存 discovery 结果并提供 `refresh()`。单个插件 manifest 失败只记 warning，不影响其它 runner。`plugin:author/name/runner` 是稳定 id 格式；插件实例边界见 PROTOCOL_V1 §13。

Host 内置 runner / adapter 不能作为 `AgentRunnerDescriptor.source` 绕过插件
runtime、`run_id`、`ctx.resources` 和 `AgentRunAPIProxy` 权限链。若需要
开发期调试 adapter，应放在 Host 内部测试入口，不进入可选 runner 列表。

刷新触发点：插件安装/卸载/升级/重启后；Pipeline metadata 请求时发现缓存为空；可选 TTL（优先保证正确性）。

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

它负责：`run_id` 生成和生命周期、timeout/deadline/cancellation、插件异常隔离、result schema 校验和大小限制、`state.updated` 处理、delivery backpressure 和 telemetry。

典型 run 时序：

```text
QueryEntryAdapter / EventRouter
  -> AgentRunOrchestrator.run(event, binding)
  -> AgentRunnerRegistry.resolve(runner_id)
  -> AgentResourceBuilder.freeze_snapshot(binding, event)
  -> AgentRunSessionRegistry.register(run_id, runner_id, snapshot)
  -> AgentContextBuilder.build(event, binding, snapshot)
  -> PluginRuntimeConnector.run_agent(ctx)
       -> AgentRunAPIProxy action
          -> validate active run session + caller identity + snapshot
          -> Host API / Store
       <- AgentRunResult stream
  -> apply state.updated to PersistentStateStore
  -> write message.completed / artifact.created to Transcript / ArtifactStore
  -> render delivery or raise RunnerExecutionError
  -> AgentRunSessionRegistry.unregister(run_id)
```

`run_from_query()` 保留为 Query entry adapter 入口，但内部转换成 event + binding 后走统一 `run()`。约束：`ChatMessageHandler` 不解析 `plugin:*`、不实例化 wrapper、不知道 runner 组件细节；`PipelineService` 从 registry 读取 metadata，不直接访问插件 runtime；跨请求持久化状态必须走授权 storage / 外部服务。

### 4.5 Resource Authorization

LangBot 在每次 run 前生成 `ctx.resources`（PROTOCOL_V1 §6），来自 manifest permissions 与 binding policy 的交集：

1. `descriptor.permissions` 声明 runner 需要的 LangBot 资源访问上限。
2. binding / resource policy 允许的资源范围。
3. Agent/runner config 中选择的模型、知识库、文件等资源。
4. 当前 event / actor / bot / workspace 的实际权限。
5. `ctx.context.available_apis` 暴露的 pull API 能力。

这次裁剪结果必须冻结为 run-scoped authorization snapshot，并由
`AgentRunSessionRegistry` 按 `run_id` 保存。`ctx.resources` 是投影给 runner
看的同一份授权结果；运行期每个 proxy action 只依据该 snapshot 校验 active
run session、caller plugin identity、resource id、scope、payload size、rate
limit 和 deadline。Handler 不应重新执行授权裁剪，否则 build-time 与 runtime
授权逻辑会漂移。

SDK 侧本地校验只用于开发体验，host 侧 run authorization snapshot 才是安全边界。`spec.capabilities` 只帮助 Host 判断 runner 是否需要 tool / knowledge / skill 等资源投影，不能替代 permissions 或 binding policy。

资源裁剪应通用，不写死 local-agent。selector 与资源的映射示例：`model-fallback-selector` → primary/fallback LLM、`llm-model-selector` → LLM、`rerank-model-selector` → rerank 模型、`knowledge-base-multi-selector` → 知识库；新增 selector 时在 resource builder 中统一扩展。

执行/文件/skill/MCP 等能力的接入方向：先由 Host / sandbox 封装成普通 scoped tool，再通过 `ctx.resources.tools` 和 SDK runtime 转发进入 runner；runner 不应识别或硬编码执行环境 provider。外部 harness 的 native tools 不能直接访问 LangBot 资源。

### 4.6 State / Storage

LangBot 可提供 host-owned state 让 runner 寄宿状态（conversation / actor / subject / runner / binding / workspace state），但**不是强制**。Host 只需提供：授权开关、scope key、get/set/list/delete API（见 PROTOCOL_V1 §8）、持久化 backend、审计和清理策略。外部 agent runtime 可维护自己的 session 和 memory。进程内 state store 只能作为过渡实现，不能作为正式生产语义。

### 4.7 EventLog / Transcript / Artifact（事实源）

- `EventLog`: durable append-only，保存原始事件、系统事件、工具调用、投递结果、错误。
- `Transcript`: 从 EventLog 投影出的对话视图，用于 UI、审计和按需历史读取。
- `ArtifactStore`: 保存大文件、多模态输入、工具大结果、平台附件。

三类数据与 working context 的边界、读取约束见 [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md)。AgentRunner 可读取这些能力，但不被迫使用 LangBot 作为唯一记忆系统。

### 4.8 External harness resource projection

Claude Code、Codex、Kimi Code 等外部 harness runner 可能不直接调用 LangBot 的 model/tool loop，而是把 LangBot 事件和授权资源句柄投影到自己的 harness 执行。Host 侧仍保持统一边界：Host 负责构造 event-first context、资源授权、state/storage、EventLog/Transcript/ArtifactStore 和审计；Host 或 binding policy 决定哪些 MCP bridge、skill-backed tool、artifact、history/state 句柄可投影给 runner；runner plugin 把 scoped projection 转成目标 harness 可消费形式；所有 LangBot 资源访问必须经 SDK runtime / `AgentRunAPIProxy` / SDK-owned MCP bridge 转发并接受 Host 校验；外部 harness 负责自己的 native session、tool loop、压缩、权限模式和 resume，但不能用 native tools 绕过 Host 授权。

投影的具体形态（context 文件、resource handles、SDK-owned MCP bridge、state pointers）见 AGENT_CONTEXT_PROTOCOL §4.5；Claude Code / Codex 当前实现见 OFFICIAL_RUNNER_PLUGINS §7。发布级隔离要求见 SECURITY_HARDENING。

## 5. SDK 侧协议

SDK 组件入口如下；所有数据结构定义见 PROTOCOL_V1。

```python
class AgentRunner(BaseComponent):
    __kind__ = "AgentRunner"

    @classmethod
    def get_config_schema(cls) -> list[dict]: ...

    async def run(self, ctx: AgentRunContext) -> AsyncGenerator[AgentRunResult, None]: ...
    # ctx: PROTOCOL_V1 §5.2 ; AgentRunResult: PROTOCOL_V1 §7
```

- Manifest / capabilities / effective access：PROTOCOL_V1 §4。Capabilities 来自组件 manifest 的 `spec.capabilities`，不是 SDK 基类 classmethod。
- `AgentRunContext`：PROTOCOL_V1 §5.2。`messages` / `bootstrap` 不是协议字段。
- `AgentRunResult`：PROTOCOL_V1 §7。
- `AgentRunAPIProxy`：PROTOCOL_V1 §8，是 runner 访问 host 能力的唯一入口，所有请求带 `run_id`。
