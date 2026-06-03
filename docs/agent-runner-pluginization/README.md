# Agent Runner 插件化文档入口

本文档是 agent-runner 插件化工作的路由页。具体设计拆到独立文档中维护，避免把 LangBot 宿主架构、SDK 协议、上下文管理、EBA 预留和官方 runner 迁移混在同一份 README 里。

## 文档维护原则（单一事实源）

- **协议数据结构（schema）唯一定义在 [PROTOCOL_V1.md](./PROTOCOL_V1.md)。** 其他文档不得重抄 schema，只能引用，例如"见 PROTOCOL_V1 §4.2"。
- **实现状态唯一记录在 [PROGRESS.md](./PROGRESS.md)。** 规范类文档不维护"当前状态/✅"段落。
- Host 内部模型（`AgentEventEnvelope`、`AgentBinding`、Descriptor、各 Store）定义在 [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md)，不属于 SDK 协议。
- 其余专题文档只讲"为什么/边界/怎么用"，避免重复叙述。

## 本分支目标

**本分支目标：AgentRunner 外化 / 插件化基础设施**

本分支只做 LangBot 作为 Agent Host 的基础能力建设：

- LangBot 与 SDK 的稳定协议合同（Protocol v1）
- Host-side `AgentEventEnvelope` / `AgentBinding` 模型
- `run(event, binding)` event-first 入口
- `QueryEntryAdapter`：Query → AgentEventEnvelope + AgentBinding
- EventLog / Transcript / ArtifactStore / PersistentStateStore
- History / Event / Artifact / State pull APIs
- SDK runtime forwarding pull APIs + `caller_plugin_identity` 验证路径

## 本分支不实现

以下能力由其他分支负责，本分支只预留 integration point：

- **EventGateway**：完整事件网关实现、事件路由、事件持久化管理
- **Event subscription / Event notification**：事件订阅、推送通知
- **BindingResolver persistence UI**：绑定配置的持久化 UI 和 event router 集成（如由其他模块负责）
- **Scheduler / Background event source**：定时任务、后台事件源
- **Runtime control plane v2**：runtime registry、heartbeat、task queue、daemon claim、progress/cancel 和 runtime audit

EventGateway 在本文档中描述为 **future integration point**，由外部 event branch 提供。本分支只定义 host-side envelope/binding models 和 `run(event, binding)` orchestrator 入口。

## 当前状态

**当前 Pipeline 是入口 adapter，不再是 agent runner 设计核心。**

主入口仍可由 Pipeline 触发，但内部已转换成 event-first path：`run_from_query()` 经 `QueryEntryAdapter` 把 `Query` 转换为 `AgentEventEnvelope` + `AgentBinding`，再委托到统一的 `run(event, binding, ...)`。Pipeline path 因此获得了 event-first host capabilities（EventLog / Transcript / ArtifactStore / PersistentStateStore 写入，History / Event / Artifact / State pull API 可用）。

详细实现进度、已验收能力和未完成收尾见 [PROGRESS.md](./PROGRESS.md)。

## 设计文档

| 文档 | 关注点 |
| --- | --- |
| [PROTOCOL_V1.md](./PROTOCOL_V1.md) | **🔒 唯一 schema 事实源**。LangBot Host 与 SDK / Runtime / AgentRunner 的协议合同：版本协商、discovery、run context、result stream、proxy actions、错误和 adapter 边界。 |
| [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md) | LangBot 宿主能力与分层架构、Host 内部模型（`AgentEventEnvelope` / `AgentBinding` / Descriptor / 各 Store）、runner 发现、绑定、资源授权、状态、存储、生命周期和调用链。 |
| [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md) | Agent-owned context 方向：事件到来时 LangBot 传什么，agent 如何按需拉取更多历史 / artifact / state，以及如何支持 KV cache 友好的上下文管理。 |
| [EVENT_BASED_AGENT.md](./EVENT_BASED_AGENT.md) | EBA 预留：事件模型、事件来源、触发绑定、非消息事件如何复用 AgentRunner 调度。**标注为 future design note**。 |
| [RUNTIME_CONTROL_PLANE_V2.md](./RUNTIME_CONTROL_PLANE_V2.md) | Agent Platform v2 / runtime 管控面预留：Host 新增 runtime registry、heartbeat、task queue、daemon 执行和 audit；管理插件构建在这些 Host 能力之上。**标注为 future design note**。 |
| [OFFICIAL_RUNNER_PLUGINS.md](./OFFICIAL_RUNNER_PLUGINS.md) | 官方 runner 插件迁移，包括 local-agent 和外部 runner。它是下游落地计划，不是 LangBot 基础能力设计的前置约束。 |
| [PHASE1_QA_ACCEPTANCE_MATRIX.md](./PHASE1_QA_ACCEPTANCE_MATRIX.md) | Agent Runner QA 指南：保留最高价值测试路径，指导 agent 开展下一轮 WebUI / runner smoke 验证。 |
| [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) | 安全发布级 hardening 的后续发布门槛：路径隔离、权限边界、secret、资源配额、MCP / skill 投影和审计。 |
| [PROGRESS.md](./PROGRESS.md) | **🔒 唯一状态事实源**。当前实现进度、已验收能力、未完成收尾和非本分支范围。 |

