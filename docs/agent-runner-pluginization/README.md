# Agent Runner 插件化设计

## 1. 背景

当前 `feat/agent-runner-plugin` 分支已经验证了一个最小路径：SDK 增加 `AgentRunner` 组件，LangBot 在 Pipeline 的 `runner` 配置项中动态列出插件提供的 runner，并在 `ChatMessageHandler` 中通过 `plugin_connector.run_agent()` 调用插件实现。

这个方向能把内置 `RequestRunner` 之外的 Agent 实现放到插件中，但它仍然沿用“私聊/群聊消息进入 Pipeline，再由 runner 产出回复”的旧模型。它没有解决后续 Agent 需要面对复杂上下文的问题，也没有为 EBA 计划里的事件驱动能力留下足够清晰的扩展面。

本设计只聚焦 Agent Runner 插件化。EBA 文档中的事件体系、平台 API、事件路由只作为接口预留和未来兼容参考，不纳入本阶段实现范围。

## 2. 目标与非目标

目标：

- 将 Agent Runner 从 LangBot 内置 runner 列表中解耦，允许插件提供新的 Agent 执行器。
- 保持当前聊天 Pipeline 可用，并允许现有消息场景选择插件 Agent Runner。
- 设计新的 Agent 上下文模型，使 runner 不只依赖 `query.messages` 和 `user_message`，还能承载事件、会话、资源、工具、知识库、平台能力和业务状态。
- SDK 提供稳定的 `AgentRunner` 组件接口、上下文实体、返回实体、配置 schema 和运行期 API。
- LangBot 负责 runner 发现、配置装配、权限校验、运行调度、流式结果转换、错误隔离和兼容层。
- 为未来 EBA 的非消息事件接入预留 `event`、`actor`、`subject`、`platform_capabilities` 等上下文字段。
- 现有内置 `RequestRunner` 最终强制迁移为插件形态，由 LangBot 通过同一套插件化 runner 协议调用。

非目标：

- 不在本阶段实现 EBA EventBus、EventRouter、平台多事件监听或统一平台 API。
- 不改变现有 Pipeline 的阶段链和私聊/群聊入口。
- 不引入插件内自定义长驻调度器；Agent Runner 仍由 LangBot 显式调用。

## 3. 当前分支问题

当前分支的实现可以作为 PoC，但需要调整：

- `AgentRunContext` 仍是 query 视角，字段包括 `query_id`、`session`、`messages`、`user_message`、`use_funcs`、`extra_config`，对非消息事件和复杂任务上下文表达不足。
- runner 标识使用 `plugin:author/plugin_name/runner_name` 字符串拼接，缺少结构化 ID、版本、能力和权限信息。
- LangBot 在 `PipelineService.get_pipeline_metadata()` 中直接把插件配置 schema 拼进 AI metadata，缺少缓存、失败隔离和 schema 兼容验证。
- `ChatMessageHandler` 内部直接解析插件 runner 名称并调用 wrapper，调度逻辑和消息处理逻辑耦合。
- SDK 的 `AgentRunner.run()` 只接受单一上下文，没有生命周期 hooks、能力声明、配置 schema 分层和运行结果协议版本。
- 工具调用、知识检索、LLM 调用目前依赖零散 proxy action，缺少 Agent 运行期明确的 capability set。

## 4. 总体架构

建议引入三层结构：

```text
Pipeline / future Event Router
        |
        v
AgentRunnerRegistry
        | discovers built-in runners and plugin runners
        v
AgentRunOrchestrator
        | builds context, validates permissions, invokes runner
        v
Built-in RequestRunner adapter / Plugin AgentRunner component
        |
        v
AgentRunResult stream
```

### 4.1 AgentRunnerRegistry

职责：

- 从内置 runner 和插件运行时收集 runner manifest。
- 输出统一的 `AgentRunnerDescriptor`，而不是散落在 UI metadata 中的字符串 option。
- 对插件 runner manifest 做基础校验：组件类型、配置 schema、权限声明、协议版本。
- 提供缓存和刷新机制，插件安装、卸载、重启后刷新。

建议结构：

```python
class AgentRunnerDescriptor(BaseModel):
    id: str                     # builtin:local-agent 或 plugin:author/name/runner
    source: Literal["builtin", "plugin"]
    label: I18nObject
    description: I18nObject | None = None
    config_schema: list[DynamicFormItemSchema] = []
    capabilities: AgentRunnerCapabilities
    plugin: PluginRef | None = None
    protocol_version: str = "1"
```

### 4.2 AgentRunOrchestrator

职责：

- 根据 pipeline 配置选择 runner。
- 将当前 query 或未来事件输入转换为 `AgentRunRequest`。
- 注入可用工具、模型、知识库、会话、权限、平台能力摘要。
- 统一处理超时、异常、流式返回、取消、中断和 telemetry。
- 将插件返回的 `AgentRunResult` 转换回当前 Pipeline 能消费的 `Message` / `MessageChunk`。

