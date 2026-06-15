# Agent Runner Security Boundary

本文档记录 agent-runner 插件化后的安全边界和最小护栏。

## 状态

**当前结论：不采用高强度监管模型。**

LangBot 的目标不是托管一个强隔离、不可信 code runner 平台。AgentRunner 插件，尤其是 ACP / Claude Code / Codex / OpenCode / Kimi Code 这类外部 harness，默认视为 **operator-owned execution**：用户或部署者显式配置并承担其文件系统、进程、网络、workspace、provider 登录态和 native tool 风险。

LangBot 需要负责的是保护 **LangBot 自己持有的资源**，包括模型、知识库、LangBot tools、history、event、artifact、state、plugin/workspace storage 等。只要这些资源访问是 run-scoped、permission-scoped、可校验、可诊断的，当前阶段即可接受。

这意味着：

- 不要求 LangBot 在应用层实现完整 OS sandbox、VM、cgroup、seccomp、CPU / memory / network quota。
- 不要求为 ACP runner 做复杂审批流；用户选择 ACP runner 即表示显式 opt-in。
- 不要求在非 Docker 进程部署里做强监管；只要文档明确风险归属即可。
- Docker / K8s 可以提供部署级隔离，但不是 LangBot agent-runner 协议发布的前置条件。
- 不能宣传 LangBot 已经提供 managed sandbox；除非未来真的提供受管执行环境。

## 责任边界

### LangBot Host 负责

- **资源授权**：根据 runner manifest permissions、binding resource policy、run scope 生成本次 run 可访问的资源快照。
- **运行期校验**：所有带 `run_id` 的 SDK / Host action 必须校验 active run session、caller plugin identity、resource id 和 operation。
- **Scoped projection**：只把授权后的资源摘要、MCP server config、context、artifact ref、state snapshot 投影给 runner。
- **LangBot artifact 路径约束**：LangBot 自己登记和读取的 file artifact 必须限制在声明 root 内，防止 path escape。
- **基础 secret 策略**：不要主动把 LangBot 持有的 API key / token / secret 投影给 runner；日志和错误里做常见 secret 字段脱敏。
- **基础运行约束**：提供 timeout、取消传播、输出大小限制或错误映射的基础能力。
- **audit-lite**：记录 event、run id、runner id、binding、资源授权摘要、关键失败、state/artifact/transcript 事实。

### Runner Plugin 负责

- 遵守 Host 下发的 `ctx.resources`、`ctx.context.available_apis`、runner config 和 state policy。
- 把 LangBot 资源投影成目标平台可消费的形式，例如 MCP config、context prompt、HTTP header、run token。
- 不绕过 SDK / Host action 直接访问 LangBot 内部资源。
- 对自己启动的外部进程做合理封装，包括参数构造、timeout、取消、输出解析和错误映射。
- 清楚记录自身 README 中的 provider 风险、部署假设和限制。

### 部署者 / 用户负责

- ACP / external harness 的 workspace 内容、文件系统访问、进程权限、网络访问、provider-native tool 权限。
- Docker / K8s 的 image、volume、secret、network policy、resource limit、namespace、service account 配置。
- 本机进程部署时的 OS 用户权限、PATH、HOME、CLI 登录态、全局配置和外部 MCP 配置。
- 是否允许 runner 对某个目录执行真实写操作。

### 外部 Harness 负责

Claude Code、Codex、OpenCode、Kimi Code、Gemini CLI 等外部工具继续使用自己的权限模型、MCP 加载策略、session/resume、sandbox 或 approval 能力。LangBot 不承诺约束这些工具对其所在容器或宿主 OS 用户本来可访问资源的能力。

## 部署场景策略

