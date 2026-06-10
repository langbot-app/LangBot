# Agent Runner Security Hardening

本文档记录 agent-runner 插件化进入生产发布前需要补齐的安全与稳定加固项。

## 状态

**当前结论：暂不塞进本阶段 agent-runner plugin 协议闭环。**

本阶段目标是验证 LangBot 可以通过统一的 `run(event, binding)` 协议接入 `local-agent` 与外部 harness runner（如 Claude Code runner），并能传递事件、上下文、资源句柄、状态和结果流。

安全发布级 hardening 是后续 release gate，不应阻塞当前协议闭环，但必须作为进入生产默认启用前的验收条件。

> **硬规则**：能执行代码 / 访问工作目录的外部 harness runner（Claude Code、Codex、Kimi Code 等）不得在生产环境默认启用或隐式开启。self-host stdio / 容器内部署可以作为管理员显式 opt-in，并在配置或 UI 中标明 operator-owned execution risk；只有生产默认启用、托管云 runner 或 LangBot 承诺提供受管执行环境时，才要求完成本文 full Release Gate。

## Multica 对比结论

对照 Multica 当前 daemon / runtime 模型，可以采用类似边界：

- Multica 的 agent 不运行在 Multica server 上，而是由用户机器上的 daemon 调用本机已安装的 AI coding tool；runtime 不是 server，也不是 container。
- 标准任务由 daemon 在 workspace root 下创建 per-task environment；但 `local_directory` 场景会直接在用户指定目录原地操作，只做绝对路径、路径清理、系统根目录 / home 黑名单、symlink realpath、读写能力和同路径串行锁校验。
- 子进程通过 `exec.CommandContext`、timeout、cwd 和 env 运行；custom args 只过滤 protocol-critical flags，custom env 只阻止覆盖 daemon 内部变量和关键路径变量。它没有尝试阻止外部 CLI 读取该 OS 用户本来能访问的所有宿主路径。
- MCP / secret 的约束更具体：Claude 走 `--mcp-config` + strict config；Codex 把 managed MCP 写入 per-task `$CODEX_HOME/config.toml`，避免 secret 出现在 argv / 日志；agent token 优先使用 task-scoped token。
- Skill 安全边界也明确留给用户和目标工具：第三方 skill 不由 Multica 签名、审计或沙箱化。
- provider-native sandbox 是 opportunistic guardrail，不是统一安全承诺。例如 Codex 在部分平台可写 managed sandbox config，但平台限制下也可能退回更宽松模式；Claude daemon mode 也会使用自动授权 / bypass 类能力以保证无人值守执行。

因此，LangBot 不应把“完整约束外部 harness 的宿主文件 / 进程 / CPU / 内存 / native tool 能力”作为当前协议闭环或 self-host opt-in 的前置条件。当前阶段应承认外部 harness 是 operator-owned execution，并把 LangBot 可控的最小护栏补齐。

## 启用级别

| 场景 | 当前策略 | LangBot 必须负责 | 不作为当前阶段目标 |
| --- | --- | --- | --- |
| self-host stdio 外部 harness | 管理员显式 opt-in，默认关闭。 | 风险提示、runner/binding 权限摘要、Host 资源授权、Host 生成路径约束、env / secret 过滤、MCP scoped projection、timeout / cancel / output bound、state / audit。 | 阻止该 CLI 访问同一 OS 用户本来可访问的任意宿主文件、进程或全局 CLI 配置。 |
| 容器内部署外部 harness | operator 通过容器镜像、挂载、环境变量和网络策略承担执行边界。 | 不假设 privileged container；只投影授权资源；文档提示最小挂载和最小 env；沿用 self-host 最小护栏。 | 在容器内再实现一套完整 VM / cgroup / seccomp 策略。 |
| managed/cloud/default external harness | 只有完成 full Release Gate 后才能默认启用。 | 受管 workspace、容器/VM/process isolation、CPU / memory / disk / network / output quotas、完整 lifecycle cleanup、first-class audit 和 admin control。 | 无。 |

## 责任边界

### LangBot Host 负责

- 资源授权：决定某个 `run_id` / binding 可以访问哪些模型、RAG、MCP、skill、artifact、history、state。
- 资源投影：只把授权后的资源句柄、配置片段或上下文文件传给 runner。
- 路径策略：限制 Host 生成的 workspace / context file / artifact 的允许路径和清理策略；对管理员显式指定的本地工作目录做规范化、黑名单和风险提示。
- Secret 策略：过滤环境变量、配置、日志和 transcript 中的 secret。
- 运行约束：配置超时、轮次、并发、配额、输出大小和取消路径。
- 审计记录：记录事件、绑定、资源授权、runner 调用、外部 harness session id、关键错误和结果摘要。

### Runner Plugin 负责

- 遵守 LangBot 下发的 Agent/runner config、授权资源和运行约束。
- 将 LangBot 资源投影成目标 runner 可消费的形式，例如 context 文件、MCP 配置、环境变量或 CLI 参数。
- 遵守 PROTOCOL_V1 §13 的插件实例边界；需要跨轮次保存的外部 session id / working directory 等状态应写入 host-owned state。
- 对外部进程做最小必要封装，包括命令参数构造、超时、取消、输出解析和错误映射。

