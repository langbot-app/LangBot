# Agent Runner 插件化文档入口

本文档是 agent-runner 插件化工作的路由页。具体设计拆到独立文档中维护，避免把 LangBot 宿主架构、SDK 协议、上下文管理、EBA 预留和官方 runner 迁移混在同一份 README 里。

## 核心方向

LangBot 的目标不是把旧 Pipeline runner 机制简单搬进插件系统，而是逐步转为一个面向 Agent 的宿主层：

- LangBot 负责 IM / WebUI / API / 未来事件入口、会话和身份解析、权限、存储、资源授权、运行生命周期、结果投递和审计。
- SDK 负责定义 AgentRunner 组件协议、上下文实体、返回事件流、运行期受限 API 和插件 runtime 协作方式。
- AgentRunner 负责具体 agent runtime 的上下文策略、prompt 组装、压缩、召回、模型调用策略和业务行为。

后续会逐步弱化 Pipeline。当前 Pipeline 只能视为现有消息入口和兼容层，不应作为新架构设计的中心假设。

## 设计文档

| 文档 | 关注点 |
| --- | --- |
| [PROTOCOL_V1.md](./PROTOCOL_V1.md) | LangBot Host 与 SDK / Runtime / AgentRunner 的协议合同：discovery、run context、result stream、proxy actions、错误和兼容边界。 |
| [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md) | LangBot 宿主能力、SDK 协议、runner 发现、绑定、权限、状态、存储、生命周期和调用链。 |
| [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md) | Agent-owned context 方向：事件到来时 LangBot 传什么，agent 如何按需拉取更多历史 / artifact / state，以及如何支持 KV cache 友好的上下文管理。 |
| [EVENT_BASED_AGENT.md](./EVENT_BASED_AGENT.md) | EBA 预留：事件模型、事件来源、触发绑定、非消息事件如何复用 AgentRunner 调度。 |
| [OFFICIAL_RUNNER_PLUGINS.md](./OFFICIAL_RUNNER_PLUGINS.md) | 官方 runner 插件迁移，包括 local-agent 和外部 runner。它是下游落地计划，不是 LangBot 基础能力设计的前置约束。 |
| [PHASE1_QA_ACCEPTANCE_MATRIX.md](./PHASE1_QA_ACCEPTANCE_MATRIX.md) | 当前阶段的 QA 验收矩阵。它验证现有分支的兼容性，不代表最终架构边界。 |

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

当前代码中的 legacy `max-round` 只能视为旧 Pipeline 兼容行为，不应作为目标协议继续扩展。

详见 [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md)。

### 3. Event Based Agent

消息只是事件的一种。后续 `message.received`、`message.recalled`、`group.member_joined`、`friend.request_received` 等事件都应能通过统一事件 envelope 触发 AgentRunner。

EBA 设计要复用同一套 runner registry、resource authorization、session registry、state 更新、result normalization 和 delivery lifecycle，不能另起一套调用协议。

详见 [EVENT_BASED_AGENT.md](./EVENT_BASED_AGENT.md)。

### 4. 官方 runner 插件

官方 `local-agent` 和外部 runner 迁移是下游工作。它们需要依附 LangBot 提供的宿主能力，但不应反过来决定宿主协议。

`local-agent` 可以外移，也可以重写。验收重点是它能完整消费 LangBot 的模型、工具、知识库、存储、事件、history API 和 result stream，而不是保留旧内置 runner 的内部结构。

详见 [OFFICIAL_RUNNER_PLUGINS.md](./OFFICIAL_RUNNER_PLUGINS.md)。

## 当前实现状态

当前分支已经具备一部分基础设施：

- LangBot 已有 `AgentRunnerRegistry`、`AgentRunOrchestrator`、`AgentRunContextBuilder`、`AgentResourceBuilder`、`AgentResultNormalizer`。
- `ChatMessageHandler` 主路径已经委托 orchestrator。
- Pipeline metadata 已经能从 registry 动态生成 runner 选项和配置 stage。
- SDK 已有 Protocol v1 的 `AgentRunContext`、`AgentRunResult`、capabilities、permissions、`AgentRunAPIProxy`。
- 宿主侧已有 `run_id` session registry，用于模型、工具、知识库、storage 等 runtime action 的授权校验。

仍需要从当前实现中继续剥离的部分：

- Pipeline 绑定仍是当前主要入口，后续需要抽象为通用 `AgentBinding`。
- `AgentRunContext` 仍带有旧 Query / Pipeline 语义，需要迁移到 event-first envelope。
- context packaging 仍受 legacy `max-round` 影响，后续应改为 context reference + pull API。
- state store 当前是进程内实现，需要明确 host storage backend。
- artifact / transcript / event log 还没有成为完整宿主能力。

## 已确认决策

- 一个插件可以声明多个 `AgentRunner` 组件，每个组件独立暴露 manifest、配置 schema、能力和权限。
- 插件本身按单实例、无状态执行单元理解；不同绑定不创建多个插件实例。
- 绑定只保存 runner id 和绑定配置，不代表插件实例状态。
- LangBot 可以提供 host-owned state / storage 能力，让 runner 把状态寄宿在 LangBot；但这应该是授权能力，不是强制要求。
- 官方 runner 插件是协议消费者，不是协议设计的优先约束。
- Pipeline 是当前兼容入口，不是未来架构中心。
