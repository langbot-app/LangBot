# AgentRunner 与产品扩展边界

更新：2026-09-05，适用于 `dev/4.11.x`。EBA、独立 Agent、Bot 事件绑定和处理器 UI 已与 AgentRunner 插件化合并。当前状态和测试证据以 [STATUS.md](./STATUS.md) 为准；runner 可见 schema 与调度基数以 [PROTOCOL_V1.md](./PROTOCOL_V1.md) 为准。

## 当前职责

| 层 | 已实现职责 | 边界 |
| --- | --- | --- |
| LangBot 产品层 | 独立 Agent CRUD、Pipeline、处理器工作台、Bot 事件绑定、Runner 安装与调试 | Agent 与 Pipeline 各自持久化；聚合列表不转换实体 |
| 平台层 | 适配器事件转换、能力声明、observer 广播、路由匹配、平台 API 与回复 | 路由逻辑在 RuntimeBot；不为每个入口重建 runner 协议 |
| Host Agent 底座 | envelope/binding 投影、统一编排、资源授权、run session、EventLog/Transcript/State、run/result ledger | SDK 不持有 Host 私有 Query 或数据库 |
| SDK / Plugin Runtime | typed contract、AgentRunner 组件和脚手架、proxy、MCP bridge、结果流转发、installation worker 管理 | 具体 Agent 执行策略由 Runner 插件承担 |
| Box Runtime | 沙盒会话、文件、托管进程、Skill、资源限制与作用域 | 不等于外部 harness 的通用托管承诺；存储统计不等于硬配额 |

## 已有能力与后续扩展

| 能力 | 当前状态 | 后续工作与接入点 |
| --- | --- | --- |
| Agent / binding | Agent 表、API、配置 UI、Bot event_bindings 已存在；AgentBinding 是运行投影 | 新产品模型复用现有投影，不把 Pipeline 持久化成 Agent |
| 事件路由 | observer 广播后按 pattern/filter/priority 选择一个 Pipeline、Agent 或 discard | 通用订阅、通知和其他事件源仍需单独设计 |
| 平台动作 | event_* 冻结目标，platform_* 显式授权；通过 Host 工具调用 | 新动作先定义语义、schema 和授权，不开放任意原始 action |
| 结构化交互 | interaction.requested 白名单、持久回调关联、TTL/作用域/幂等、原处理器恢复 | 补真实 provider/platform 验收；其它 action.requested 仍仅 telemetry |
| Run / runtime | 持久 AgentRun/AgentRunEvent、取消/结果/终态、heartbeat/claim/reconcile 原语 | 业务队列、任务生产、唤醒、跨 Host 执行和运维产品面 |
| Plugin worker | 独立安装进程、依赖环境、supervisor、退避及重启协调器 | 最终部署故障注入、出站网络策略及硬存储配额 |
| External harness | 通过 Runner 消费协议、按 run 访问 Host 资源 | 通用 daemon supervisor、登录态诊断、分布式调度；不要与 Plugin worker 混淆 |
| History / state / storage | Host 事实源、按需读取、state/checkpoint、sandbox 文件能力 | EventLog/Transcript 的定时 retention 接入和完整文件生命周期 |
| Scheduler / Automation | 仅保留可扩展的事件入口 | 用户定时任务必须走事件、授权和运行记录链路，不直调插件绕过 Host |
| Workflow / 多 Agent | 尚无完整产品实现 | 先定义串并联、失败恢复、投递与状态冲突语义 |
| Solution | 尚无导出/导入实现 | 处理器、路由模板、依赖、变量与文档；不导出凭据或已安装 UUID |
| 长期 memory 产品 | 提供 history/state/storage 基础 | 由 Runner 或后续产品定义召回策略，不把全量 memory 默认塞入 context |
| Cloud | 作用域与运行时隔离底座已合入；OSS 为单 Workspace 多成员 | 生产激活独立通过网络、硬配额、事务代次切换和部署验收 |

平台动作详见 [PLATFORM_ACTION_TOOLS.md](./PLATFORM_ACTION_TOOLS.md)，控制面规划详见 [RUNTIME_CONTROL_PLANE_V2.md](./RUNTIME_CONTROL_PLANE_V2.md)，Cloud 门禁见 [剩余验证清单](../multi-tenant/cloud-v2-pending-verification.md)。

## 扩展规则

- 新入口构造 Host event 和有效 binding，继续调用统一 orchestrator；Pipeline AI Stage 使用 QueryEntryAdapter。
- Host 保持 run/result、授权、事件、状态和历史的事实源；插件负责自己的执行策略及 provider 私有 continuation。
- 新增业务表、调度或 UI 不要求修改 runner 可见协议；需要协议扩展时先更新 canonical spec，再同步 SDK、Runtime、模板与测试。
- fan-out、并行仲裁和自动重试必须明确副作用、幂等、状态冲突和审计语义，不能通过多个隐式回复者实现。
- 外部 harness 自带 shell、文件系统和网络权限由部署环境负责；manifest permissions 约束的是 LangBot 持有的资源。