### 外部 Harness 负责

Claude Code、Codex、Kimi Code 等外部 harness 可以继续使用自身的权限模型、工具 allow / deny 规则、MCP 加载策略、session/resume 机制和沙箱能力。

但外部 harness 不是 LangBot 的唯一安全边界。LangBot 仍必须在 Host 可控范围内完成资源授权、路径限制、secret 过滤和审计记录；stdio / 容器内显式启用时，外部 harness 对宿主 OS 的最终访问能力由 operator 的 CLI、账户、容器和挂载策略承担。

## 当前 MVP 可接受边界

当前阶段可以接受以下前提：

- 由可信管理员配置 runner binding，并显式启用外部 harness 风险模式。
- 工作目录和 context 输出目录为显式配置或 host 生成路径。
- 外部 runner 应尽量使用保守权限，例如 plan / no-write 模式或禁用高风险工具；当前 Claude Code MVP 仍包含高风险执行模式，只能作为 dev / smoke path。
- 通过 timeout、max turns、输出长度和进程取消降低失控风险。
- 通过 host-owned state 保存 `external.session_id`、`external.working_directory` 等 resume 所需指针。

这些前提足够做本地 E2E 与协议验收，不等同于生产发布完成。

## Admin Opt-in Minimum Guardrails

外部 harness 如果只作为 self-host stdio / 容器内部署的管理员显式 opt-in，本阶段不要求完成 full OS sandbox，但至少需要：

- 默认关闭外部 harness binding；启用时显示 runner 权限、工作目录、MCP / skill 投影和危险权限提示。
- Host 生成的 workspace / context / artifact 路径必须在 allowlist root 内；管理员显式工作目录必须做 absolute path、`realpath`、系统根目录 / home 黑名单、`..` 逃逸和 symlink 检查。
- 子进程环境使用 allowlist 或强 denylist，禁止覆盖 LangBot 内部变量、token、workspace root、runner state root、`PATH` / `HOME` 等关键变量；日志、错误、transcript 和 artifact metadata 必须 redaction。
- MCP 配置必须是 scoped projection；secret 不应出现在 argv 或普通日志；LangBot MCP bridge 只暴露当前 run 授权的 tool surface。
- Skill 投影必须来自 Host 已授权资源；记录来源、版本 / hash 或摘要；投影目录在 run / workspace 生命周期内可清理。
- CLI 参数需要过滤 protocol-critical flags；高风险 permission mode 必须是显式配置或显式 MVP 标记，不能作为用户不可见的安全承诺。
- 子进程必须支持 timeout、cancel、进程组清理和输出上限；CPU / memory / container hard quota 仅对 managed/cloud/default external harness 强制。
- state / workspace / artifact 至少要有 owner scope、session id 记录、cleanup path 和 audit-lite 事件。
- 测试覆盖 path escape、env / secret 泄漏、MCP deny、timeout、cancel、resume、cleanup 和 audit 字段完整性。

## Release Gate Checklist

下表是进入“生产默认启用 / managed external harness / LangBot 承诺提供受管执行环境”前的 full gate。状态以 2026-06-09 当前 checkout 复核为准；“已补”只代表 self-host stdio / 容器内管理员显式 opt-in 的最小护栏，不代表 managed/default runner 已具备完整生产隔离。

