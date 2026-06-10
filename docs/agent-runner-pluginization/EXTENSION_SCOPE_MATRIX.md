# AgentRunner 外化扩展边界矩阵

本文用于回答一个问题：本分支只做 AgentRunner 外化时，哪些能力已经作为扩展底座完成，哪些由外部 EBA / Agent Platform / Runtime Control Plane 分支接入，后续分支接入时应该走哪个扩展点。

结论：本分支不实现完整 Agent Platform，也不实现完整 EBA。EBA 完整事件网关与事件路由由外部 EBA 分支联调。本分支必须把 runner 外化的 Host / SDK 边界做干净，让外部分支只需要接入持久模型、事件路由或 runtime task，而不需要重写 `AgentRunner Protocol v1`。

调度基数、Agent 复用、插件实例无状态、Pipeline adapter 和 fan-out 边界的单一事实源是 [PROTOCOL_V1.md](./PROTOCOL_V1.md) §13；本矩阵只说明后续能力应该接入哪个扩展点。

## 1. 分支边界

| 范围 | 本分支职责 | 不在本分支做 |
| --- | --- | --- |
| AgentRunner Protocol v1 | 定义 Host 调用 runner 的稳定合同：discovery、`AgentRunContext`、result stream、Host pull API、错误和权限边界。 | 不定义 Agent Platform 的产品数据库模型；不定义 runtime task queue。 |
| Host runner 外化底座 | 提供 `AgentEventEnvelope`、`AgentBinding` 运行投影、`run(event, binding)`、resource authorization、run-scoped session、EventLog / Transcript / Artifact / State。 | 不实现 EventGateway、scheduler、integration provider、Agent 管控面 UI。 |
| 当前 Pipeline 入口 | 通过 `QueryEntryAdapter` 把旧 Query / Pipeline config 投影成 event + binding，作为迁移期入口。 | 不继续把 Pipeline 当作长期 agent 配置中心。 |
| 官方 runner 插件 | 作为协议消费者验证 local-agent / 外部 harness runner 能接入 Host 基础设施。 | 不让官方 runner 的内部实现反向决定 Host / SDK 协议形态。 |

## 2. 扩展矩阵