| 场景 | LangBot 策略 | 不由 LangBot 承担 |
| --- | --- | --- |
| 普通进程部署 | 文档提示 operator-owned execution；Host 只保护 LangBot 资源。 | 阻止外部 CLI 读取同一 OS 用户可访问的文件、进程、HOME、全局 CLI 配置。 |
| Docker / K8s 部署 | 继续使用相同 Host 资源边界；容器隔离由部署环境提供。 | 应用层重复实现容器/VM/cgroup/seccomp/network quota。 |
| ACP runner | 用户显式选择 runner 和 workspace；LangBot 注入 scoped MCP / run token。 | ACP CLI native tools、workspace 写入、provider 登录态和外部 MCP 行为。 |
| 外部 SaaS runner，例如 Dify | LangBot 通过 run token / gateway 限制 LangBot 资产访问。 | SaaS 平台内部 agent 执行策略、模型工具消息格式、平台侧日志。 |
| 未来 managed runner | 只有当 LangBot 明确提供受管执行环境时，才需要单独定义强隔离 SLA。 | 当前协议闭环不承诺 managed sandbox。 |

## 最小护栏

以下是当前阶段需要维持的最小要求。它们是保护 LangBot 资源边界的要求，不是完整监管外部进程的要求。

### Resource Permission Boundary

每次 run 前必须冻结授权快照：

- runner manifest permissions 是资源访问上限。
- binding resource policy / runner config 决定本次实际授权。
- runtime action 按 `run_id` + `caller_plugin_identity` + resource id + operation 校验。
- manifest permissions 只约束 LangBot 持有资源，不约束 external harness native tools。

当前实现方向是正确的：`AgentRunSessionRegistry` 保存 run-scoped snapshot，`plugin/handler.py` 对模型、工具、知识库、history、artifact、state、storage 等 action 做运行期校验。

### MCP / Asset Gateway Boundary

LangBot MCP / asset gateway 只暴露当前 run 授权的工具面：

- `langbot_list_assets`
- `langbot_get_current_event`
- `langbot_history_page`
- `langbot_retrieve_knowledge`
- `langbot_get_tool_detail`
- `langbot_call_tool`

外部平台需要使用短期 `run_token` 或 Authorization bearer token。token 缺失、错误或过期时必须拒绝访问。

不要求当前阶段实现 admin 级 MCP allowlist、dangerous tool approval 或复杂审批流。是否注册外部 MCP provider 是部署者/用户行为。

### Workspace / Path Boundary

LangBot 只需要约束自己管理的路径：

- Host 生成或登记的 file artifact 必须校验 `realpath` 和 root containment。
- Artifact metadata 不应暴露 Host-only storage key / host path。
- Context 文件、artifact 文件如由 LangBot 创建，应放在可清理的位置。

用户配置给 ACP runner 的 workspace 不属于 LangBot 的强监管范围。Docker/K8s 下依赖 volume 挂载边界；普通进程部署下依赖 OS 用户权限和用户自担风险。

### Secret Handling

这里的 secret 指 API key、provider token、run token、MCP token、platform secret、数据库密码等。

当前阶段只要求基础策略：

- LangBot 不主动把自己持有的 secret 投影给 runner，除非这是 runner config 明确需要的外部服务凭据。
- run token 是短期、run-scoped 的，不应长期保存。
- 日志、错误、transcript、artifact metadata 尽量避免打印常见 secret 字段。
- 配置 UI / API 返回时继续沿用现有 secret masking 规则。

不要求当前阶段实现完整 DLP、全链路敏感数据追踪、secret lineage 或自动轮换体系。

### Process / Runtime Bounds

LangBot 需要提供基本可控性：

- Host run deadline / runner timeout。
- runner 侧请求 timeout。
- generator close / cancel 传播。
- 输出和 artifact inline size 上限。
- 错误映射为受控 runner failure。

不要求 LangBot 为外部 harness 实现 CPU、内存、磁盘、网络、进程树强隔离。需要这些能力时由 Docker/K8s、systemd、容器平台或用户机器策略提供。

### UI / Admin Surface

前端可以展示 runner 权限摘要，但它是信息披露，不是审批系统。