| 项目 | 状态 | 当前已补 | 仍缺口 / 发布前要求 |
| --- | --- | --- | --- |
| Path isolation | Partial | 本地 Claude / Codex runner 会规范化 `working-directory`，拒绝系统根目录、用户 home 和不存在路径；context directory 必须是工作目录内相对路径，拒绝绝对路径、`..` 和 symlink 逃逸；remote daemon 对投影文件使用相对路径 + `realpath` containment，拒绝绝对路径、`..` 和 workspace 内 symlink 写出；ArtifactStore 对 file artifact 使用 `realpath` + root containment 复核。 | Host 生成 workspace / context / artifact root 还缺统一 allowlist、mount 策略、TTL cleanup 和 orphan cleanup；管理员显式 `working-directory` 仍是 operator-owned local directory，LangBot 不承诺阻止外部 CLI 访问同一 OS 用户可访问的所有路径。 |
| Permission boundary | Partial | Host 已有 binding 级 resource policy、run-scoped authorization snapshot、`ctx.context.available_apis`、proxy action `caller_plugin_identity` 校验；Claude Code `--dangerously-skip-permissions` 已改为显式配置，默认 false；Codex 默认 `sandbox=read-only`、`approval_policy=never`，并过滤用户 `mcp_servers.*` config override。 | 外部 CLI 的 native 文件 / 进程 / tool 能力仍属于 operator-owned execution；当前 Protocol v1 不实现 runner manifest permissions，生产默认或 managed runner 需要容器/VM/OS 级隔离、tool allow/deny 和可审计审批，不能把 runner manifest 当成外部 CLI 的完整权限边界。 |
| Secret handling | Partial | 子进程不再继承完整 LangBot / daemon 环境，只保留 CLI auth、proxy、locale、CA 等 allowlisted env；Codex `environment-json` 禁止覆盖 `HOME`、`PATH`、`CODEX_HOME`、`PYTHONPATH` 和 `LANGBOT_*`；Codex per-run `CODEX_HOME` 会继承 runtime 用户的 Codex auth/session 和非 MCP provider config，但剥离全局 `mcp_servers`；LangBot managed MCP 写入 per-run `CODEX_HOME/config.toml` 且 `0600`，scoped secret 不进入 argv；remote daemon MCP config / `mcp.json` 使用 `0600`；stdout/stderr、错误和 diagnostic artifact 做 redaction + 输出截断；相关单测覆盖 secret/env 泄漏。 | 仍缺 Host 全链路统一 redaction policy、transcript / artifact metadata / admin UI 脱敏规则、secret 来源与轮换策略、跨 runner 的配置脱敏审计。 |
| MCP policy | Partial | SDK-owned per-run LangBot MCP bridge 已有；remote MCP channel 有 per-run secret；bridge 只暴露 SDK annotated tool surface；Codex managed MCP 不允许用户通过 `config-overrides` 注入/覆盖 `mcp_servers.*`，也不继承 runtime 用户全局 `mcp_servers`；remote Codex MCP secret 不进 argv。 | 缺 Host / Admin 级外部 MCP server allowlist、scoped token 生命周期、tool allow / deny 策略、危险工具审批和 MCP 调用审计。 |
| Skill access policy | Partial | Host resource builder 会按 runner capability 和 resource policy 暴露 skill-backed scoped tool；当前 code-agent runner 不再接受用户手写 `skills-json`，避免 runner binding 任意投影 skill；skill tool 路径和可见性已有部分单测。 | 缺 code-agent harness 的发布级 skill 来源验证、版本 / hash 记录、projection cleanup 和审计；如后续需要 harness-native skill 文件，也必须由 Host / sandbox 生成受限 tool surface，不能绕过 SDK runtime 访问 LangBot 资源。 |
| Process isolation | Partial | Host runtime deadline、runner subprocess timeout、timeout 后 kill、remote request size limit 已有；本地 Claude / Codex 和 remote daemon 子进程使用新进程组，timeout / cancel 路径会杀进程组；stdout/stderr 有输出上限；Codex 默认使用 `sandbox=read-only`、`approval_policy=never`；Claude Code 高风险 bypass 默认关闭。 | CPU / 内存 / 文件 / 容器 hard quota、网络策略、长期 workspace GC 和平台级 cancel/audit 仍只作为 managed/cloud/default external harness 的 full gate。self-host stdio 只能做到 runner wrapper 层的 timeout / kill / output bound。 |
| State lifecycle | Partial | PersistentStateStore 有 runner / binding / scope 隔离、JSON size limit、state get / set / list / delete；外部 runner 已写回 `external.session_id`、本地 `external.working_directory`、远端 `external.runtime_id` / `external.workspace_key`，避免把远端绝对路径当成 Host resume 事实。 | 缺 session / workspace / artifact TTL、过期清理、迁移策略、orphan cleanup 和 lifecycle audit；managed/default runner 需要 Host first-class workspace 生命周期。 |
| Audit first-class | Partial | EventLog、Transcript、ArtifactStore、PersistentStateStore 已能记录主链路事实；proxy 校验失败会写 warning。 | 资源授权快照、外部命令、MCP tool 决策、secret redaction、cleanup、resume / workspace 生命周期还不是一等 audit surface。 |
| UI / Admin control | Missing | 当前 Pipeline runner 配置能选择插件 runner。 | 缺管理员可见的 runner 权限摘要、风险提示、生产禁用 / 启用入口、resource binding 管理、MCP / skill / workspace 策略 UI。 |
| Test matrix | Partial | 已有 run authorization、caller identity、artifact、state、history / event pull API、local / remote path escape、remote symlink escape、env allowlist / secret 泄漏、Claude dangerous mode 显式启用、timeout、进程组 kill、MCP bridge、remote MCP 回访、Codex MCP secret 不进 argv、Codex per-run auth/config seed、skill visibility 等单测；runner 仓库 `pytest` / `ruff` 已通过；本机真实 Claude Code CLI 与 Codex CLI 的 runner 级 E2E 已通过。 | 仍缺 Host UI smoke、生产禁用入口、MCP deny / dangerous tool 审计、workspace cleanup / audit 完整性矩阵；CPU / memory / container quota 测试属于 managed/cloud/default full gate。 |

## 非当前范围

以下内容不属于本阶段协议闭环：

- 完整异步队列与 issue-centric 产品模型。
- 复杂 workflow engine。
- Codex / Kimi runner 全量接入。
- EBA 分支的完整迁移由外部 EBA 分支联调；本阶段只复用其需要的 AgentRunner Host 底座。
- 发布级安全 hardening 的完整实现。
