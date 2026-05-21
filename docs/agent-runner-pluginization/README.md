# Agent Runner 插件化设计

## 1. 背景

当前 `feat/agent-runner-plugin` 分支已经验证了一个最小路径：SDK 增加 `AgentRunner` 组件，LangBot 在 Pipeline 的 `runner` 配置项中动态列出插件提供的 runner，并在 `ChatMessageHandler` 中通过 `plugin_connector.run_agent()` 调用插件实现。

这个方向能把内置 `RequestRunner` 之外的 Agent 实现放到插件中，但它仍然沿用“私聊/群聊消息进入 Pipeline，再由 runner 产出回复”的旧模型。它没有解决后续 Agent 需要面对复杂上下文的问题，也没有为 EBA 计划里的事件驱动能力留下足够清晰的扩展面。

本设计只聚焦 Agent Runner 插件化。EBA 文档中的事件体系、平台 API、事件路由只作为接口预留和未来兼容参考，不纳入本阶段实现范围。

## 1.1 当前实现状态

当前实现已经不是早期 PoC：

- LangBot 已有 `AgentRunnerRegistry`、`AgentRunOrchestrator`、`AgentRunContextBuilder`、`AgentResourceBuilder`、`AgentResultNormalizer`。
- `ChatMessageHandler` 主路径已经委托给 orchestrator，不再直接解析插件 runner 或实例化 wrapper。
- Pipeline metadata 已经从 registry 动态生成插件 runner 选项和配置 stage。
- SDK 已有 Protocol v1 的 `AgentRunContext`、`AgentRunResult`、capabilities、permissions、`AgentRunAPIProxy`。
- 旧 `RequestRunner` 文件仍保留，当前作为迁移基准和回退分析材料；最终 parity 完成后再移除或隔离。

当前仍在收尾的重点不是“能不能调用插件 runner”，而是：

- 宿主侧通用能力是否足够，让插件 runner 获得旧内置 runner 隐式拥有的上下文。
- `local-agent` 官方插件是否能在对外行为上对齐旧内置 local-agent。
- 权限裁剪、timeout、错误隔离和端到端 parity 测试是否完整。

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

## 3. 当前实现剩余问题

以下是当前实现仍需要收敛的点：

- `AgentRunContext` 需要持续补齐宿主处理后的有效上下文，例如有效 prompt、结构化输入、runtime metadata、params/state。
- `AgentRunAPIProxy` 需要通过 `run_id/query_id` 保留旧 runner 隐式拥有的 Query 语义，例如工具调用上下文、知识库检索 settings、模型 extra args、remove-think。
- `AgentResourceBuilder` 应按 manifest + Pipeline 绑定 + runner config schema 通用裁剪资源，不能只为 local-agent 写死。
- `local-agent` 插件需要对齐旧内置 runner 的外部行为，包括 prompt preprocessing、多模态、fallback、tool loop、RAG、rerank、流式/非流式选择。
- timeout/deadline、取消、插件无输出、结果过大等运行保护还需要更完整的端到端验证。

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
        | resolves binding, provisions context/resources/state, invokes runner
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
- 编排 `ContextBuilder` / `ResourceBuilder` 生成 SDK `AgentRunContext` envelope 与已授权资源。
- 注册本次运行的 `run_id` / runner / resource scope，供后续 `AgentRunAPIProxy` 做权限校验。
- 统一处理超时、异常、流式返回、取消、中断和 telemetry。
- 将插件返回的 `AgentRunResult` 转换回当前 Pipeline 能消费的 `Message` / `MessageChunk`。

