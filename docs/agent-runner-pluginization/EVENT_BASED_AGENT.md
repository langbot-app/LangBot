# Event Based Agent 预留设计

> **注意**：本文档是 future design note，不是当前分支实现范围。
>
> EventGateway、EventRouter、Event subscription/notification 由其他分支实现。
> 本分支只预留 event-first 入口和 envelope/binding models。
> 2026-05-29 的 local-agent / Claude Code runner smoke 只验证本分支的 `run(event, binding)` 调度边界，不表示 EBA 分支已经完成联调。

本文档描述未来 EBA 接入时，事件如何进入 LangBot、如何触发 AgentRunner，以及如何复用插件化 agent 基础设施。

本阶段不实现完整 EventBus / EventRouter / Platform API。本阶段要做的是把协议边界设计对，避免当前消息入口继续绑死 Pipeline 和用户文本消息。

## 1. 设计目标

- 消息、撤回、入群、好友申请、定时任务、API 调用都能抽象为 host event。
- EventRouter 可以根据 event type、bot、workspace、conversation、actor、subject 解析 AgentBinding。
- AgentRunner 通过同一套 orchestrator 被调用。
- 非消息事件不伪造成用户文本消息。
- 平台动作执行通过显式 capability / permission / result type 预留，不混入普通文本回复。

## 2. 事件不是消息

`message.received` 只是事件的一种。协议不应假设：

- 一定有用户文本。
- 一定有 conversation history。
- 一定要返回一条聊天消息。
- actor 一定等于 sender。
- subject 一定等于当前消息。

例如：

| event_type | actor | subject | input |
| --- | --- | --- | --- |
| `message.received` | 发消息的人 | 当前消息 | 文本、图片、文件等 |
| `message.recalled` | 撤回操作者，未知时为系统 | 被撤回消息 | 通常为空 |
| `group.member_joined` | 新成员或邀请人 | 群/成员关系 | 通常为空 |
| `friend.request_received` | 申请人 | 好友申请 | 验证消息或申请理由 |
| `schedule.triggered` | 系统 | 定时任务 | 任务 payload |
| `api.invoked` | API caller | API request | request payload |

## 3. Event Envelope

建议事件 envelope：

```python
class AgentEventEnvelope(BaseModel):
    event_id: str
    event_type: str
    event_time: int | None
    source: EventSource
    workspace_id: str | None
    bot_id: str | None
    conversation_id: str | None
    thread_id: str | None
    actor: ActorRef | None
    subject: SubjectRef | None
    input: AgentInput
    delivery: DeliveryContext
    raw_ref: RawEventRef | None
    metadata: dict[str, Any] = {}
```

顶层字段使用 LangBot 稳定协议名。平台原始事件名和原始 payload 放到 `metadata` 或 `raw_ref`，不直接成为 runner 的稳定依赖。

## 4. Event Source

事件来源可以包括：

- `platform_adapter`: 飞书、QQ、微信、Telegram 等 IM 平台。
- `webui`: Debug Chat、控制台操作。
- `http_api`: 外部系统调用 LangBot。
- `scheduler`: 定时任务。
- `system`: runtime、plugin、maintenance 事件。

同一个 event source 可以产生多个 event type。EventRouter 不应该写死平台 adapter 的类名。

## 5. Event Binding

EBA 中，AgentBinding 取代 Pipeline runner 配置成为触发关系：

```python
class AgentBinding(BaseModel):
    binding_id: str
    enabled: bool
    event_types: list[str]
    scope: BindingScope
    filters: list[EventFilter]
    runner_id: str
    runner_config: dict[str, Any]
    resource_policy: ResourcePolicy
    state_policy: StatePolicy
    delivery_policy: DeliveryPolicy
```

Binding scope 示例：

- workspace 全局。
- bot 级别。
- platform channel 级别。
- conversation / group / thread 级别。
- user / actor 级别。

旧 Pipeline 可以迁移为 `message.received` 的 binding source，但不是唯一 binding source。

## 6. EventRouter 调用链

目标调用链：

```text
Platform Adapter / WebUI / API
  -> Event Gateway normalize payload
  -> EventLog append raw event
  -> EventRouter resolve bindings
  -> AgentRunOrchestrator.run(event, binding)
  -> AgentRunContextBuilder.build(event, binding)
  -> PluginRuntimeConnector.run_agent()
  -> AgentRunResult stream
  -> DeliveryController render / platform action
```