## 工作拆分

### 1. LangBot + SDK 基础设施

目标是把 LangBot 从内置 runner 执行器变成 agent host：

- LangBot 与 SDK 的稳定协议合同
- runner manifest / descriptor / registry
- agent binding 与配置解析
- run orchestration 和生命周期管理
- resource authorization 与 `run_id` 级权限校验
- host-owned state / storage / event log / transcript / artifact 能力
- SDK `AgentRunner`、`AgentRunContext`、`AgentRunResult`、`AgentRunAPIProxy`

协议合同详见 [PROTOCOL_V1.md](./PROTOCOL_V1.md)。

详见 [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md)。

### 2. Agent-owned context

LangBot 不应成为最终 agentic context manager。它应提供事实源、默认上下文引用和按需读取 API；agent 或其背后的 runtime 负责历史剪裁、摘要、召回和 KV cache 策略。

Host 不定义通用历史窗口字段或策略；runner 通过 Host pull API 按需拉取历史并自行管理 working context。

详见 [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md)。

### 3. Event Based Agent（Future）

消息只是事件的一种。后续 `message.received`、`message.recalled`、`group.member_joined`、`friend.request_received` 等事件都应能通过统一事件 envelope 触发 AgentRunner。

**本分支不实现 EBA 完整能力，只预留：**
- event-first envelope (`AgentEventEnvelope`)
- AgentBinding model
- `run(event, binding)` 入口
- QueryEntryAdapter（当前 AgentEventEnvelope / AgentBinding 的 Query entry adapter source）

详见 [EVENT_BASED_AGENT.md](./EVENT_BASED_AGENT.md)。

### 4. 官方 runner 插件

官方 `local-agent` 和外部 runner 迁移是下游工作。它们需要依附 LangBot 提供的宿主能力，但不应反过来决定宿主协议。

`local-agent` 可以外移，也可以重写。验收重点是它能完整消费 LangBot 的模型、工具、知识库、存储、事件、history API 和 result stream，而不是保留旧内置 runner 的内部结构。

详见 [OFFICIAL_RUNNER_PLUGINS.md](./OFFICIAL_RUNNER_PLUGINS.md)。

### 5. Runtime Control Plane v2（Future）

当前 AgentRunner v1 主线只负责 `event -> binding -> runner.run(ctx) -> result stream`。
后续 Agent Platform v2 可以在 Host 侧新增 runtime registry、heartbeat、task queue、daemon claim、progress/cancel 和 runtime audit。

在这些 Host 能力之上，可以构建独立 agent 管控面插件；插件负责 UI、策略和编排体验，runtime/task 的事实源仍由 Host 持有。

详见 [RUNTIME_CONTROL_PLANE_V2.md](./RUNTIME_CONTROL_PLANE_V2.md)。

## 已确认决策

- 一个插件可以声明多个 `AgentRunner` 组件，每个组件独立暴露 manifest、配置 schema、能力和权限。
- 插件本身按单实例、无状态执行单元理解；不同绑定不创建多个插件实例。
- 绑定只保存 runner id 和绑定配置，不代表插件实例状态。
- LangBot 可以提供 host-owned state / storage 能力，让 runner 把状态寄宿在 LangBot；但这应该是授权能力，不是强制要求。
- 官方 runner 插件是协议消费者，不是协议设计的优先约束。
- Pipeline 是当前入口 adapter，不是未来架构中心。
- EventGateway 是 future integration point，由外部 event branch 提供。
- Runtime control plane 是 v2 Host capability layer，不阻塞当前 AgentRunner v1 主线；agent 管控面插件应构建在该 Host 能力层之上。
