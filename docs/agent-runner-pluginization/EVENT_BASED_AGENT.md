# Event Based Agent 接入设计

> 本文记录 EBA 如何接入当前 AgentRunner Protocol v1 / Host 底座。EventGateway、EventRouter、Event subscription/notification 由外部 EBA 分支实现并联调；本分支只保留 event-first 入口和 envelope/binding models。
>
> 数据结构唯一定义在 [PROTOCOL_V1.md](./PROTOCOL_V1.md)（runner 可见）与 [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md)（Host 内部模型）；本文只讲 EBA 语义，不重抄 schema。
> 与当前 runner 外化分支、后续 Agent Platform / Runtime Control Plane 的边界见 [EXTENSION_SCOPE_MATRIX.md](./EXTENSION_SCOPE_MATRIX.md)。

本文描述 EBA 接入时，事件如何进入 LangBot、如何在平级的 Pipeline / Agent 处理器之间路由，以及 Agent 分支如何复用插件化 AgentRunner 基础设施。本分支不实现完整 EventBus / EventRouter / Platform API；这些能力正在外部 EBA 分支联调。这里的目标是把处理器路由与 runner 协议边界说清楚。

## 1. 设计目标

- 消息、撤回、入群、好友申请、定时任务、API 调用都能抽象为 host event。
- EventRouter 可以根据 event type、bot、workspace、conversation、actor、subject 选择一个 Pipeline 或 Agent 处理器。
- Pipeline 目标执行完整消息 Stage 链；Agent 目标通过统一 orchestrator 调用 AgentRunner。
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
- EBA 持久路由通过 `event_pattern`、`filters`、`target_type` 和 `target_uuid` 选择处理器。只有 `target_type=agent`，或 Pipeline AI Stage 需要调用 runner 时，才进一步解析 `AgentBinding`（HOST_SDK §4.2）。

EBA 每个事件只选择一个有效处理器；AgentRunner 调用的基数、Agent 复用和 fan-out 边界以 PROTOCOL_V1 §13 为准。

路由 scope 示例：workspace 全局、bot 级、platform channel 级、conversation / group / thread 级、user / actor 级。Pipeline 是 `message.*` 场景的一等处理器，适合需要预处理、AI、后处理、扩展和输出控制的消息链路；Agent 是 runner 驱动的一等处理器，可处理其声明支持的消息与非消息事件。二者都不会被转换成对方。

Event Source 可包括：`platform_adapter`（飞书、QQ、微信、Telegram 等）、`webui`、`http_api`、`scheduler`、`system`。EventRouter 不应写死平台 adapter 的类名。

## 5. EventRouter 调用链

```text
Platform Adapter / WebUI / API
  -> Event Gateway normalize payload
  -> EventLog append raw event
  -> EventRouter resolve one Processor target
     -> target_type=pipeline: MessageAggregator -> QueryPool -> Pipeline stages
     -> target_type=agent: resolve AgentBinding -> AgentRunOrchestrator
        -> AgentRunContextBuilder -> PluginRuntimeConnector.run_agent()
        -> AgentRunResult stream
  -> DeliveryController render / platform action
```

约束：Pipeline 和 Agent 是 EventRouter 的平级目标；Pipeline 仅接受消息事件，Agent 受其事件能力声明约束。任何 AgentRunner 调用都必须复用现有 orchestrator，不能为 EBA 单独实现另一套 plugin runner 协议；非消息事件不能绕过 resource authorization；delivery 和 platform action 走统一权限模型；外部 harness runner 也通过同一套 envelope/binding/context/result 协议接入。observer / fan-out / parallel arbitration 的额外语义仍按 PROTOCOL_V1 §13 处理。

## 6. 平台动作执行

EBA 后 `action.requested`（PROTOCOL_V1 §7.3，当前仅 telemetry 不执行）将用于请求 host 执行平台动作：

```json
{ "type": "action.requested",
  "data": { "action": "friend.request.accept",
            "target": {"platform": "wechat", "request_id": "..."},
            "payload": {"reason": "policy matched"} } }
```

Host 必须校验：binding / platform action policy 是否授权该 action、actor / bot / workspace 是否允许、是否需要人工审批，以及当前 run session / caller identity 是否匹配。EBA 还可能预留 `delivery.requested`（请求投递到某 surface）。

Delivery 方面，event 不一定回复到当前聊天窗口：消息事件通常带 reply target；系统事件可能没有默认 reply target，需要 runner 返回 `action.requested` 或由 binding 的 delivery policy 决定投递位置（`DeliveryContext` 见 PROTOCOL_V1 §5.7）。
当前 Host 会把 adapter 声明的通用 API 投影到
`DeliveryContext.platform_capabilities.supported_apis`，并据此设置
`supports_edit` / `supports_reaction`。该投影只供 runner 选择输出形态，不构成
平台动作授权；合成测试 adapter 会移除副作用能力并抑制实际出站调用。

## 7. 与 Context 协议的关系

EBA 事件进入 AgentRunner 时仍遵循 [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md)：inline 当前事件、大 payload 用 raw/staged file ref、不默认 inline 完整 history、agent 按需通过 API 拉取、Host 保留 EventLog 和权限 guardrail。非消息事件可以被投影进 Transcript，但不能强制伪装为 user message；AgentRunner 根据 event type 自己决定是否纳入模型上下文。

## 8. 当前集成状态

当前分支已完成 EventRouter、Pipeline / Agent 平级处理器路由、Bot
`event_bindings` 持久化与 WebUI、AgentBinding 投影、路由 dry-run、合成测试事件、
运行状态和真实 OneBot 非消息事件到 Agent 的闭环。Pipeline 消息链和独立 Agent
均复用同一个 AgentRunner orchestrator / context / result 协议。

尚未落地的是 platform action permission model 和 `action.requested` 执行器；在显式
action allowlist、binding policy、adapter capability 和审批模型完成前，该 result 仍只
记录 telemetry，不执行平台副作用。
