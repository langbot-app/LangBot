# Agent Runner 插件化实现进度

本文档跟踪 Agent Runner 插件化的实现状态，便于快速了解当前进度。

## 总体进度

**当前阶段**: Phase 3 已完成，Phase 4 预留/部分上下文字段已填充

| Phase | 描述 | 状态 |
|-------|------|------|
| Phase 0 | PoC 验证 | ✅ 完成 |
| Phase 1 | 核心架构（Registry、Orchestrator、上下文模型） | ✅ 完成 |
| Phase 2 | 权限、能力声明、资源注入 | ✅ 完成 |
| Phase 3 | 内置 runner 迁移到插件 | ✅ 完成（7/7） |
| Phase 4 | EBA 事件支持 | 🔲 未开始（message event/actor/subject 上下文已预填充） |

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

### LangBot 侧

| 组件 | 状态 | 备注 |
|------|------|------|
| `AgentRunnerRegistry` | ✅ | `pkg/agent/runner/registry.py` |
| `AgentRunOrchestrator` | ✅ | `pkg/agent/runner/orchestrator.py` |
| `AgentRunnerDescriptor` | ✅ | `pkg/agent/runner/descriptor.py` |
| `AgentResourceBuilder` | ✅ | `pkg/agent/runner/resource_builder.py` |
| `AgentRunContextBuilder` | ✅ | `pkg/agent/runner/context_builder.py` |
| `AgentResultNormalizer` | ✅ | `pkg/agent/runner/result_normalizer.py` |
| `ConfigMigration` | ✅ | `pkg/agent/runner/config_migration.py` |
| `ChatMessageHandler` 集成 | ✅ | 使用 orchestrator 替代 wrapper |
| `PipelineService` 集成 | ✅ | 从 registry 获取 runner metadata |
| Plugin connector | ✅ | `list_agent_runners()` / `run_agent()` |

### 官方插件

> 外部服务插件仓库：`/home/glwuy/langbot-app/langbot-agent-runner/`  
> 本地 Local Agent 插件仓库：`/home/glwuy/langbot-app/langbot-local-agent/`

| 插件 | 状态 | 备注 |
|------|------|------|
| `local-agent` | ✅ 已完成 | 核心功能：模型、工具、知识库、流式、会话 |
| `dify-agent` | ✅ 已完成 | 支持 chat/agent/workflow 三种应用类型 |
| `n8n-agent` | ✅ 已完成 | Webhook 调用，支持 basic/jwt/header 认证 |
| `coze-agent` | ✅ 已完成 | 多模态输入，思维链处理 |
| `dashscope-agent` | ✅ 已完成 | 阿里云百炼，支持 agent/workflow 两种模式 |
| `langflow-agent` | ✅ 已完成 | SSE 流式，tweaks 配置支持 |
| `tbox-agent` | ✅ 已完成 | 蚂蚁百宝箱，多模态输入 |

**注意**: LangBot 内置的旧 runner（`pkg/provider/runners/`）已标记为 legacy，文件顶部添加了 DEPRECATED 注释。

---

## 待办事项

### 高优先级

- [x] 工具详情 API — SDK `GET_TOOL_DETAIL` action、`AgentRunAPIProxy.get_tool_detail()` 与 Host 侧授权校验已接通

### 低优先级 / 未来

- [ ] EBA 完整集成 — message event/actor/subject 上下文已填充，完整事件路由与非消息事件仍待实现
- [ ] 平台 API 动作执行 — `action.requested` 结果类型存在但未执行

---

## 关键决策记录

| 日期 | 决策 |
|------|------|
| 2026-05-10 | Phase 0 集成测试通过，SDK v1 协议验证成功 |
| 2026-05-13 | Phase 3 完成：所有 7 个官方 runner 插件迁移完成 |

---

## 相关文档

- [README.md](./README.md) — 总体设计
- [OFFICIAL_RUNNER_PLUGINS.md](./OFFICIAL_RUNNER_PLUGINS.md) — 官方插件仓库计划
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) — 具体实施细节