LangBot 当前 `ChatMessageHandler` 里的插件 wrapper 应下沉到 orchestrator，避免消息处理器知道插件 runner 的细节。
这里的 “context” 指 Host 提供的协议 envelope、运行身份、资源、状态快照和默认工作窗口，不是 Agent 的最终 prompt 组装或长期记忆策略。最终模型上下文如何压缩、摘要、召回，应由 AgentRunner 声明策略并在 AgentRunner 边界执行；LangBot 负责提供受限的基础设施和 guardrail。

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
    prompt: list[Message] = []
    messages: list[Message] = []
    context_request: AgentContextRequest | None = None
    context_packaging: ContextPackagingMetadata = ContextPackagingMetadata()
    input: AgentInput
    params: dict[str, Any] = {}
    resources: AgentResources
    state: AgentRunState = AgentRunState()
    runtime: AgentRuntimeContext
    config: dict[str, Any] = {}
```

关键点：

- `trigger` 标明触发来源。当前消息 Pipeline 使用 `message.received`，未来 EBA 可使用 `group.member_joined`、`friend.request_received` 等。
- `conversation` 承载会话历史、launcher、sender、bot 等聊天语义。
- `event` 是未来 EBA 的预留封装，本阶段可以由 query 生成一个最小 message event。
- `actor` 表示触发者，`subject` 表示事件作用对象，例如被邀请用户、被撤回消息、被操作群组。
- `prompt` 是宿主处理后的有效 prompt。它来自 LangBot 当前 conversation prompt，并且已经过 `PromptPreProcessing` 等插件事件处理；runner 调模型时应优先使用它，而不是重新读取静态 `config["prompt"]`。
- `messages` 是历史消息，也已经过宿主 pipeline preprocessing。插件化 AgentRunner 路径不再由 Pipeline `msgtrun` 截断，而是在 AgentRunner context packaging 边界按 legacy max-round 语义裁剪。
- `context_request` 是未来 AgentRunner manifest / binding config 提出的上下文偏好，例如 token budget、summary hybrid、external session；它不是 LangBot 单方面的策略开关。
- `context_packaging` 描述 Host 本次实际下发的历史窗口，例如使用的策略、来源、已下发消息数、是否确认完整、未来 cursor 等。本阶段只标注 AgentRunner legacy 窗口。
- `input` 是 runner 的主输入，不再强制等同于纯文本消息；`input.contents` 必须保留图片、文件等结构化内容。
- `params` 是单次运行的公开业务变量，宿主过滤内部变量和敏感变量后提供。
- `resources` 列出 LangBot 已授权给 runner 的工具、知识库、模型、文件等。
- `state` 是宿主管理的持久 runner-scoped 状态快照。
- `runtime` 提供 host 信息、workspace/bot/pipeline 标识、trace id、deadline 等。
- `config` 是当前 Pipeline 或未来事件绑定对该 runner id 的绑定配置，替代当前 `extra_config`。

为了兼容现有实现，SDK 可提供：

```python
ctx.input.to_text()
ctx.conversation.to_legacy_session()
ctx.to_legacy_query_context()
```

当前代码不改 SDK v1 schema，Host 实际下发结果先作为
`ctx.runtime.metadata.context_packaging` 下发；它是 packaging receipt，不是 LangBot 侧的长期策略控制面。

### 5.2.1 Agentic 上下文与文件协作方向

本节主要记录后续设计。本轮已把 legacy `max-round` working window 搬到
`AgentContextPackager`；LangBot 的完整会话历史仍主要来自进程内 `Conversation.messages`，
长期仍需要持久化 store 和压缩机制。

长期方向应区分三类数据：

- `ConversationStore` / `EventLog`: LangBot 持久保存完整原始消息、事件、工具调用和结果引用，作为审计、重放、重新压缩和历史检索的事实来源。
- `working context`: 每次 `AgentRunner.run()` 收到的受控上下文窗口。它不应是完整历史全文，而应由 `AgentContextPackager` 组装，例如 effective prompt、压缩摘要、最近若干轮、相关历史片段、RAG/tool context 和当前输入。
- `context state`: 压缩摘要、`last_compacted_seq`、外部 conversation id、用户偏好等跨轮状态。它由 host-owned state 或授权 storage 持久化，不能放在插件实例内存里。

因此不要把完整历史全部塞给插件 runner。正确边界是 LangBot host 保留完整历史，
AgentRunner 边界下发默认安全窗口；如果 runner 需要更多历史，应通过受限
`AgentRunAPIProxy` 按 cursor/page size 请求片段。这样可以避免每轮 O(n) 复制和跨进程
序列化，也避免插件 runtime 收到无限膨胀的上下文。

上下文压缩应在后续 LiteLLM 接入、能够获得模型 context window 后再实现。建议策略是：

- 每轮 run 前估算 `prompt + summary + recent turns + tool/RAG context + current input` 的 token。
- 超过阈值时，对较旧的历史窗口做 compression，生成 summary/checkpoint。
- 原始消息不删除；summary 是派生记忆，可以重算和审计。
- 下一轮使用 `summary + recent turns + relevant recalled history` 继续工作。
- 重启后从持久化 `ConversationStore/EventLog` 和 summary checkpoint 恢复 working context，而不是依赖进程内窗口。

大文件、多模态和工具产物不应内联进 `ctx.messages`。后续建议统一成 artifact/resource
引用：

- 小文本可以直接进入 message/content；大文件、图片、音频、工具输出文件只在 context 中放
  `artifact_id`、`mime_type`、`size`、`digest`、摘要和访问权限。
- `/tmp` 只适合作为单次 run 的本地临时 staging；不能作为重启后的事实来源。
- 长期可复用或跨工具协作的文件应放到 box/object storage。当前分支还没有合并 box 能力，
  因此本阶段只预留协议，不实现存取。
- AgentRunner 通过受限 API 读取 artifact，例如后续的 `get_artifact_metadata()`、
  `open_artifact_stream()`、`read_artifact_range()`。Host 必须校验 run_id、runner 权限、
  文件大小、MIME、过期时间和可访问范围。
- 工具返回大结果时也应返回 artifact ref + 摘要，而不是把完整结果塞回消息历史。

EBA 接入后，完整事实来源更适合建成 `EventLog + Projection`：

- `EventLog` 保存 `message.received`、`tool.call.completed`、`message.recalled`、
  `group.member_joined` 等原始事件。
- `ConversationProjection` 把与对话相关的事件投影成 agent 可读 history。
- 非消息事件不必伪造成用户消息；它可以带 `actor`、`subject`、`event_data`，再由
  `AgentContextPackager` 决定是否纳入 working context。

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

- 模型：`invoke_llm`、`invoke_llm_stream`、rerank、后续 embedding。
- 工具：`get_tool_detail`、`call_tool`。runner 通过 `ctx.resources.tools` 获取已授权工具列表，不暴露 unrestricted `list_tools`。
- 知识：`retrieve_knowledge`。runner 通过 `ctx.resources.knowledge_bases` 获取已授权知识库列表，不暴露 unrestricted `list_knowledge_bases`。
- 存储：plugin storage、workspace storage。
- 文件：配置文件读取、知识文件读取。

SDK 应把这些能力按 capability 分组。LangBot 在调用 runner 前根据 runner manifest、pipeline 配置、插件绑定范围生成 `resources`，插件不能绕过资源列表调用未授权对象。

宿主 action handler 不应只是把请求转发给 provider/tool/knowledge manager。对 AgentRunner 调用，它还需要通过 `run_id/query_id` 找回当前 Pipeline Query，并自动补齐旧内置 runner 过去直接拥有的上下文，例如：

- provider 调用的 `query`
- model `extra_args`
- 输出设置 `remove-think`
- 工具调用需要的 Query 上下文
- 知识库检索的 `bot_uuid`、`sender_id`、`session_name`

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

### 7.1 现在必须预留的事件适配方式

后续消息撤回、群成员加入、新好友申请等事件不要再走“伪造一条用户文本消息”的方式接入 AgentRunner。正确方向是让未来 `EventRouter` 构造同一份 `AgentRunContext`，然后复用当前 `AgentRunOrchestrator` 的 registry、resource builder、result normalizer 和插件调用协议。

当前先固定这些公共协议约束：

- 顶层 `ctx.event.event_type` 使用稳定协议名，不暴露 SDK 类名或平台原始事件名。
- 平台原始事件名、平台 payload、适配器细节放进 `ctx.event.event_data`。
- `ctx.input.text` 可以为空；runner 不能假设所有触发都是一段用户文本。
- `ctx.actor` 表示触发动作的主体，`ctx.subject` 表示被操作或被关注的对象。
- 需要平台动作时，runner 只能返回 `action.requested`；当前阶段只记录，真正执行等统一平台 API 和权限模型落地。

已预留的事件类型：

| event_type | actor | subject | input |
| --- | --- | --- | --- |
| `message.received` | 发消息的人 | 当前消息 | 文本、图片、文件等消息内容 |
| `message.recalled` | 撤回操作者，未知时为系统 | 被撤回消息 | 通常为空，原消息摘要放 `event_data` |
| `group.member_joined` | 新成员或邀请人，按平台 payload 标明 | 群/成员关系 | 通常为空，可把欢迎上下文放 `event_data` |
| `friend.request_received` | 申请人 | 好友申请 | 验证消息或申请理由 |

未来 EventRouter 的最小调用链应是：

```text
Platform Adapter
  -> EventRouter normalize platform payload
  -> resolve event binding: event_type + bot/workspace/scope -> runner id + config
  -> AgentRunOrchestrator.run_from_event(event_request)
  -> AgentRunContextBuilder.build_context_from_event(event_request)
  -> PluginRuntimeConnector.run_agent()