权限摘要指 runner manifest 声明的 LangBot 资源权限，例如：

- `tools.detail`
- `tools.call`
- `knowledge_bases.retrieve`
- `history.page`
- `storage.plugin`

当前阶段不要求强制弹窗、管理员审批、dangerous tool approval 或生产禁用开关。可以在 runner 配置区展示简短提示：此 runner 能访问哪些 LangBot 资源，外部 harness 执行风险由用户/部署者承担。

### Audit Lite

需要记录足够排查问题的事实：

- run id、runner id、binding、event。
- 授权资源摘要。
- state update、artifact created、transcript message。
- MCP / pull API 拒绝时的 warning。
- steering queued / injected / dropped。

不要求当前阶段建立独立安全审计产品、审批记录系统或 SIEM 级事件模型。

## 降级后的检查表

| 项目 | 当前要求 | 状态判断 |
| --- | --- | --- |
| Path isolation | 只约束 LangBot 管理的 artifact/context 路径；runner workspace 归用户/部署环境。 | Minimal required |
| Permission boundary | 必须保护 LangBot 资源；不约束外部 CLI native 能力。 | Required |
| Secret handling | 基础不投影、基础 masking、run token 短期化。 | Basic required |
| MCP policy | run-scoped token + scoped tool surface；无复杂审批。 | Required |
| Skill access policy | 通过 Host 授权资源暴露；harness-native skill 文件不作为 LangBot 安全边界。 | Basic required |
| Process isolation | 由 Docker/K8s/用户机器负责。 | Out of scope |
| State lifecycle | scope 隔离、JSON size limit、基础 cleanup primitive。 | Basic required |
| Audit | 记录运行事实和拒绝原因。 | Audit-lite |
| UI / Admin control | 权限摘要可展示；不要求审批流。 | Optional |
| Test matrix | 覆盖 run auth、MCP token、permission deny、timeout、artifact path、state size。 | Focused tests |

## 当前实现快照

截至 2026-06-15，已有实现覆盖：

- SDK typed AgentRunner manifest、capabilities、permissions。
- Host resource builder 按 manifest permissions 和 binding policy 生成 `ctx.resources`。
- Active run session snapshot 和 `caller_plugin_identity` 校验。
- History / event / artifact / state / tool / knowledge runtime action 的 run-scoped 校验。
- Artifact file path `realpath` + root containment。
- Persistent state scope 隔离和 JSON size limit。
- SDK-owned MCP bridge 和 long-lived asset gateway。
- Dify / ACP runner 对 LangBot asset gateway 的接入。
- Runner timeout、Dify HTTP timeout、ACP startup / initialize / request timeout。

仍可继续优化但不阻塞当前发布的事项：

- 前端展示 runner LangBot 资源权限摘要。
- 常见 secret 字段 redaction 收敛成统一 helper。
- Artifact/context TTL cleanup 调度。
- 更完整的 MCP 调用 audit。
- 更好的文档提示：ACP runner 是 operator-owned execution。

## 非目标

以下不属于当前 agent-runner pluginization 的安全目标：

- 防止 ACP / external harness 修改其 workspace。
- 防止外部 CLI 读取同一容器或 OS 用户本来可读的文件。
- 管控 external harness 的 provider-native tools、approval、MCP、browser、shell。
- 在 LangBot 应用层实现 VM / container / cgroup / seccomp / network policy。
- 为 Docker/K8s 部署替代平台自身的 secret、volume、network、resource limit 管理。
- 实现企业级审批系统、SIEM、DLP 或安全运营面板。

## 发布口径

可以对外说明：

> AgentRunner 插件通过 run-scoped authorization 和 scoped MCP gateway 保护 LangBot 持有资源。外部 code harness 的执行环境由用户或部署平台负责隔离；LangBot 当前不提供 managed sandbox。

不能对外说明：

> LangBot 已经安全沙箱化 Claude Code / Codex / OpenCode 等外部 runner。
