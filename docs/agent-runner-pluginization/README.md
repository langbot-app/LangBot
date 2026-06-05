# Agent Runner 插件化文档入口

本文档是 agent-runner 插件化工作的路由页。具体设计拆到独立文档中维护，避免把 LangBot 宿主架构、SDK 协议、上下文管理、EBA 预留和官方 runner 迁移混在同一份 README 里。

## 背景与问题

旧 runner 路径主要围绕 Pipeline / Query 和 `pkg/provider/runners` 内置实现展开，扩展外部 agent runtime 时容易把 runner 选择、上下文裁剪、资源授权和消息投递绑在同一条聊天链路里。这个分支要把 LangBot 收敛成 Agent Host：Host 负责事件、绑定、授权、事实源和结果投递；AgentRunner 作为插件或外部 harness 消费统一协议并自主管理 prompt / history / memory。

## 文档维护原则（单一事实源）

- **协议数据结构（schema）唯一定义在 [PROTOCOL_V1.md](./PROTOCOL_V1.md)。** 其他文档不得重抄 schema，只能引用，例如"见 PROTOCOL_V1 §4.2"。
- **实现状态唯一记录在 [PROGRESS.md](./PROGRESS.md)。** 规范类文档不维护"当前状态/✅"段落。
- Host 内部模型（`AgentEventEnvelope`、`AgentBinding`、Descriptor、各 Store）定义在 [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md)，不属于 SDK 协议。
- 其余专题文档只讲"为什么/边界/怎么用"，避免重复叙述。

## 本分支目标

**本分支目标：AgentRunner 外化 / 插件化基础设施**

本分支只做 LangBot 作为 Agent Host 的基础能力建设，为后续用 `Agent`
替代 Pipeline 承载 agent 配置打底：

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

本分支与后续 EBA / Agent Platform / Runtime Control Plane 的扩展边界见 [EXTENSION_SCOPE_MATRIX.md](./EXTENSION_SCOPE_MATRIX.md)。

## 目标产品模型

未来产品层应把 `Agent` 理解为 Pipeline 的替代物：原先 bot 绑定 Pipeline，Pipeline 携带 agent/provider/RAG/tool 等配置；后续应改为 bot 或 IM channel 绑定一个 Agent，Agent 携带 runner id、runner config、resource/state/delivery policy 等 agent 配置。

调度基数、Agent 复用、插件实例无状态、Pipeline adapter 和 fan-out 边界的规范来源是 [PROTOCOL_V1.md](./PROTOCOL_V1.md) §13；README 不复写这些约束。

## 当前入口关系

**当前 Pipeline 是入口 adapter，不再是 agent runner 设计核心。**

主入口仍可由 Pipeline 触发，但内部已转换成 event-first path：`run_from_query()` 经 `QueryEntryAdapter` 把 `Query` 转换为 `AgentEventEnvelope` + `AgentBinding`，再委托到统一的 `run(event, binding, ...)`。Pipeline path 因此获得了 event-first host capabilities（EventLog / Transcript / ArtifactStore / PersistentStateStore 写入，History / Event / Artifact / State pull API 可用）。

详细实现进度、已验收能力和未完成收尾见 [PROGRESS.md](./PROGRESS.md)。

## 术语表

| 术语 | 含义 |
| --- | --- |
| Protocol v1 | Host 调用 AgentRunner 的 runner 可见合同：discovery、`AgentRunContext`、result stream、Host pull API 和错误模型。 |
| Agent | 目标产品层配置对象，保存 runner id、runner config 和资源/状态/投递策略；不等于插件实例。 |
| AgentConfig | Host 内部迁移期配置投影，由当前 Pipeline config 或未来持久 Agent 生成。 |
| AgentBinding / binding | Host 在一次事件运行前解析出的有效绑定，决定调用哪个 runner 以及带什么策略。 |
| envelope | Host 内部事件封装，即 `AgentEventEnvelope`；runner 看到的是由它投影出的 `ctx.event`。 |
| descriptor / manifest | runner discovery 的能力和配置描述；manifest 来自插件，descriptor 是 Host 校验后的注册表视图。 |
| EBA | Event Based Agent，未来把消息、撤回、入群、定时任务等都统一成 host event 的接入方向。 |
| harness runner | Claude Code、Codex 等已有自身 session / tool loop / MCP / 压缩机制的外部 runtime adapter。 |
| projection | Host 把内部事实源、授权资源或配置裁剪成 runner / harness 可消费视图的过程。 |
| `static_refs` | KV cache 友好的静态上下文引用，例如 system policy、tool schema、resource manifest 的 hash/version。 |
| Runtime Control Plane | v2 Host 能力层，负责 runtime registry、heartbeat、task queue、progress/cancel 和 audit；不是 Protocol v1 主线。 |

