# AgentRunner Pluginization Status

本文档是 `docs/agent-runner-pluginization/` 的状态事实源。协议 schema 仍以 [PROTOCOL_V1.md](./PROTOCOL_V1.md) 为准；测试步骤以 [AGENT_RUNNER_QA_GUIDE.md](./AGENT_RUNNER_QA_GUIDE.md) 为准；安全发布门槛以 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) 为准。

状态快照日期：2026-07-12。

## 实现状态

| 领域 | 状态 | 说明 |
| --- | --- | --- |
| SDK manifest schema | Done | `AgentRunnerManifest` 包含 typed `capabilities` / `permissions`；未知 capability / permission key 禁止进入 typed model。 |
| Runner discovery | Done | Runtime 返回 typed manifest；Host registry 校验单个 runner，失败 warning + skip，不影响其它 runner。 |
| Host resource authorization | Done | `ctx.resources` 和 `ctx.context.available_apis` 由 manifest permissions 与 binding policy / run scope 求交后生成。 |
| Run authorization snapshot | Done | active run session 冻结 run-scoped resources 与 available APIs；runtime handler 按 snapshot 校验 pull API。 |
| Result payload validation | Done | Wire 保持 `{type, data}`；Host 对投递/副作用类 payload 严格校验，tool-call telemetry 宽松，未知 type 忽略并 warning。 |
| Old built-in runners | Done | 旧 `src/langbot/pkg/provider/runners/*` 与 `RequestRunner` 路径已从本分支删除。 |
| Official runner manifests | Done | `local-agent`、ACP / Claude Code / Codex 外部 harness runner、外部服务 runner 已重新声明真实生效的 LangBot resource permissions。 |
| Skill 链路 | Unit-pass; WebUI smoke pending | 已按 **skill 全 tool 化** 收敛：发现走 `list_skills` / `langbot_list_assets` 和 skill resources；`activate` / `register_skill` 走统一 tool 授权；`skill_authoring` capability 降级为便捷开关。`activate` 现在会 best-effort 写入 conversation-scope `host.activated_skills`，后续 run 通过当前 pipeline-visible skill cache 恢复，语义为 last-write-wins。 |
| Runtime Control Plane v2 foundation | Partial | Host-owned `AgentRun` / `AgentRunEvent` ledger、orchestrator 自动建账、result event persistence、run get/list/event page/cancel/append/finalize actions 已落地；`agent_run:admin` / `runtime:admin` 控制权限、最小 runtime register/heartbeat/list/reconcile 和 run claim/renew/release 原语已落地。完整 Agent Platform 产品形态、daemon supervisor、任务唤醒/长轮询/WebSocket、分布式 runtime 管控仍未完成。 |
| Security boundary | Done | 当前口径降级为轻量边界：LangBot 保护自身持有资源；external harness 的 OS / process / network / workspace 风险由用户或部署环境承担；managed sandbox 不是当前承诺。 |
| Steering control path | Done | claim 异常不再逃逸 consumer loop；queue 有上限；未 pull 的 claimed 输入在 run 结束时写 `steering.dropped` 审计终态。 |
| SDK v1 contract closure | Done | SDK 提供 `AgentAPIError` / `AgentAPIException`、typed `SteeringPullResult`、未知 result type 宽容解析、result `sequence` 注入与取消传播。 |
| EBA processor routing | Done; release gate 5/5 pass | Bot `event_bindings`、Pipeline / Agent 平级路由、WebUI dry-run / 合成测试 / 状态、OneBot 非消息事件到 Agent 及平台回复已闭环；隔离空白实例已验证从 Space 安装并注册 LocalAgent。 |

## Spec 与实现已知差距

