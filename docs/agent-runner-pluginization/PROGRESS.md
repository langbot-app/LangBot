# Agent Runner 插件化实现进度

本文档跟踪 Agent Runner 插件化的实现状态，便于快速了解当前进度。

## 总体进度

**当前阶段**: Phase 3.5 已完成，Event-first 基础设施已完成；2026-05-29 已通过本地 `local-agent` 与 Claude Code runner smoke。

| Phase | 描述 | 状态 |
|-------|------|------|
| Phase 0 | PoC 验证 | ✅ 完成 |
| Phase 1 | 核心架构（Registry、Orchestrator、上下文模型） | ✅ 完成 |
| Phase 2 | 权限、能力声明、资源注入 | ✅ 完成 |
| Phase 3 | 内置 runner 迁移到插件 | ✅ 完成（7/7） |
| Phase 3.5 | Event-first 基础设施 | ✅ 完成 |
| Phase 3.6 | 外部 harness runner 协议 smoke | ✅ 完成（Claude Code MVP） |
| Phase 4 | EBA 事件支持 | 🔲 未开始（已预留 event-first 入口，EventGateway 由其他分支实现） |

---

## 详细状态

### SDK 侧 (`langbot-plugin-sdk`)

| 组件 | 状态 | 备注 |
|------|------|------|
| `AgentRunner` 组件 | ✅ | `api/definition/components/agent_runner/runner.py` |
| `AgentRunContext` | ✅ | `api/entities/builtin/agent_runner/context.py` |
| `AgentRunResult` | ✅ | `api/entities/builtin/agent_runner/result.py` |
| `AgentRunnerCapabilities` | ✅ | `api/entities/builtin/agent_runner/capabilities.py` |
| `AgentRunnerPermissions` | ✅ | `api/entities/builtin/agent_runner/permissions.py` |
| EBA 事件模型 (Event/Actor/Subject) | ✅ | `api/entities/builtin/agent_runner/event.py` |
| `LIST_AGENT_RUNNERS` action | ✅ | `runtime/io/handlers/control.py` |
| `RUN_AGENT` action | ✅ | `runtime/io/handlers/control.py` |
| `AgentRunAPIProxy` | ✅ | `api/proxies/agent_run_api.py` |
| Pull API handlers (State/History/Event/Artifact) | ✅ | `runtime/io/handlers/plugin.py` |
| `caller_plugin_identity` injection | ✅ | Pull API handlers inject caller identity |

### LangBot 侧

| 组件 | 状态 | 备注 |
|------|------|------|
| `AgentRunnerRegistry` | ✅ | `pkg/agent/runner/registry.py` |
| `AgentRunOrchestrator` | ✅ | `pkg/agent/runner/orchestrator.py` - event-first `run(event, binding)` |
| `AgentRunnerDescriptor` | ✅ | `pkg/agent/runner/descriptor.py` |
| `AgentResourceBuilder` | ✅ | `pkg/agent/runner/resource_builder.py` |
| `AgentRunContextBuilder` | ✅ | `pkg/agent/runner/context_builder.py` - event-first context |
| `AgentResultNormalizer` | ✅ | `pkg/agent/runner/result_normalizer.py` |
| `ConfigMigration` | ✅ | `pkg/agent/runner/config_migration.py` |
| `PipelineAdapter` | ✅ | `pkg/agent/runner/pipeline_adapter.py` - Query → Event + Binding |
| `run_from_query()` → `run(event, binding)` | ✅ | Pipeline 路径委托到 event-first path |
| `ChatMessageHandler` 集成 | ✅ | 使用 orchestrator 替代 wrapper |
| `PipelineService` 集成 | ✅ | 从 registry 获取 runner metadata |
| Plugin connector | ✅ | `list_agent_runners()` / `run_agent()` |
| `EventLogStore` | ✅ | `pkg/agent/runner/event_log_store.py` |
| `TranscriptStore` | ✅ | `pkg/agent/runner/transcript_store.py` |
| `ArtifactStore` | ✅ | `pkg/agent/runner/artifact_store.py` |
| `PersistentStateStore` | ✅ | `pkg/agent/runner/persistent_state_store.py` |
| History / Event pull APIs | ✅ | Orchestrator + APIProxy |
| Artifact pull APIs | ✅ | Orchestrator + APIProxy |
| State pull APIs | ✅ | Orchestrator + APIProxy |
| `artifact.created` / `state.updated` handling | ✅ | Event-first handlers in orchestrator |
| Pipeline path host capability coverage | ✅ | EventLog/Transcript/ArtifactStore/PersistentStateStore |
| External harness state handoff | ✅ | `external.session_id` / `external.working_directory` 写入 PersistentStateStore |

### 官方插件

> 外部服务插件仓库：`/home/glwuy/langbot-app/langbot-agent-runner/`  
> 本地 Local Agent 插件仓库：`/home/glwuy/langbot-app/langbot-local-agent/`

