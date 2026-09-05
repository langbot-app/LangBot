# AgentRunner Pluginization Status

本文档是 `docs/agent-runner-pluginization/` 的状态事实源。协议 schema 仍以 [PROTOCOL_V1.md](./PROTOCOL_V1.md) 为准；测试步骤以 [AGENT_RUNNER_QA_GUIDE.md](./AGENT_RUNNER_QA_GUIDE.md) 为准；安全发布门槛以 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) 为准。

状态快照日期：2026-09-05。代码基线为 LangBot `dev/4.11.x` / `a4d36aa2d` 和 SDK `dev/4.11.x` / `f1da058`；本文是本地检视快照，不代表远端最新状态或正式发布批准。

## 当前版本与验收边界

- Core 声明版本 `4.11.0`，`pyproject.toml` / `uv.lock` 仍依赖 `langbot-plugin==0.5.3`；SDK 源码声明版本 `0.5.5`。本机 Core 实际导入旁边 SDK 的可编辑源码，不能用这个组合的测试通过证明 registry 安装可复现。
- 检视时 SDK 有四个未提交文件：`api/agent_tools/asset_gateway.py`、`api/agent_tools/external_tools.py`、`api/entities/builtin/agent_runner/resources.py`（均位于 `src/langbot_plugin/`），以及 `tests/api/test_agent_tools_mcp_bridge.py`。这些改动增加 `platform_tools` 分类发现、可选 schema 和 gateway 引导。下面的 SDK 测试包含这些工作区改动；正式配套版本尚需冻结。
- 本轮仅重新执行下列定向测试与 TypeScript 检查，没有重跑全量 backend、真实平台、provider、浏览器 E2E 或 Cloud 部署门禁。后文旧日期的成功记录仍是历史证据。

| 2026-09-05 验证 | 结果 |
| --- | --- |
| Core：`tests/unit_tests/agent`、`tests/unit_tests/api/service/test_agent_service.py`、`tests/unit_tests/platform/test_routing_rules.py`、`tests/unit_tests/api/service/test_maintenance_service.py` | 561 passed，74 warnings |
| SDK：`tests/api/entities/builtin/agent_runner`、`tests/api/proxies`、`tests/api/test_agent_tools_mcp_bridge.py`、`tests/runtime/plugin/test_mgr_agent_runner.py`、`tests/runtime/plugin/test_dependency_environment.py`、`tests/runtime/plugin/test_restart_coordinator.py` | 362 passed，10 warnings |
| Web：`pnpm exec tsc --noEmit` | pass |
| Web：`pnpm test:unit` | 62 passed，2 failed |

前端失败为源码形状断言：`oss-cloud-ui-privacy.test.mjs` 仍要求 fieldset 的精确旧 class；`processor-detail-workbench.test.mjs` 仍要求 Agent 的旧四分区。当前表单已增加布局 class，并使用运行器、运行器配置、事件与工具分区。发布前需按当前设计更新断言或修正实现，不能记为全绿。

## 近期已集成内容

