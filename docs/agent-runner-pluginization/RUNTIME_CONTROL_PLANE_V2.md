# Agent Runtime Control Plane V2

本文档记录后续 Agent Platform / runtime 管控面的设计方向。它是当前讨论中的 **v2 文档**，但这里的 v2 指 Host capability layer / runtime control plane，不是 `AgentRunner Protocol v2`，也不属于当前 AgentRunner Protocol v1 插件化主线的交付范围。

## 1. 结论

当前主线应继续收口 AgentRunner v1：

```text
message/event -> binding -> runner.run(ctx) -> result stream
```

Runtime Control Plane v2 在 Host 侧新增 runtime control plane：

```text
event -> task -> runtime selection -> daemon claim -> execute -> progress/audit/result
```

在 Runtime Control Plane v2 之上，可以构建独立的 agent 管控面插件。插件负责 UI、策略和编排体验；runtime、task、heartbeat、audit 的事实源必须属于 LangBot Host，而不是插件私有 storage。

## 2. 不影响 v1 主线

v2 不应改变 AgentRunner v1 的基本契约：

- 现有 `local-agent`、Dify、n8n、Coze 等 runner 仍可按 v1 直接执行。
- 当前 Claude Code / Codex MVP runner 可以继续作为本机 subprocess 开发路径。
- Host v1 已有的 event-first context、resource authorization、history / event / artifact / state / storage pull APIs 继续保留。
- Pipeline 仍只是当前入口 adapter，不参与 v2 runtime 管控面的设计中心。

v2 只是在 Host 上新增一层可选能力。需要管控面的 runner 或管理插件可以声明使用它；不需要的 runner 不受影响。

## 3. 当前 Host 能力与缺口

当前 Host 已经具备 v2 的基础设施底座：

- `AgentEventEnvelope` / `AgentBinding`
- run-scoped resource authorization
- EventLog / Transcript / ArtifactStore / PersistentStateStore
- History / Event / Artifact / State / Storage pull APIs
- AgentRunner result stream 和受控错误回流
- binding config 与 host-owned state

这些能力足够支持一次 `runner.run(ctx)` 内的安全执行，但不足以承担完整 runtime 管控面。

v2 还需要 Host 新增：

- runtime registry：runtime id、所属 workspace、所在机器、provider 能力、状态。
- capability discovery：`claude` / `codex` / 其它 CLI 是否存在、版本、登录状态、执行隔离能力。
- heartbeat / liveness：runtime 在线、忙闲、最后心跳、可用 slot。
- task queue：enqueue、claim、start、progress、complete、fail、cancel。
- workspace mapping：LangBot workspace / project 如何映射到 runtime 上的真实目录、仓库或挂载。
- secret / env projection：按授权向 runtime 投影 token、代理、MCP 配置、技能和环境变量。
- runtime audit：stdout、stderr、事件流、产物、失败原因、执行耗时、使用量。
- control API / UI：选择 runtime、测试 runtime、查看状态、下线、取消任务、重试任务。

## 4. 角色边界

### 4.1 LangBot Host

Host 是事实源和控制面内核：

- 保存 runtime / task / heartbeat / audit 状态。
- 做权限校验、资源裁剪、workspace 绑定和审计。
- 决定任务是否可被某 runtime claim。
- 将执行结果统一回写到 event / transcript / artifact / state。

Host 不应内置具体 agent CLI 的复杂业务逻辑，也不应把某个官方 runner 的特殊行为提升为通用协议。

### 4.2 Agent 管控面插件

管理插件是 v2 control plane 的产品化管理层：

- 展示 runtime、agent、task、进度、失败、审计。
- 提供策略配置，例如默认 runtime、provider 偏好、并发限制、重试策略。
- 触发 runtime 测试、任务取消、任务重试、手动分配。

管理插件不应把 runtime/task 的事实源放进自己的 plugin storage。它应该调用 Host v2 API。

### 4.3 Runtime daemon / worker

Runtime daemon 负责真实执行：

- 在所在机器上检测 CLI 和版本。
- 管理工作目录、仓库、挂载、临时文件和进程。
- 从 Host claim 任务，执行后上报 progress / complete / fail。
- 将 stdout / stderr / artifacts / session id 回流 Host。

Claude Code、Codex、OpenCode、Gemini CLI 等 provider 适配逻辑应主要落在 daemon / worker 或 provider adapter 中。

## 5. 部署形态

### 5.1 uv / local embedded

用户用 `uv` 或源码直接启动 LangBot 时，LangBot 进程所在机器就是 runtime host。

这种模式下可以直接检测用户主机上的 `claude`、`codex` 等 CLI，也可以直接 subprocess 执行。它适合个人开发和本地 smoke，但不应作为团队级管控面的唯一形态。

### 5.2 Docker embedded