| 能力 | 当前分支状态 | 后续归属 | 后续接入方式 | 禁止事项 |
| --- | --- | --- | --- | --- |
| Product `Agent` | 已有运行期 `AgentConfig` / `AgentBinding` 投影；还没有正式持久化产品对象。 | Agent Platform / binding persistence UI。 | 持久 Agent 保存 runner id、runner config、resource/state/delivery policy；运行前投影为 `AgentBinding`。 | 不把持久 Agent schema 加进 SDK 协议；插件实例边界见 PROTOCOL_V1 §13。 |
| Bot / channel 绑定 Agent | 已有单次运行前的 `AgentBinding` 解析投影；目标调度语义见 PROTOCOL_V1 §13。 | EBA / Agent Platform。 | EventRouter 根据 bot、channel、workspace、conversation、event type 解析有效 `AgentBinding`。 | 不在本矩阵重定义 fan-out / observer 语义；需要时按 §3 新增设计。 |
| Agent session / run | 当前只有 `run_id` 和 active `AgentRunSessionRegistry`，用于权限校验和生命周期。 | Agent Platform / Runtime Control Plane。 | 如需要可新增持久 `AgentRun` / `AgentSession` / task 表，但执行仍回到 `run(event, binding)` 或 runtime-managed 等价入口。 | 不把持久 session 字段塞进 `AgentRunContext` 顶层；不要求所有 runner 长期持有 LangBot session。 |
| EventLog / Transcript / Artifact | 已完成 Host-owned store 和 pull API；runner 不直接写 DB。 | 本分支持续维护底座；Agent Platform 可复用。 | 外部 EBA、scheduler、integration、runtime task 都写同一套 EventLog / Transcript / Artifact。 | 不让 runner / sandbox 直接访问 Host DB；不把大 payload 内联进 prompt。 |
| Host-owned state / storage | 已有 state snapshot、`state.updated` 处理和 State API；storage 作为授权能力保留。 | 本分支持续维护底座；Runtime / Platform 可复用。 | 外部 session id、working directory、checkpoint 等小 JSON 用 state；大对象用 storage / artifact。 | 不把跨轮次状态存在插件实例内；不绕过 run-scoped authorization。 |
| EventGateway / EventRouter | 本分支只提供 event-first envelope 和 `run(event, binding)` 入口。 | EBA 分支（联调中）。 | EventGateway 规范化平台/WebUI/API/scheduler 事件；EventRouter 解析一个 binding；调用现有 orchestrator。 | 不为 EBA 新增另一套 runner 调用协议；不把非消息事件伪装成 user message。 |
| Scheduler / Automation | 不实现。文档中只把 `scheduler` 作为 future event source。 | EBA / Agent Platform。 | 定时任务触发 `schedule.triggered` host event，复用 EventGateway -> EventRouter -> `run(event, binding)`。 | 不直接调用某个 runner 插件；不绕过 EventLog / authorization。 |
| Integration provider | 不实现。IM platform adapter 仍是当前平台接入系统。 | EBA / Agent Platform。 | OAuth/webhook/outbound provider 应先转成 canonical host event 或 platform action，再交给 AgentRunner。 | 不把 Linear/Slack/GitHub 等 provider 私有 payload 扩散到 runner 协议顶层。 |
| Platform action / delivery | `action.requested` 已预留但当前仅 telemetry，不执行。`DeliveryContext` 只作为上下文/策略投影。 | EBA / platform action executor。 | 后续 executor 校验 runner capability、binding policy、actor/bot/workspace 权限和审批后执行。 | 不让 runner 直接调用平台 adapter 私有 API；不把平台动作伪装成文本回复副作用。 |
| Runtime registry / worker / task queue | 不实现。当前 Claude Code / Codex 是本机 subprocess MVP path。 | Runtime Control Plane v2。 | 第一阶段先补 Host-owned `AgentRun` / `AgentRunEvent` / run control primitives；完整 runtime registry、heartbeat、task queue、daemon claim、progress/audit 是后续可选阶段。 | 不把 heartbeat/task/warm pool 放进 Protocol v1；不让管理插件拥有 runtime/task 事实源。 |
| Warm pool / reconcile / diagnose | 不实现。 | Runtime Control Plane v2 / deployment layer。 | 作为 task/runtime 的运维能力，围绕 Host-owned runtime/task/audit 表实现。 | 不把 runtime 运维语义写进普通 runner 协议；不把 pod/task 细节泄漏给普通 runner。 |
| Agent memory | 不实现通用长期记忆产品层；提供 history/state/storage/artifact 基础能力。 | Agent Platform 或具体 runner/plugin。 | 平台 memory 可通过 Host storage/state 或独立产品表实现，runner 通过授权 API 拉取。 | 不在 Host core 内置通用 agentic memory 策略；不默认把 memory 全量 inline 到 context。 |
| External harness native session | 已支持 external session id / working directory state handoff 和 resource projection。 | 官方 runner 后续增强；Runtime Control Plane v2 可接管执行。 | 一次性 CLI runner 可继续走 `runner.run(ctx)`；长连接/daemon 模式按 external session key 串行 turn，reader 独占 native stream。 | 不把 Claude/Codex native wire 变成 LangBot 协议；全局锁边界见 PROTOCOL_V1 §13。 |

## 3. 后续分支接入规则

外部 EBA、Agent Platform 或 Runtime Control Plane 分支接入时，默认遵守以下规则：

- 新入口只生产或解析 Host 内部模型：`AgentEventEnvelope`、持久 Agent 投影出的 `AgentBinding`、以及必要的 delivery/resource/state policy。
- runner 调用仍走 `AgentRunOrchestrator.run(event, binding)`，除非 Runtime Control Plane 明确引入 runtime-managed 执行模式；即便如此，runner 可见合同仍应保持 Protocol v1。
- Host-owned facts 继续写入 EventLog / Transcript / Artifact / State；产品层可以新增更高阶视图，但不能替代这些事实源。
- 新能力如果需要持久化，优先加 Host-owned 表或 service；不要把事实源藏在插件 storage 或 runner subprocess 内。
- 新 result type 可以按 Protocol v1 的演进规则增加；不能用入口 adapter 私有字段绕过 schema。
- 任何 fan-out、observer agent、parallel arbitration、platform action execution 都必须单独定义 delivery、state conflict、approval 和 audit 语义。

## 4. 与 LiteLLM Agent Platform 的关系

这里的 LiteLLM Agent Platform 指面向 agent 产品层的实体拆分：`Agent` 描述可配置 agent，`Session` / `SessionMessage` 描述会话事实，`Automation` 描述自动触发，`IntegrationBinding` 描述外部集成连接，`Memory` 描述长期记忆，`WarmTask` 描述预热/后台任务。这些拆分对 LangBot 后续产品层有参考价值，但不能直接搬进本分支。

LangBot 当前分支的对应目标是更底层的：把 IM/WebUI/API 等入口统一投影到 Host event，把 Agent / binding 配置统一投影到 runner binding，把 runner 能力统一收束到 Protocol v1。完整 Agent Platform 可以在这个底座之上构建，而不应反过来污染本分支的 runner 外化边界。