| 插件 | 状态 | 备注 |
|------|------|------|
| `local-agent` | ✅ 已完成 | 核心功能：模型、工具、知识库、流式、会话 |
| `dify-agent` | ✅ 已完成 | 支持 chat/agent/workflow 三种应用类型 |
| `n8n-agent` | ✅ 已完成 | Webhook 调用，支持 basic/jwt/header 认证 |
| `coze-agent` | ✅ 已完成 | 多模态输入，思维链处理 |
| `claude-code-agent` | ✅ MVP smoke 通过 | 本地 Claude Code CLI；context / skill / MCP 投影；host-owned resume state |
| `dashscope-agent` | ✅ 已完成 | 阿里云百炼，支持 agent/workflow 两种模式 |
| `langflow-agent` | ✅ 已完成 | SSE 流式，tweaks 配置支持 |
| `tbox-agent` | ✅ 已完成 | 蚂蚁百宝箱，多模态输入 |

**注意**: LangBot 内置 runner（`pkg/provider/runners/`）已停用，文件顶部添加了 DEPRECATED 注释。

### 本地验收

| 日期 | 范围 | 状态 | 证据 |
|------|------|------|------|
| 2026-05-29 | `local-agent` Pipeline Debug Chat | ✅ PASS | `langbot-skills/reports/2026-05-29-17-59-00-462-08-00-pipeline-debug-chat.md` |
| 2026-05-29 | `claude-code-agent` Pipeline Debug Chat | ✅ PASS | `langbot-skills/reports/2026-05-29-18-03-31-169-08-00-pipeline-debug-chat.md` |
| 2026-05-29 | Claude Code context / skill / MCP projection | ✅ PASS | `langbot-skills/reports/claude-code-agent-resource-context-20260529.md` |
| 2026-05-29 | Claude Code resume state | ✅ PASS | `langbot-skills/reports/claude-code-agent-real-workdir-20260529.md` |

---

## 未完成但仍属本分支收尾

以下项目属于本分支收尾工作：

- [x] Smoke / manual validation — `local-agent` 与 Claude Code MVP 已通过本地 WebUI smoke
- [ ] Docs final QA
- [ ] Claude Code runner 文档、安装和 marketplace 发布准备

---

## 非本分支范围

以下能力由其他分支负责：

| 能力 | 负责分支 | 备注 |
|------|----------|------|
| EventGateway implementation | event branch | 完整事件网关、事件路由、持久化管理 |
| Event subscription / notification | event branch | 事件订阅、推送通知 |
| BindingResolver persistence UI | 其他模块 | 绑定配置的持久化 UI |
| Event router integration | event branch | 与 BindingResolver 集成 |
| Scheduler / background event source | 其他模块 | 定时任务、后台事件源 |
| Security release hardening | 后续 release gate | 路径隔离、权限边界、secret、MCP/skill 投影策略、资源配额、审计 |
| Codex / Kimi runner 全量接入 | 后续 runner 插件工作 | 当前只验证 Claude Code MVP 形态，不扩大 scope |
| Issue-centric 产品模型 / 异步队列 / workflow engine | 后续产品架构 | 不属于当前 agent-runner plugin 协议闭环 |

---

## 待办事项

### 高优先级

- [x] 工具详情 API — SDK `GET_TOOL_DETAIL` action、`AgentRunAPIProxy.get_tool_detail()` 与 Host 侧授权校验已接通
- [x] Pipeline `run_from_query()` → `run(event, binding)` — 已完成
- [x] EventLog / Transcript / ArtifactStore / PersistentStateStore — 已完成
- [x] History / Event / Artifact / State pull APIs — 已完成
- [x] `caller_plugin_identity` 验证路径 — 已完成

### 低优先级 / 未来

- [ ] EBA 完整集成 — EventGateway、event subscription、event notification 由其他分支实现
- [ ] 平台 API 动作执行 — `action.requested` 结果类型存在但未执行
- [ ] 安全发布级 hardening — 作为生产默认启用前的 release gate，不阻塞当前协议闭环

---

## 关键决策记录

| 日期 | 决策 |
|------|------|
| 2026-05-10 | Phase 0 集成测试通过，SDK v1 协议验证成功 |
| 2026-05-13 | Phase 3 完成：所有 7 个官方 runner 插件迁移完成 |
| 2026-05-23 | Phase 3.5 完成：`run_from_query()` 委托到 event-first `run(event, binding)`，Pipeline path 获得 host capabilities |
| 2026-05-29 | 本地 `local-agent` 与 `claude-code-agent` 通过 WebUI smoke；Claude Code runner 验证 external harness context 投影和 host-owned resume state |

---

## 相关文档

- [README.md](./README.md) — 总体设计
- [PHASE1_QA_ACCEPTANCE_MATRIX.md](./PHASE1_QA_ACCEPTANCE_MATRIX.md) — Phase 1 agent QA 验收矩阵
- [PHASE1_QA_REPORT_2026-05-29.md](./PHASE1_QA_REPORT_2026-05-29.md) — 2026-05-29 本地 smoke 验收记录
- [OFFICIAL_RUNNER_PLUGINS.md](./OFFICIAL_RUNNER_PLUGINS.md) — 官方插件仓库计划
- [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) — 安全发布级 hardening 后续门槛
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) — 具体实施细节