- **EBA 与独立 Agent**：Bot 事件绑定、observer 广播、Pipeline / Agent / discard 单目标分派、Agent CRUD、处理器工作台与路由诊断已在同一分支。逻辑路由器实现在 `pkg/platform/botmgr.py::RuntimeBot`，不是外部独立 EventRouter 服务。
- **事件感知工具权限**：Core 9 月 4 日提交已实现 `event_*` 自动事件工具、`allowed_platform_tools` 和 `allowed_tools`。Host 冻结事件目标，结合 Runner 权限、适配器能力和运行快照授权，执行时再次检查。详见 [PLATFORM_ACTION_TOOLS.md](./PLATFORM_ACTION_TOOLS.md)。SDK 分类发现的提交状态见上文。
- **产品流程**：Runner 市场内联安装、安装恢复和健康状态、事件范围选择、统一详情工作台、Agent 调试及 Bot 平台事件调试已实装。Agent 自身已无 enabled 开关；Bot 路由仍有 enabled。具体页面形态见 [处理器页面](../event-based-agents/08-agent-page-and-event-orchestration.md)。
- **Runtime 与存储**：SDK 已加入 artifact 对应的独立依赖环境、Windows worker 连接路径、安装期间响应性测试；Core/Plugin Runtime/Box 分别报告拥有的存储目录。存储分析是观测，不提供硬配额。
- **工作空间**：OSS 单工作空间多人协作和资源作用域已合入。Cloud 隔离基础与生产激活分开验收，见 [Cloud 剩余事项](../multi-tenant/cloud-v2-pending-verification.md)。

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
| Skill 链路 | Unit-pass; WebUI E2E pass | 已按 **skill 全 tool 化** 收敛：发现走 `list_skills` / `langbot_list_assets` 和 skill resources；`activate` / `register_skill` 走统一 tool 授权；`skill_authoring` capability 降级为便捷开关。`activate` 会 best-effort 写入 conversation-scope `host.activated_skills`，后续 run 通过当前 pipeline-visible skill cache 恢复。新注册 Skill 在当前 Query 内立即获得临时可见性；Docker `exec` 产生的宿主侧不可写文件由 `write` / `edit` 回退到 Box 执行。2026-07-15 真实 LocalAgent Debug Chat 已完成创建、注册、同 Query 激活、编辑和执行闭环；非流式 runner turn 只向下游 Pipeline 产出一次，工具中间结果不再拆成额外 Bot 气泡。 |
| Runtime Control Plane v2 foundation | Partial | Host-owned `AgentRun` / `AgentRunEvent` ledger、orchestrator 自动建账、result event persistence、run get/list/event page/cancel/append/finalize actions 已落地；`agent_run:admin` / `runtime:admin` 控制权限、最小 runtime register/heartbeat/list/reconcile 和 run claim/renew/release 原语已落地。完整 Agent Platform 产品形态、daemon supervisor、任务唤醒/长轮询/WebSocket、分布式 runtime 管控仍未完成。 |
| Security boundary | Done | 当前口径降级为轻量边界：LangBot 保护自身持有资源；external harness 的 OS / process / network / workspace 风险由用户或部署环境承担；managed sandbox 不是当前承诺。 |
| Steering control path | Done | claim 异常不再逃逸 consumer loop；queue 有上限；未 pull 的 claimed 输入在 run 结束时写 `steering.dropped` 审计终态。 |
| SDK v1 contract closure | Done | SDK 提供 `AgentAPIError` / `AgentAPIException`、typed `SteeringPullResult`、未知 result type 宽容解析、result `sequence` 注入与取消传播。 |
| EBA processor routing | Done; release gate 5/5 pass | Bot `event_bindings`、Pipeline / Agent 平级路由、WebUI dry-run / 合成测试 / 状态、OneBot 非消息事件到 Agent 及平台回复已闭环；隔离空白实例已验证从 Space 安装并注册 LocalAgent。 |
| Structured interactions | Cross-repo unit-pass; provider E2E pending | Host 已完成 `interaction.requested` 白名单、持久化 callback correlation、TTL/作用域/幂等校验和 Pipeline/Agent 原处理器恢复；六个平台已接入按钮/单选投递，Lark 和 DingTalk 进一步支持原生单字段 `text` / `textarea` / `number` / `select` 控件。SDK typed contract、通用 Runner 脚手架和 DifyAgent `workflow_paused` plugin-storage continuation 已落入对应仓库。 |

## Spec 与实现已知差距

- `action.requested` 是严格白名单协议面：当前只执行 `interaction.requested`；其它 action 仍只记录 telemetry。平台语义动作通过已授权的 `event_*` / `platform_*` 工具执行，不通过任意 result action 或原始 `call_platform_api`。
- 结构化交互 SDK typed contract 与 DifyAgent continuation 已实现；SDK 正式发布、真实 Dify 凭据 E2E，以及需要长驻双向进程的 Claude Code 权限确认仍是后续验收项。Host 不持有 provider 私有 token。
- State 与 storage 的长期类型边界仍可继续收窄；当前合同只要求 JSON-safe state 与受控 storage API。
- `ToolResource.parameters` 已作为 best-effort full schema 由 Host 在构造 `ctx.resources` 时一次塞齐；无 schema 时 runner 仍需兼容 `parameters=None` 或按需调用 detail API。
- EventLog / Transcript 已提供显式 cleanup primitive；长期 retention 默认值、TTL 调度接入和 sandbox/workspace 文件清理仍是运维收尾项，应在 Runtime Control Plane 产品化前补齐。
- External harness 的 native shell / filesystem / CLI / MCP 权限不受 manifest permissions 约束；manifest permissions 只约束 LangBot 持有的资源访问。
- LangBot 当前不承诺 managed sandbox；external harness 的 OS/process/network quota、workspace GC、provider-native tool 权限由用户或部署环境承担。
- Runtime Control Plane v2 已有 Host 事实源和控制原语，独立 Agent 与处理器 UI 也已存在；仍缺业务任务队列、外部 harness daemon 托管、wakeup channel、跨 Host 分布式锁及 provider 登录态诊断。SDK installation worker 的 supervisor/重启协调已实现，不能与外部 harness 管控混淆。

## Runner 历史验收记录（未在本轮重跑）

