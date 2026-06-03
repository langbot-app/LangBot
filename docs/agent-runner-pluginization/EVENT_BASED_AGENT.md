# Event Based Agent 预留设计

> **future design note**，不是当前分支实现范围。EventGateway、EventRouter、Event subscription/notification 由其他分支实现；本分支只预留 event-first 入口和 envelope/binding models。实现进度见 [PROGRESS.md](./PROGRESS.md)。
>
> 数据结构唯一定义在 [PROTOCOL_V1.md](./PROTOCOL_V1.md)（runner 可见）与 [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md)（Host 内部模型）；本文只讲 EBA 语义，不重抄 schema。

本文描述未来 EBA 接入时，事件如何进入 LangBot、如何触发 AgentRunner，以及如何复用插件化 agent 基础设施。本阶段不实现完整 EventBus / EventRouter / Platform API，目标是把协议边界设计对，避免当前消息入口继续绑死 Pipeline 和用户文本消息。

## 1. 设计目标

- 消息、撤回、入群、好友申请、定时任务、API 调用都能抽象为 host event。
- EventRouter 可以根据 event type、bot、workspace、conversation、actor、subject 解析 `AgentBinding`。
- AgentRunner 通过同一套 orchestrator 被调用。
- 非消息事件不伪造成用户文本消息。
- 平台动作执行通过显式 capability / permission / result type 预留，不混入普通文本回复。

## 2. 事件不是消息

`message.received` 只是事件的一种。协议不应假设：一定有用户文本、一定有 conversation history、一定要返回一条聊天消息、actor 一定等于 sender、subject 一定等于当前消息。

| event_type | actor | subject | input |
| --- | --- | --- | --- |
| `message.received` | 发消息的人 | 当前消息 | 文本、图片、文件等 |
| `message.recalled` | 撤回操作者，未知时为系统 | 被撤回消息 | 通常为空 |
| `group.member_joined` | 新成员或邀请人 | 群/成员关系 | 通常为空 |
| `friend.request_received` | 申请人 | 好友申请 | 验证消息或申请理由 |
| `schedule.triggered` | 系统 | 定时任务 | 任务 payload |
| `api.invoked` | API caller | API request | request payload |

## 3. 稳定事件名

先保留的稳定事件名（作为插件协议的一部分保持稳定）：

- `message.received`
- `message.recalled`
- `group.member_joined`
- `friend.request_received`

平台原始事件名只能进入 `ctx.event.source_event_type` / `raw_ref`，不能成为 `ctx.event.event_type` 的公共契约。

## 4. Event Envelope 与 Binding

- 入口事件用 `AgentEventEnvelope`（HOST_SDK §4.1）承载；顶层字段使用 LangBot 稳定协议名，平台原始事件名和原始 payload 放 `metadata` / `raw_ref`。
- 触发关系用 `AgentBinding`（HOST_SDK §4.2）表达。EBA 阶段 binding 通过 `event_types`、`scope`、`filters` 决定哪些事件触发哪个 runner。

Binding scope 示例：workspace 全局、bot 级、platform channel 级、conversation / group / thread 级、user / actor 级。旧 Pipeline 可迁移为 `message.received` 的 binding source，但不是唯一 binding source。

Event Source 可包括：`platform_adapter`（飞书、QQ、微信、Telegram 等）、`webui`、`http_api`、`scheduler`、`system`。EventRouter 不应写死平台 adapter 的类名。

## 5. EventRouter 调用链

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

约束：必须复用现有 orchestrator，不能为 EBA 单独实现另一套 plugin runner 调用协议；非消息事件不能绕过 resource authorization；delivery 和 platform action 走统一权限模型；外部 harness runner 也通过同一套 envelope/binding/context/result 协议接入，不为 Claude Code / Codex / Kimi 单独发明队列协议。

## 6. 平台动作执行

EBA 后 `action.requested`（PROTOCOL_V1 §7.2，当前仅 telemetry 不执行）将用于请求 host 执行平台动作：

```json
{ "type": "action.requested",
  "data": { "action": "friend.request.accept",
            "target": {"platform": "wechat", "request_id": "..."},
            "reason": "policy matched" } }
```

Host 必须校验：runner manifest 是否声明 `platform_api` capability、binding 是否授权该 action、actor / bot / workspace 是否允许、是否需要人工审批。EBA 还可能预留 `delivery.requested`（请求投递到某 surface）。

Delivery 方面，event 不一定回复到当前聊天窗口：消息事件通常带 reply target；系统事件可能没有默认 reply target，需要 runner 返回 `action.requested` 或由 binding 的 delivery policy 决定投递位置（`DeliveryContext` 见 PROTOCOL_V1 §5.7）。

## 7. 与 Context 协议的关系

EBA 事件进入 AgentRunner 时仍遵循 [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md)：inline 当前事件、大 payload 用 raw/artifact ref、不默认 inline 完整 history、agent 按需通过 API 拉取、Host 保留 EventLog 和权限 guardrail。非消息事件可以被投影进 Transcript，但不能强制伪装为 user message；AgentRunner 根据 event type 自己决定是否纳入模型上下文。

## 8. 未来 EBA 完整落地需要

EventGateway 完整实现、EventRouter 与 BindingResolver 集成、`AgentBinding` 持久模型和 UI、`DeliveryContext` 完整实现、platform action permission model 和执行器、真实平台事件接入。

落地顺序：① 把当前 Pipeline 消息入口适配成 `message.received` event（已完成）→ ② 增加 `AgentBinding` 抽象，先由 current config 生成（已完成）→ ③ context builder 改为从 event + binding 构造（已完成）→ ④ 引入 EventLog / Transcript（已完成）→ ⑤ 增加非消息事件的协议测试，不接真实平台 → ⑥ 接入真实 EventRouter 和 platform action。