LangBot 当前 `ChatMessageHandler` 里的插件 wrapper 应下沉到 orchestrator，避免消息处理器知道插件 runner 的细节。

## 5. SDK 设计

### 5.1 AgentRunner 组件

SDK 保留当前分支新增的组件方向，但需要补齐能力声明：

```python
class AgentRunner(BaseComponent):
    __kind__ = "AgentRunner"
    __protocol_version__ = "1"

    @classmethod
    def get_capabilities(cls) -> AgentRunnerCapabilities:
        return AgentRunnerCapabilities()

    @classmethod
    def get_config_schema(cls) -> list[dict]:
        return []

    async def run(self, ctx: AgentRunContext) -> AsyncGenerator[AgentRunResult, None]:
        ...
```

一个插件可以声明多个 `AgentRunner` 组件。每个 runner 使用独立的 component manifest、配置 schema、能力声明和权限声明；LangBot 侧以 `plugin:author/name/runner` 作为稳定 ID 区分。插件包可以因此同时提供多个执行策略，例如通用聊天 runner、客服 runner、工单 runner，而不需要拆成多个插件。

`get_capabilities()` 用来告诉 LangBot 这个 runner 是否支持：

- `streaming`
- `tool_calling`
- `knowledge_retrieval`
- `multimodal_input`
- `event_context`
- `platform_api`
- `interrupt`
- `stateful_session`

本阶段可以先实现 `streaming`、`tool_calling`、`knowledge_retrieval` 三项，其他字段只作为声明和预留。

### 5.2 上下文模型

当前 `AgentRunContext` 应升级为更通用的运行上下文：

```python
class AgentRunContext(BaseModel):
    run_id: str
    trigger: AgentTrigger
    conversation: ConversationContext | None = None
    event: AgentEventContext | None = None
    actor: ActorContext | None = None
    subject: SubjectContext | None = None
    messages: list[Message] = []
    input: AgentInput
    resources: AgentResources
    runtime: AgentRuntimeContext
    config: dict[str, Any] = {}
```

关键点：

- `trigger` 标明触发来源。当前消息 Pipeline 使用 `message.received`，未来 EBA 可使用 `group.member_joined`、`friend.request_received` 等。
- `conversation` 承载会话历史、launcher、sender、bot 等聊天语义。
- `event` 是未来 EBA 的预留封装，本阶段可以由 query 生成一个最小 message event。
- `actor` 表示触发者，`subject` 表示事件作用对象，例如被邀请用户、被撤回消息、被操作群组。
- `input` 是 runner 的主输入，不再强制等同于纯文本消息。
- `resources` 列出 LangBot 已授权给 runner 的工具、知识库、模型、文件等。
- `runtime` 提供 host 信息、workspace/bot/pipeline 标识、trace id、deadline 等。
- `config` 是当前 Pipeline 或未来事件绑定对该 runner id 的绑定配置，替代当前 `extra_config`。

为了兼容现有实现，SDK 可提供：

```python
ctx.input.to_text()
ctx.conversation.to_legacy_session()
ctx.to_legacy_query_context()
```

### 5.3 返回协议

当前 `AgentRunReturn.type` 建议规范化为事件流：

```python
class AgentRunResult(BaseModel):
    type: Literal[
        "message.delta",
        "message.completed",
        "tool.call.started",
        "tool.call.completed",
        "state.updated",
        "run.completed",
        "run.failed",
    ]
    data: dict[str, Any] = {}
```

本阶段 Pipeline 兼容映射：

- `message.delta` -> `MessageChunk`
- `message.completed` -> `Message`
- `run.completed` 且带 `message` -> `Message`
- `run.failed` -> 记录错误并按当前 runner 错误策略返回

`action.requested` 不进入本阶段的必选协议。它表示“Agent 希望 LangBot 执行一个非文本平台动作”，例如未来 EBA 里编辑消息、通过好友请求、踢人等。当前 Agent Runner 仍作为 Pipeline 的一个 stage 执行，输出只需要覆盖消息流、工具调用状态和运行完成/失败；如果实验性 runner 返回 `action.requested`，LangBot 只记录 telemetry 并忽略执行。

### 5.4 LangBotAPIProxy

Agent Runner 插件需要使用 LangBot 能力，但这些能力必须通过显式授权暴露：

- 模型：`invoke_llm`、`invoke_llm_stream`、embedding。
- 工具：`list_tools`、`get_tool_detail`、`call_tool`。
- 知识：`list_knowledge_bases`、`retrieve_knowledge`。
- 存储：plugin storage、workspace storage。
- 文件：配置文件读取、知识文件读取。

