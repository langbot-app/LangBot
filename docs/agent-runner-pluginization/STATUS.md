# AgentRunner Pluginization Status

本文档是 `docs/agent-runner-pluginization/` 的状态事实源。协议 schema 仍以 [PROTOCOL_V1.md](./PROTOCOL_V1.md) 为准；测试步骤以 [AGENT_RUNNER_QA_GUIDE.md](./AGENT_RUNNER_QA_GUIDE.md) 为准；安全发布门槛以 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) 为准。

状态快照日期：2026-06-12。

## 实现状态

| 领域 | 状态 | 说明 |
| --- | --- | --- |
| SDK manifest schema | Done | `AgentRunnerManifest` 包含 typed `capabilities` / `permissions`；未知 capability / permission key 禁止进入 typed model。 |
| Runner discovery | Done | Runtime 返回 typed manifest；Host registry 校验单个 runner，失败 warning + skip，不影响其它 runner。 |
| Host resource authorization | Done | `ctx.resources` 和 `ctx.context.available_apis` 由 manifest permissions 与 binding policy / run scope 求交后生成。 |
| Run authorization snapshot | Done | active run session 冻结 run-scoped resources 与 available APIs；runtime handler 按 snapshot 校验 pull API。 |
| Result payload validation | Done | Wire 保持 `{type, data}`；Host 对投递/副作用类 payload 严格校验，tool-call telemetry 宽松，未知 type 忽略并 warning。 |
| Old built-in runners | Done | 旧 `src/langbot/pkg/provider/runners/*` 与 `RequestRunner` 路径已从本分支删除。 |
| Official runner manifests | Done | `local-agent`、LiteLLM Agent Platform、外部服务 runner 已重新声明真实生效的 LangBot resource permissions。 |
| Runtime Control Plane v2 | Future | 第一阶段设计为 Host-owned Run Ledger；runtime registry / heartbeat / daemon claim 是后续可选阶段。 |
| Full release security gate | Future | self-host / container opt-in 可继续；managed/default external harness 需完成 SECURITY_HARDENING full gate。 |
| Steering control path | Done | claim 异常不再逃逸 consumer loop；queue 有上限；未 pull 的 claimed 输入在 run 结束时写 `steering.dropped` 审计终态。 |
| SDK v1 contract closure | Done | SDK 提供 `AgentAPIError` / `AgentAPIException`、typed `SteeringPullResult`、未知 result type 宽容解析、result `sequence` 注入与取消传播。 |

## Spec 与实现已知差距

- `action.requested` 仍只作为 telemetry / reserved surface；platform action executor 不在本分支执行。
- EventGateway / EventRouter 完整实现由外部 EBA 分支联调；本分支只提供 event-first host envelope / binding / run 入口。
- State 与 storage 的长期类型边界仍可继续收窄；当前合同只要求 JSON-safe state 与受控 storage API。
- Artifact 读取路径已检查 `expires_at`，EventLog / Transcript / Artifact 已提供显式 cleanup primitive；长期 retention 默认值、TTL 调度接入和大 payload 去重仍是运维收尾项，应在 Runtime Control Plane Phase 1 前补齐。
- External harness 的 native shell / filesystem / CLI / MCP 权限不受 manifest permissions 约束；manifest permissions 只约束 LangBot 持有的资源访问。
- Managed/cloud/default external harness 的 OS/process/network quota、workspace GC、完整 audit/admin control 仍是发布门槛，不是 Protocol v1 已完成能力。

## Runner 验收状态

| Runner | 状态 | 最近证据 |
| --- | --- | --- |
| `plugin:langbot/local-agent/default` | Unit-pass; UI smoke pending | 2026-06-10 本地 pytest / ruff 通过；WebUI smoke 由人工统一执行。 |
| `plugin:langbot/litellm-agent-platform-agent/default` | Unit-pass; E2E pending | 通过 runner 仓库单测覆盖 HTTP session、run_id prompt 注入和 LangBot MCP gateway；真实 harness E2E 取决于 LiteLLM Agent Platform 部署和 provider 登录态。 |
| Dify / n8n / Coze / DashScope / Langflow / Tbox | Unit-pass; credential smoke optional | 2026-06-10 plugin layout / parser tests 通过；真实服务凭据 smoke 非每轮必跑。 |

## 历史高价值记录

历史报告已合并为本状态页和 QA 指南，不再保留单独进度文档。后续若需要追溯，优先查看 `langbot-skills/reports/` 下的原始执行报告。

截至 2026-05-29，已有本地 smoke 证明：

- `local-agent` 可以通过 Pipeline Debug Chat 走插件化 `AgentRunOrchestrator` 主链路。
- 外部 harness runner 可以通过同一条 `run(event, binding)` 路径执行；当前官方实现已收敛到 LiteLLM Agent Platform runner，具体 Claude Code / Codex CLI provider 不再由本仓库直接维护。

这些记录只证明本地协议闭环可用，不代表发布级 security hardening 已完成。