用户用 Docker 启动 LangBot 时，runtime host 是容器，不是宿主机。

因此：

- 只能检测容器内的 `claude`、`codex`。
- 只能使用容器内的 HOME、PATH、凭据和挂载目录。
- 如果镜像未安装 CLI，或未挂载认证文件 / workspace，CLI runner 会不可用。

Docker embedded 可以作为高级部署选项，但需要用户显式安装 CLI、挂载工作区和凭据。Host 不应假设 Docker 容器能自动访问宿主机 CLI。

### 5.3 Sidecar daemon

推荐的 v2 形态是 sidecar daemon：

```text
LangBot Host (Docker or server)
  <-> Runtime daemon on user host / worker host
        -> claude / codex / other CLI
```

这种模式下，LangBot 可以跑在 Docker 内，runtime daemon 跑在宿主机或独立 worker 机器上。daemon 负责检测本机 CLI、持有本机凭据和工作区访问能力。

### 5.4 Remote runtime

团队场景可以使用远端 runtime：

- 开发机、构建机、云主机或专用 worker。
- 多个 workspace 可绑定不同 runtime。
- Host 只通过 registry / task queue / heartbeat / audit 进行管理。

### 5.5 API-only agent

Dify、n8n、Coze、DashScope 等 API 型 runner 不依赖本地 CLI。它们可以继续按 v1 直接执行，也可以在未来按需要接入 v2 task/audit。

## 6. 与 Claude Code / Codex MVP runner 的关系

当前 Claude Code / Codex runner 是 v1 runner：

```text
runner.run(ctx) -> subprocess("claude" / "codex")
```

它们适合验证 Host context 投影、state resume、result stream 和基础 CLI 调用，但有明确限制：

- 命令只在 LangBot runtime host 上执行。
- Docker 环境只能看到容器内 CLI。
- 没有 runtime registry、heartbeat、task queue、cancel、workspace lifecycle。
- 不提供发布级执行隔离、secret projection、团队级 audit。

v2 不需要删除这些 runner。它们可以继续作为 dev / MVP 路径存在。未来若接入管控面，可以增加 runtime-managed 执行模式：

```text
runner binding -> Host task -> runtime daemon -> provider CLI -> Host result
```

## 7. 最小 v2 API 草案

以下仅记录能力边界，不代表最终 API 命名。

Runtime：

- `runtime.register`
- `runtime.heartbeat`
- `runtime.list`
- `runtime.get`
- `runtime.disable`
- `runtime.capabilities.report`
- `runtime.capabilities.probe`

Task：

- `task.enqueue`
- `task.claim`
- `task.start`
- `task.progress`
- `task.complete`
- `task.fail`
- `task.cancel`
- `task.retry`

Workspace：

- `runtime.workspace.bind`
- `runtime.workspace.unbind`
- `runtime.workspace.resolve`

Audit / artifacts：

- `task.log.append`
- `task.artifact.create`
- `task.events.page`

这些 API 应由 Host 提供，并受 workspace、runtime、binding、actor 和 plugin identity 约束。

## 8. 管控面插件可以构建的能力

基于 v2 Host 能力，可以实现一个类似 Multica 的 agent 管控面插件：

- runtime 列表、在线状态、CLI 能力、版本、认证状态。
- agent profile 与 runtime/provider 绑定。
- 任务看板、任务详情、进度流、失败原因、重试和取消。
- workspace 到 runtime 目录 / 仓库的映射管理。
- provider capability 测试，例如 Claude Code / Codex 是否可执行。
- 审计视图：输入、输出、工具、artifact、stdout/stderr、session id。
- 策略配置：并发、队列、默认 runtime、fallback runtime、权限模式。

该插件应该是 Host v2 的消费者，而不是 Host v2 的替代品。

## 9. 设计原则

- v1 先稳定，v2 可选叠加。
- Host 保存事实源，插件提供管理体验。
- Runtime daemon 执行具体 CLI 和本机资源访问。
- Docker 不假设拥有宿主机 CLI；需要 sidecar 或显式挂载。
- Pipeline 不进入 v2 控制面中心。
- 直接 subprocess runner 可保留，但只作为 local/dev/MVP 路径。
- 发布级能力必须经过 Host 权限、审计和资源边界。

## 10. 待定问题

- runtime daemon 与 Host 的认证模型：workspace token、device token、还是 scoped PAT。
- task 与 AgentRunner binding 的映射关系：由 binding 直接 enqueue，还是由独立 task policy 决定。
- runtime capability schema 的稳定字段：provider、version、login status、execution isolation、workspace access、slot。
- secret projection 的边界：Host 存储、用户本机存储、或外部 secret manager。
- Docker compose 是否提供官方 sidecar daemon 示例。
- v2 UI 是核心前端的一部分，还是完全由管理插件提供。