SDK 应把这些能力按 capability 分组。LangBot 在调用 runner 前根据 runner manifest、pipeline 配置、插件绑定范围生成 `resources`，插件不能绕过资源列表调用未授权对象。

## 6. LangBot 设计

### 6.1 runner 发现

在 LangBot 增加 `AgentRunnerRegistry`：

- 内置 runner 由 `runner_module.preregistered_runners` 注册为 `builtin:*`。
- 插件 runner 通过 `PluginRuntimeConnector.list_agent_runners()` 获取。
- manifest 中必须包含 `metadata`、`spec.config`、`spec.capabilities`。
- 发现失败只影响对应插件 runner，不影响 Pipeline metadata 返回。

当前 `PipelineService.get_pipeline_metadata()` 可以继续作为 UI 入口，但应改为读取 registry，而不是直接拼插件列表。

### 6.2 配置模型与绑定位置

当前阶段 runner 配置仍跟 Pipeline 绑定，并且仍然作为 Pipeline 的一个 stage 执行。也就是说，Bot 收到私聊/群聊消息后仍按现有 Pipeline 流转，只是在 AI runner stage 中选择插件化 Agent Runner。

这里的“绑定配置”不代表插件实例。插件安装后由插件 runtime 维护插件本身的运行实例；LangBot 不会因为多个 Pipeline 选择同一个 runner id 而创建多个插件实例或 runner 实例。不同 Pipeline 可以保存不同的 `runner_config[id]`，调用时 LangBot 只把当前绑定配置放进 `AgentRunContext.config` 转发给同一个插件 runner。

插件 runner 应按无状态执行单元设计。需要跨请求保存的 conversation id、外部平台状态或用户状态，应通过明确授权的 plugin storage、workspace storage、外部服务或 context runtime state 管理，不能隐式依赖 per-pipeline 插件对象状态。

后续 EBA EventRouter 落地后，同一套 `AgentRunnerDescriptor` 和 `AgentRunOrchestrator` 需要支持直接与 Bot 的事件触发器绑定。届时 Bot event handler 可以绕过完整 Pipeline，直接选择某个 Agent Runner 处理 `message.received`、`group.member_joined`、`friend.request_received` 等事件。

Pipeline AI 配置建议从：

```json
{
  "runner": {
    "runner": "local-agent"
  },
  "local-agent": {}
}
```

演进为：

```json
{
  "runner": {
    "id": "plugin:author/name/runner"
  },
  "runner_config": {
    "plugin:author/name/runner": {}
  }
}
```

为了兼容现有配置：

- 读取时同时支持 `runner.runner` 和 `runner.id`。
- 写入时可以先继续写 `runner.runner`，等前端完成迁移后再切到 `runner.id`。
- 旧的内置 runner config key 保持可用。

### 6.3 运行调度

`ChatMessageHandler` 不应直接构造 `PluginAgentRunnerWrapper`。建议路径：

```text
ChatMessageHandler
  -> AgentRunOrchestrator.run_from_query(query)
      -> resolve runner descriptor
      -> build AgentRunContext
      -> invoke built-in adapter or plugin connector
      -> normalize AgentRunResult stream
```

内置 `RequestRunner` 可以由 adapter 包一层，统一成 `AgentRunnerDescriptor`，但不要求现在改写内置 runner。

### 6.4 插件调用协议

LangBot 到 SDK runtime 需要以下 action：

- `LIST_AGENT_RUNNERS`
- `RUN_AGENT`

`RUN_AGENT` 输入：

```json
{
  "plugin_author": "...",
  "plugin_name": "...",
  "runner_name": "...",
  "context": {}
}
```

`RUN_AGENT` 输出为流式 `AgentRunResult`。LangBot 必须校验每个结果：

- 未知 `type` 记录 warning 后忽略。
- 单次 result 大小限制，避免插件输出过大。
- `message.delta` 和 `message.completed` 做 provider message schema 校验。
- `run.failed` 进入统一错误处理。

### 6.5 权限与隔离

插件 runner 的权限不能只靠插件安装即全量开放。建议 manifest 增加：

```yaml
spec:
  capabilities:
    streaming: true
    tool_calling: true
    knowledge_retrieval: true
  permissions:
    models: ["invoke"]
    tools: ["call"]
    knowledge_bases: ["retrieve"]
    platform_api: []
```

LangBot 执行前做三层裁剪：

- 插件 manifest 声明的权限。
- Pipeline 或 Bot 绑定的扩展范围。
- 用户在 Pipeline runner 绑定配置中选择的资源范围。

最终写入 `ctx.resources`，并在 proxy action 里再次校验。

## 7. 与 EBA 的边界

本阶段只使用 EBA 文档中的以下思想：