```

`run_from_event()` 不能重新实现一套 runner 调用逻辑，只能复用当前 `run_from_query()` 已经使用的 registry、资源裁剪、session registry、状态更新和结果归一化能力。这样 Pipeline 消息入口和 EBA 非消息入口不会分裂成两套协议。

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
- 将所有内置 `RequestRunner` 强制迁移为官方插件包。
- 迁移期间旧 `RequestRunner` 文件可以保留作为 parity 基准；主聊天路径不应继续依赖它们。
- LangBot 最终只保留插件 runtime、registry、orchestrator 和兼容迁移逻辑，不再维护独立的内置 runner 执行分支。

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
- 官方 `local-agent` 插件在外部行为上对齐旧内置 local-agent：有效 prompt、历史消息、结构化输入、RAG、rerank、工具循环、模型 fallback、streaming/non-streaming。
- 文档明确区分“Agent Runner 插件化”和“未来 EBA 架构”。

## 11. 已确认决策

- 插件可以声明多个 `AgentRunner` 组件，每个组件独立暴露 manifest、配置 schema、能力和权限。
- 本阶段不把 `action.requested` 作为必须实现的运行结果。它只是为未来 EBA 平台动作预留的返回类型；当前 Pipeline stage 中如收到该类型，只记录 telemetry，不执行动作。
- 当前 runner 配置先跟 Pipeline 绑定，仍然在 Pipeline 的 AI runner stage 中执行；后续需要支持直接与 Bot 的事件触发器绑定。
- Pipeline/Event 绑定只保存 runner id 和绑定配置，不创建插件实例或 runner 实例；插件 runner 按无状态转发调用处理，跨请求状态必须显式存储。
- 内置 `RequestRunner` 最终强制迁移为插件形态，避免长期保留“内置 runner 分支”和“插件 runner 分支”两套执行体系。

## 12. QA 验收

Phase 1 收尾进入 agent QA 时，使用 [PHASE1_QA_ACCEPTANCE_MATRIX.md](./PHASE1_QA_ACCEPTANCE_MATRIX.md) 作为验收标准。该矩阵只验收 Agent Runner 插件化 parity，不验收 EBA EventBus、EventRouter 或平台动作执行。