- `action.requested` 仍只作为 telemetry / reserved surface；platform action executor 不在本分支执行。
- `action.requested` 权限模型完成前，DeliveryContext 的 adapter capability 投影只用于输出决策，不提供平台动作执行权限。
- State 与 storage 的长期类型边界仍可继续收窄；当前合同只要求 JSON-safe state 与受控 storage API。
- `ToolResource.parameters` 已作为 best-effort full schema 由 Host 在构造 `ctx.resources` 时一次塞齐；无 schema 时 runner 仍需兼容 `parameters=None` 或按需调用 detail API。
- EventLog / Transcript 已提供显式 cleanup primitive；长期 retention 默认值、TTL 调度接入和 sandbox/workspace 文件清理仍是运维收尾项，应在 Runtime Control Plane 产品化前补齐。
- External harness 的 native shell / filesystem / CLI / MCP 权限不受 manifest permissions 约束；manifest permissions 只约束 LangBot 持有的资源访问。
- LangBot 当前不承诺 managed sandbox；external harness 的 OS/process/network quota、workspace GC、provider-native tool 权限由用户或部署环境承担。
- Runtime Control Plane v2 当前只落地 Host 事实源和控制原语；还没有内置 Agent Platform UI、业务队列、daemon 进程托管、runtime wakeup channel、跨 Host 分布式锁或 provider 登录态诊断。

## Runner 验收状态

| Runner | 状态 | 最近证据 |
| --- | --- | --- |
| `plugin:langbot-team/LocalAgent/default` | Unit-pass; Marketplace UI pass | 2026-07-12 隔离 first-run 实例从真实 AgentRunner catalog 安装 `langbot-team/LocalAgent` 0.1.0，Host 注册 `plugin:langbot-team/LocalAgent/default`，Wizard 自动选中并解锁后续操作。此项不替代带真实模型的 Debug Chat 能力验收。 |
| `plugin:langbot-team/ACPAgentRunner/default` / `plugin:langbot-team/ClaudeCodeAgent/default` / `plugin:langbot-team/CodexAgent/default` | Unit-pass; E2E pending | 通过 runner 仓库单测覆盖 session、run_id 注入和 LangBot MCP gateway；真实 harness E2E 取决于对应运行环境、CLI/daemon 可用性和 provider 登录态。 |
| Dify / n8n / Coze / DashScope / Langflow / Tbox / DeerFlow / WeKnora | Unit-pass; credential smoke optional | 2026-06-13 plugin layout / parser tests 通过；真实服务凭据 smoke 非每轮必跑。 |

## Host / SDK 验收状态

| 范围 | 状态 | 最近证据 |
| --- | --- | --- |
| LangBot Runtime Control Plane v2 foundation | Unit-pass; EBA release gate 5/5 pass | 2026-07-12 `eba-functional-20260712-release-gate-rerun` 通过 Quick Start 场景筛选、隔离实例 Runner Marketplace 安装、Runner 健康状态、事件路由 dry-run / 合成派发，以及真实 OneBot `group.member_joined` → Agent → `send_group_msg` 链路。 |
| SDK AgentRunner control entities / proxy | Unit-pass | 2026-06-23 SDK `tests/api/entities/builtin/agent_runner`、`tests/api/proxies`、`tests/api/test_agent_tools_mcp_bridge.py`、`tests/runtime/plugin/test_mgr_agent_runner.py`、`tests/runtime/test_pull_api_handlers.py`、`tests/runtime/io/handlers/test_plugin_handler.py`、EBA event entities 和 message tests 通过，覆盖 typed entities、AgentRunAPIProxy、MCP bridge、runtime manager 与 pull API handlers。 |

## 历史高价值记录

历史报告已合并为本状态页和 QA 指南，不再保留单独进度文档。后续若需要追溯，优先查看 `langbot-skills/reports/` 下的原始执行报告。

截至 2026-05-29，已有本地 smoke 证明：

- `local-agent` 可以通过 Pipeline Debug Chat 走插件化 `AgentRunOrchestrator` 主链路。
- 外部 harness runner 可以通过同一条 `run(event, binding)` 路径执行；当前官方实现已收敛到 ACP / Claude Code / Codex 等直接 runner 插件。

这些记录只证明本地协议闭环可用，不代表 LangBot 提供 managed sandbox 或 external harness OS 级隔离。