约束：

- `run_from_event()` 必须复用现有 orchestrator 能力。
- 不能为 EBA 单独实现另一套 plugin runner 调用协议。
- 不能让非消息事件绕过 resource authorization。
- Delivery 和 platform action 要走统一权限模型。
- 外部 harness runner 也应通过同一套 envelope/binding/context/result 协议接入；EBA 不应为 Claude Code / Codex / Kimi Code 单独发明队列协议。

## 7. Delivery Context

Event 不一定回复到当前聊天窗口。需要显式 delivery：

```python
class DeliveryContext(BaseModel):
    surface: str
    reply_target: ReplyTarget | None
    supports_streaming: bool
    supports_edit: bool
    supports_reaction: bool
    max_message_size: int | None
    platform_capabilities: dict[str, Any] = {}
```

消息事件通常带 reply target。系统事件可能没有默认 reply target，需要 runner 返回 `action.requested` 或由 binding 的 delivery policy 决定投递位置。

## 8. AgentRunResult 与平台动作

当前消息路径主要消费：

- `message.delta`
- `message.completed`
- `run.completed`
- `run.failed`

EBA 后需要预留：

- `action.requested`: 请求 host 执行平台动作。
- `artifact.created`: runner 生成文件或大结果。
- `delivery.requested`: 请求投递到某个 surface。

示例：

```json
{
  "type": "action.requested",
  "data": {
    "action": "friend.request.accept",
    "target": {"platform": "wechat", "request_id": "..."},
    "reason": "policy matched"
  }
}
```

Host 必须校验：

- runner manifest 是否声明 platform_api capability。
- binding 是否授权该 action。
- actor / bot / workspace 是否允许。
- 是否需要人工审批。

本阶段如收到 `action.requested`，可以只记录 telemetry，不执行。

## 9. 与 Context 协议的关系

EBA 事件进入 AgentRunner 时仍使用 [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md) 的原则：

- inline 当前事件。
- 大 payload 用 raw/artifact ref。
- 不默认 inline 完整 history。
- agent 按需通过 API 拉 history/event/artifact/state。
- Host 保留 EventLog 和权限 guardrail。

非消息事件可以被投影进 Transcript，但不能强制伪装为 user message。AgentRunner 可以根据 event type 自己决定是否把它纳入模型上下文。

## 10. 当前实现与目标差距

**当前分支已落地（Event-first 基础设施）**：

- ✅ `AgentRunOrchestrator` — event-first `run(event, binding)` 入口
- ✅ `AgentRunContextBuilder` — event-first context 构建
- ✅ `AgentEventEnvelope` 模型
- ✅ `AgentBinding` 模型
- ✅ `AgentRunResult` 基础消息流
- ✅ `ctx.event` 的最小消息事件封装
- ✅ `PipelineAdapter` — Query → Event + Binding 转换
- ✅ `run_from_query()` → `run(event, binding)` 委托
- ✅ EventLog / Transcript / ArtifactStore
- ✅ History / Event / Artifact / State pull APIs
- ✅ 当前消息事件 path 已用 `local-agent` 与 Claude Code external harness runner 做本地 smoke

**其他分支负责（非本分支范围）**：

- EventGateway 实现
- EventRouter 实现
- Event subscription / notification
- EventLog 持久化管理 UI
- AgentBinding 持久化 UI
- 平台动作执行 (`action.requested` 执行器)

**未来 EBA 完整落地需要**：

- EventGateway 完整实现
- EventRouter 与 BindingResolver 集成
- AgentBinding 持久模型和 UI
- DeliveryContext 完整实现
- platform action permission model 和执行器
- 真实平台事件接入

## 11. 落地顺序

1. 先把当前 Pipeline 消息入口适配成 `message.received` event。
2. 增加 `AgentBinding` 抽象，先由 Pipeline config 生成。
3. `AgentRunContextBuilder` 改为从 event + binding 构造 context。
4. 引入 EventLog / Transcript。
5. 增加非消息事件的协议测试，不接真实平台。
6. 再接入真实 EventRouter 和 platform action。