- 统一事件命名，例如当前消息 query 可映射为 `message.received`。
- Agent 不应假设输入一定是用户文本消息。
- Agent 返回不应只限于文本回复，未来可表达动作请求。
- 插件 SDK 的事件和 API 应向后兼容。

本阶段不实现：

- EventBus。
- EventRouter。
- 新平台适配器目录结构。
- 群组、好友、Bot 状态等非消息事件监听。
- 统一平台 API 的实际执行。

因此文档和代码命名应避免把当前任务称为 EBA 实现。推荐使用 `agent-runner-pluginization`、`AgentRunContext`、`AgentRunResult` 等命名。

## 8. 分阶段落地

### Phase 1：整理当前分支

- 保留 SDK `AgentRunner` 组件。
- 调整 `AgentRunContext` / `AgentRunReturn` 为协议 v1 的命名和字段。
- LangBot 增加 `AgentRunnerRegistry` 和 `AgentRunOrchestrator`。
- `ChatMessageHandler` 改为调用 orchestrator。
- Pipeline metadata 从 registry 读取 runner 列表。

### Phase 2：能力和权限

- runner manifest 增加 `capabilities`、`permissions`、`config_schema`。
- LangBot 对工具、知识库、模型资源做注入和裁剪。
- proxy action 做二次校验。
- 增加超时、取消、错误隔离和 telemetry。

### Phase 3：内置 runner 插件化迁移

- 兼容当前 `plugin:author/name/runner` 字符串 ID。
- 兼容 `runner.runner` 配置键。
- 提供从旧 runner 配置到 `runner.id` / `runner_config` 的迁移。
- 将所有内置 `RequestRunner` 强制迁移为内置插件或官方插件包。
- LangBot 只保留插件 runtime、registry、orchestrator 和兼容迁移逻辑，不再维护独立的内置 runner 执行分支。

### Phase 4：为 EBA 接入做预留

- `AgentRunContext.event` 支持 EBA 文档定义的事件 envelope 子集。
- `AgentRunResult.action.requested` 仍只记录，不执行；真正执行平台动作需要等统一平台 API 和事件触发器权限模型完成。
- 等 EBA EventRouter 落地后，由 EventRouter 直接调用 orchestrator。

## 9. 需要修改的代码范围

LangBot：

- `src/langbot/pkg/pipeline/process/handlers/chat.py`：移除插件 runner 解析细节，改为 orchestrator。
- `src/langbot/pkg/api/http/service/pipeline.py`：从 registry 获取 runner metadata。
- `src/langbot/pkg/plugin/connector.py`：保留 `list_agent_runners()` / `run_agent()`，增加协议校验。
- `src/langbot/pkg/plugin/handler.py`：整理 Agent 运行期可调用的 proxy action。
- 新增 `src/langbot/pkg/provider/agent_runner/` 或 `src/langbot/pkg/agent/runner/`：registry、orchestrator、context builder、result normalizer。

SDK：

- `src/langbot_plugin/api/definition/components/agent_runner/runner.py`：补 capabilities、config schema、协议版本。
- `src/langbot_plugin/api/entities/builtin/agent_runner/context.py`：升级上下文和返回协议。
- `src/langbot_plugin/runtime/io/handlers/control.py`：保留 `LIST_AGENT_RUNNERS` / `RUN_AGENT`。
- `src/langbot_plugin/runtime/plugin/mgr.py`：runner 发现、调用、异常隔离。
- `src/langbot_plugin/api/proxies/langbot_api.py`：补齐 Agent 运行期需要的 host capability proxy。

## 10. 验收标准

- Pipeline 可以选择一个插件提供的 Agent Runner。
- 插件 runner 能收到结构化上下文，并能流式返回消息。
- 插件 runner 只能看到 LangBot 注入的工具、知识库、模型资源。
- 插件 runner 异常不会中断插件 runtime 或 Pipeline 主流程。
- 旧 Pipeline 配置和旧内置 runner 正常工作。
- 文档明确区分“Agent Runner 插件化”和“未来 EBA 架构”。

## 11. 已确认决策

- 插件可以声明多个 `AgentRunner` 组件，每个组件独立暴露 manifest、配置 schema、能力和权限。
- 本阶段不把 `action.requested` 作为必须实现的运行结果。它只是为未来 EBA 平台动作预留的返回类型；当前 Pipeline stage 中如收到该类型，只记录 telemetry，不执行动作。
- 当前 runner 配置先跟 Pipeline 绑定，仍然在 Pipeline 的 AI runner stage 中执行；后续需要支持直接与 Bot 的事件触发器绑定。
- Pipeline/Event 绑定只保存 runner id 和绑定配置，不创建插件实例或 runner 实例；插件 runner 按无状态转发调用处理，跨请求状态必须显式存储。
- 内置 `RequestRunner` 最终强制迁移为插件形态，避免长期保留“内置 runner 分支”和“插件 runner 分支”两套执行体系。
