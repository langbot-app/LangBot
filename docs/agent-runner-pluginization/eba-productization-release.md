# EBA 产品化与发布计划

更新：2026-09-05，适用于合并后的 `dev/4.11.x`。本文维护产品边界和剩余交付顺序；具体实现、提交与验证结果统一记录在 [STATUS.md](./STATUS.md)。原 2026-07-01 草案中的功能缺口和 Phase 编号不再作为当前排期。

## 产品模型

- **Bot**：平台连接、凭据和事件路由入口。用户在机器人上决定“发生什么时，使用哪个处理器”。
- **Processor**：可复用处理逻辑的上位概念，当前类型为 Agent 与 Pipeline。
- **Pipeline**：保留完整 Stage 链的消息处理器，提供预处理、AI、后处理、扩展和输出控制。
- **Agent**：独立配置对象，选择 AgentRunner 插件并配置事件范围、运行器与工具权限，可被多个 Bot 引用。
- **Workflow**：后续编排方向，当前尚无完整执行产品。
- **Solution**：后续分发单元，包含处理器、路由模板、依赖、变量和文档。

处理器入口聚合 Agent 与 Pipeline，不转换实体，不复制旧 Pipeline runner 配置生成 Agent。EBA 是内部术语，主要产品流程使用机器人、事件、处理器、流水线和工具等名称。

## 已完成的产品化基础

| 用户流程 | 当前实现 |
| --- | --- |
| 创建处理器 | Agent/Pipeline 类型选择、独立配置与统一详情工作台 |
| 选择运行器 | 已安装 Runner 动态 metadata、市场安装入口、安装进度/恢复和可用性反馈 |
| 配置 Agent | 运行器、运行器配置、事件与工具；基础信息在详情入口编辑 |
| 配置事件 | 分组事件选择、兼容目标过滤、路由排序、冲突提示和兜底匹配说明 |
| 验证行为 | 路由 dry-run、Agent 调试、Bot 配置中的平台事件调试；合成派发仍需遵循抑制真实出站的后端边界 |
| 理解故障 | 路由匹配/失败轨迹、Runner 状态、模型测试与调试错误反馈 |
| 首次使用 | 场景引导与插件化 Runner 安装流程 |
| 工具权限 | 自动事件工具、显式平台动作、普通工具白名单，运行时再次授权 |
| 存储诊断 | Core、Plugin Runtime、Box 分别报告拥有的目录与不可用状态 |

这张表表示代码已实现，不代表所有平台/provider 和首次安装组合均完成当前版本真实验收。页面契约见 [处理器与事件编排](../event-based-agents/08-agent-page-and-event-orchestration.md)，动作授权见 [平台工具](./PLATFORM_ACTION_TOOLS.md)。

## 4.11 发布收尾

| 顺序 | 工作 | 完成条件 |
| --- | --- | --- |
| 1 | 冻结跨仓库依赖 | 提交/确认 SDK 平台工具发现改动，固定配套 SDK 和 Runner 包，更新 Core 声明及 lock；验证 registry 或精确 commit 的干净安装 |
| 2 | 收敛自动化 | 按当前页面设计处理前端旧断言，执行 backend/SDK 定向测试、前端单测、类型检查及发布所需 lint/build/E2E |
| 3 | 验证用户路径 | 空白实例安装 Runner、创建 Agent/Pipeline、连接 Bot、保存路由、消息/非消息执行、工具允许与拒绝、错误诊断 |
| 4 | 补真实交互与平台证据 | 当前版本的选定平台媒体/回调、Dify continuation、外部 harness；记录支持、未支持、阻塞及未执行 |
| 5 | 完成生命周期 | EventLog/Transcript retention 调度、状态/文件清理、取消和重启后的行为有明确策略与测试 |

验收记录必须写明 Core/SDK/Runner 版本、操作系统、Runtime 连接方式、Box backend 和是否使用 editable 源码。真实平台测试、合成事件与 mock provider 测试分别记账。过去的成功报告不能自动作为当前 HEAD 的通过记录。

## Cloud 独立交付边界

当前 OSS 支持单 Workspace 多成员及固定 RBAC；Cloud 目录和计费归控制面，Core 负责资源作用域与执行边界。不能用 edition 字段或普通配置开启 OSS 多 Workspace。

当前业务隔离单位是 Workspace 与 execution generation；不要求依据旧草案额外创建 Tenant/Workspace/Namespace 三层同构表。目录、安装绑定、存储与执行作用域以 [多租户架构](../multi-tenant/workspace-multi-user-architecture.md) 为准。

生产激活仍需关闭：

- 插件和可配置出站目标的网络/SSRF 策略。
- Plugin installation 与 Box 各存储面真正的 byte/inode 硬配额。
- 普通业务写入贯穿提交的 generation fence、业务 outbox 和持久对象引用切换保障。
- 最终 Linux/cgroup、持久卷、数据库权限、容量、故障恢复与 24 小时 soak 验收。

完整清单见 [Cloud 剩余验证](../multi-tenant/cloud-v2-pending-verification.md)。存储统计、局部压力测试或 OSS 功能验收不能替代这些门禁。

## 后续产品方向

- **完整 Agent 管控面**：业务任务队列、唤醒、外部 harness daemon 管理、provider 登录态诊断和分布式执行。已有 run ledger/heartbeat/claim 是底座。
- **Workflow 与多 Agent**：先确定独立处理器或 Runner 扩展形式，再定义串并联、失败恢复、状态冲突和副作用幂等。
- **Solution 导入导出**：使用逻辑依赖和路由模板；导入时选择 Bot、模型和资源，不能保留源实例 UUID、凭据、token 或租户密钥。包格式与更新策略待定。
- **模型能力与评估**：国内 Provider reasoning 专项回归、reasoning token/生效策略记录、质量与延迟成本基线，见 [模型思考控制](../review/model-reasoning-control-design.md)。

这些方向不自动构成 4.11 OSS 发布前置条件，也不承诺旧草案中的 5.0/GA 版本号或日期。