| Runner | 状态 | 最近证据 |
| --- | --- | --- |
| `plugin:langbot-team/LocalAgent/default` | Unit-pass; Marketplace UI pass; Debug Chat E2E pass | 2026-07-12 隔离 first-run 实例从真实 AgentRunner catalog 安装 `langbot-team/LocalAgent` 0.1.0，Host 注册 `plugin:langbot-team/LocalAgent/default`，Wizard 自动选中并解锁后续操作。2026-07-15 `2026-07-15-08-44-10-770-08-00-sandbox-skill-authoring-edit-existing-e2e` 使用真实 `gpt-5.5` 完成 Skill 创建、注册、同 Query 激活、已激活包编辑与脚本执行；三阶段 UI、浏览器诊断和结构化文件系统检查全部通过，每阶段恰好新增一个 Bot 气泡，p95 14.6 秒、错误率 0。 |
| `plugin:langbot-team/ACPAgentRunner/default` | Unit-pass; Debug Chat E2E pass | 2026-07-15 从本地 0.1.4 发布包安装并注册 PascalCase runner，remote-ssh Claude ACP 通过反向隧道调用 run-scoped `langbot_get_current_event`，97.8 秒返回可见结果；Host 将增量 delta 和 `message.completed` 聚合为一个完整 Bot 气泡。 |
| `plugin:langbot-team/ClaudeCodeAgent/default` / `plugin:langbot-team/CodexAgent/default` | Unit-pass; E2E pending | 通过 runner 仓库单测覆盖 session、run_id 注入和 LangBot MCP gateway；真实 harness E2E 取决于对应运行环境、CLI/daemon 可用性和 provider 登录态。 |
| Dify | Human-input unit-pass; credential E2E pending | `langbot-agent-runner/dify-agent` 已实现 `workflow_paused`、原子字段/确认交互、plugin-storage continuation、Dify submit/events 恢复与再次暂停；真实 Dify 凭据 E2E 待执行。 |
| n8n / Coze / DashScope / Langflow / Tbox / DeerFlow / WeKnora | Unit-pass; credential smoke optional | 2026-06-13 plugin layout / parser tests 通过；真实服务凭据 smoke 非每轮必跑。 |

## Host / SDK 历史验收记录

| 范围 | 状态 | 最近证据 |
| --- | --- | --- |
| LangBot Runtime Control Plane v2 foundation | Unit-pass; EBA release gate 5/5 pass; AgentRunner preflight pass | 2026-07-12 `eba-functional-20260712-release-gate-rerun` 通过 Quick Start 场景筛选、隔离实例 Runner Marketplace 安装、Runner 健康状态、事件路由 dry-run / 合成派发，以及真实 OneBot `group.member_joined` → Agent → `send_group_msg` 链路。2026-07-15 AgentRunner release preflight 16 项通过、0 warning；fixture contract、5 类 behavior matrix、ledger schema / async DB readiness / 100-run stress / 120-run 8-worker contention / claim-lease-auth concurrency、SDK runtime chaos 探针全部通过。 |
| Host Skill / native tool integration | Unit-pass; WebUI E2E pass | 2026-07-15 provider / native / Skill / monitoring 定向测试 67 项通过，Pipeline / Chat / Wrapper 定向测试 61 项通过，Skills CLI 105 项通过；真实 Debug Chat 验证 `register_skill` 后同 Query `activate` 成功，监控工具调用不再把 SQL 行误取为字符串，结构化 JSON 文件检查不依赖格式空格，非流式多阶段 runner 结果只生成一个最终 Bot 气泡。 |
| SDK AgentRunner control entities / proxy | Unit-pass | 2026-06-23 SDK `tests/api/entities/builtin/agent_runner`、`tests/api/proxies`、`tests/api/test_agent_tools_mcp_bridge.py`、`tests/runtime/plugin/test_mgr_agent_runner.py`、`tests/runtime/test_pull_api_handlers.py`、`tests/runtime/io/handlers/test_plugin_handler.py`、EBA event entities 和 message tests 通过，覆盖 typed entities、AgentRunAPIProxy、MCP bridge、runtime manager 与 pull API handlers。 |

## 历史高价值记录

历史报告已合并为本状态页和 QA 指南，不再保留单独进度文档。后续若需要追溯，优先查看 `langbot-skills/reports/` 下的原始执行报告。

截至 2026-05-29，已有本地 smoke 证明：

- `local-agent` 可以通过 Pipeline Debug Chat 走插件化 `AgentRunOrchestrator` 主链路。
- 外部 harness runner 可以通过同一条 `run(event, binding)` 路径执行；当前官方实现已收敛到 ACP / Claude Code / Codex 等直接 runner 插件。

这些记录只证明本地协议闭环可用，不代表 LangBot 提供 managed sandbox 或 external harness OS 级隔离。