## 设计文档

| 文档 | 关注点 |
| --- | --- |
| [PROTOCOL_V1.md](./PROTOCOL_V1.md) | **🔒 唯一 schema 事实源**。LangBot Host 与 SDK / Runtime / AgentRunner 的协议合同：版本协商、discovery、run context、result stream、proxy actions、错误和 adapter 边界。 |
| [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md) | LangBot 宿主能力与分层架构、Host 内部模型（`AgentEventEnvelope` / `AgentBinding` / Descriptor / 各 Store）、runner 发现、绑定、资源授权、状态、存储、生命周期和调用链。 |
| [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md) | Agent-owned context 方向：事件到来时 LangBot 传什么，agent 如何按需拉取更多历史 / artifact / state，以及如何支持 KV cache 友好的上下文管理。 |
| [EXTENSION_SCOPE_MATRIX.md](./EXTENSION_SCOPE_MATRIX.md) | AgentRunner 外化与后续 EBA / Agent Platform / Runtime Control Plane 的扩展边界矩阵，说明哪些是本分支底座、哪些由后续分支接入。 |
| [EVENT_BASED_AGENT.md](./EVENT_BASED_AGENT.md) | EBA 预留：事件模型、事件来源、触发绑定、非消息事件如何复用 AgentRunner 调度。**标注为 future design note**。 |
| [RUNTIME_CONTROL_PLANE_V2.md](./RUNTIME_CONTROL_PLANE_V2.md) | Agent Platform v2 / runtime 管控面预留：Host 新增 runtime registry、heartbeat、task queue、daemon 执行和 audit；管理插件构建在这些 Host 能力之上。**标注为 future design note**。 |
| [OFFICIAL_RUNNER_PLUGINS.md](./OFFICIAL_RUNNER_PLUGINS.md) | 官方 runner 插件迁移，包括 local-agent 和外部 runner。它是下游落地计划，不是 LangBot 基础能力设计的前置约束。 |
| [AGENT_RUNNER_QA_GUIDE.md](./AGENT_RUNNER_QA_GUIDE.md) | Agent Runner QA 指南：保留最高价值测试路径，指导 agent 开展下一轮 WebUI / runner smoke 验证。 |
| [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) | 安全发布级 hardening 的后续发布门槛：路径隔离、权限边界、secret、资源配额、MCP / skill 投影和审计。 |
| [PROGRESS.md](./PROGRESS.md) | **🔒 唯一状态事实源**。当前实现进度、已验收能力、未完成收尾和非本分支范围。 |

## 工作拆分

### 1. LangBot + SDK 基础设施

目标是把 LangBot 从内置 runner 执行器变成 agent host：

- LangBot 与 SDK 的稳定协议合同
- runner manifest / descriptor / registry
- Agent / binding 配置解析
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

EBA dispatch 的基数和 fan-out 边界仍以 PROTOCOL_V1 §13 为准；本文档只列出本分支为 EBA 预留的入口点。

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

## 约束事实源

本分支已确认约束不在 README 重写：

- Runner 可见协议、result stream 和调度边界见 [PROTOCOL_V1.md](./PROTOCOL_V1.md)。
- Host 内部 `AgentConfig` / `AgentBinding` 投影见 [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md)。
- 后续 EBA / Agent Platform / Runtime Control Plane 接入边界见 [EXTENSION_SCOPE_MATRIX.md](./EXTENSION_SCOPE_MATRIX.md)。
