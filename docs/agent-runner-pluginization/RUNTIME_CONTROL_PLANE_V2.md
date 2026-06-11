# Agent Platform / Runtime Control Plane Decision Note

本文档记录 AgentRunner 插件化之后，LangBot 如何继续演进成 Agent Platform 基础设施层。这里讨论的是 Host capability layer，不是 `AgentRunner Protocol v2`，也不是把某个具体 Agent Platform 产品写进 LangBot core。

> 本文是当前决策版。协议数据结构仍以 [PROTOCOL_V1.md](./PROTOCOL_V1.md) 为准；测试执行入口见 [AGENT_RUNNER_QA_GUIDE.md](./AGENT_RUNNER_QA_GUIDE.md)；扩展边界见 [EXTENSION_SCOPE_MATRIX.md](./EXTENSION_SCOPE_MATRIX.md)。

## 1. 当前决策

LangBot 后续定位应更像 **Agent Host / infrastructure provider / transfer layer**，而不是把某个完整 Agent Platform 产品固化进 core。

结论：

- **Agent Platform 产品形态做成插件**。插件负责 agent 管理、策略、业务队列、UI、编排、多 agent 协作和产品体验。
- **Agent Platform 所需的基础事实源做进 Host**。Host 保存 event、run、result、artifact、state、transcript、权限快照、审计和通用控制状态。
- **不在第一阶段把 runtime registry / daemon worker 管控做成 Host 必选能力**。远程 harness / daemon 可以先由 AgentRunner 插件和 SDK remote layer 自己维护连接、心跳和本地执行。
- **不把业务调度写进 Host**。Host 提供通用 run/result/control primitives，Platform 插件决定哪些事件触发哪些 agent、如何排队、如何分配、是否 fan-out。

推荐分层：

```text
LangBot Host
  Event / Agent / Binding / Run / RunEvent / Artifact / State / Transcript
  Authorization / audit / delivery / result persistence / control primitives

Agent Platform plugin
  Agent management UI / project-task model / event routing policy
  Business queue / multi-agent orchestration / runtime selection policy

AgentRunner plugin / external harness runtime
  Connects LiteLLM Agent Platform / remote agent / subprocess / HTTP API
  Executes and converts provider-native events to AgentRunResult
```

## 2. Platform 与非 Platform 的区别

当前 LangBot 已经具备 Agent Host 的核心特征：

- 抹平不同 AgentRunner。
- 从 IM / Pipeline 入口触发 runner。
- 有 event-first context 方向。
- 有 Host-owned EventLog / Transcript / Artifact / State 的一部分。
- 有 runner config 下发和 run-scoped authorization。

这还不是完整 Agent Platform。完整 Platform 至少还需要：

- 可管理的 agent 资产：agent profile、binding、resource policy、runner config、可用状态。
- 可观察的执行生命周期：run status、result stream、失败原因、artifact、审计、回放。
- 可运营的控制面：取消、重试、排队、并发、超时、恢复、诊断。
- 可产品化的调度体验：事件订阅、路由策略、任务板、多 agent 协作、项目/工作区视图。

因此，区别不只是“有没有调度”，而是是否具备：

```text
managed agent assets + observable run lifecycle + operational run control
```

Host 负责这些能力的通用事实源和安全边界；Platform 插件负责把它们组装成具体产品。

## 3. 基础概念

### 3.1 Event

Event 表示“发生了什么”：

```text
message.received
github.issue.opened
scheduler.tick
user.approved
system.webhook.received
```

EBA 负责把外部输入标准化成 event。Event 本身不是 queue，也不等同于一次 agent 执行。

### 3.2 Run

Run 表示“某个 agent / binding / runner 针对某个 event 的一次执行”。

Run 应由 Host 持久化，成为执行状态、结果、权限和审计的事实源：

```text
run_id
event_id
agent_id / binding_id
runner_id
status
created_at / started_at / finished_at
error / failure_reason
delivery target
metadata
```

当前 `AgentRunSessionRegistry` 只保存 active run 的内存态授权信息，不足以支撑 Platform 的回放、审计、取消、重试和异步执行。

### 3.3 RunEvent / RunResult

RunEvent 是一次 run 过程中产生的结果事件流，对应 `AgentRunResult`：

```text
message.delta
message.completed
tool.call.started
tool.call.completed
artifact.created
state.updated
action.requested
run.completed
run.failed
```

Host 应保存这些事件，按 `run_id + sequence` 可回放。Transcript、Artifact、State 可以由这些 result event 触发写入现有 store。

### 3.4 Queue

Queue 不是 EBA 的替代品。

EBA 负责产生 event；queue 负责处理“这个 event 对应的执行 work item 何时执行、谁来执行、如何取消/重试/恢复”。

队列可以分两层：

- **业务队列**：由 Platform 插件管理，例如项目任务、优先级、agent team、workflow、人工审批。
- **执行队列 / run queue**：可选 Host 原语，例如 queued / running / completed / failed / cancelled、claim lease、dispatch timeout、orphan recovery。

第一阶段不要求 Host 内置完整执行队列。Platform 插件可以先管理业务队列，然后调用 Host 创建 run、保存 result。

### 3.5 Runtime / Daemon

Runtime / daemon 表示执行位置或执行能力，例如某台机器上的 Claude Code / Codex CLI。

当前决策：

- Host 不在第一阶段维护完整 runtime registry。
- AgentRunner 插件可以通过 SDK remote layer 与 daemon 保持连接、心跳和执行通道。
- 外部 harness / agent 不应直接访问 LangBot Host。访问 LangBot 资源必须通过 daemon / AgentRunner plugin / SDK runtime / `AgentRunAPIProxy` / MCP bridge。
- 如果后续多个插件都需要共享 runtime 状态，再把薄的 `RuntimeLease` / registry 下沉为 Host 通用能力。

## 4. Host 应新增的最小能力

第一阶段最重要的不是 daemon registry，而是让 Host 成为 run/result 的事实源。

### 4.1 AgentRun Store

新增持久 `AgentRun`：

```text
id / run_id
event_id
agent_id
binding_id
runner_id
conversation_id / thread_id
workspace_id / bot_id
status
status_reason
created_at / started_at / finished_at / updated_at
deadline_at
cancel_requested_at
metadata_json
```

建议 status 至少包含：

```text
created
running
completed
failed
cancelled
timeout
```

如果后续加执行队列，再引入：

```text
queued
claimed
dispatching
```

### 4.2 AgentRunEvent Store

新增持久 `AgentRunEvent`：

```text
id
run_id
sequence
type
data_json
created_at
source
artifact_refs_json
metadata_json
```

约束：

- 同一 `run_id` 内 `sequence` 单调递增。
- append 必须幂等，支持远程 daemon / plugin 重试。
- 未知 result type 可保存但 Host 只对已知类型执行副作用。
- 大 payload 仍应转 artifact，不直接塞入 result event。

### 4.3 Run Control API

Host 提供通用控制原语：

```text
run.create
run.get
run.list
run.events.page
run.cancel
run.append_result
run.finalize
```

语义：

- `run.create` 创建 Host-owned run 和授权快照。
- `run.append_result` 只允许受信 SDK/runtime 路径调用，写入 `AgentRunEvent` 并触发 transcript/artifact/state/delivery 副作用。
- `run.finalize` 关闭 run，更新 terminal status。
- `run.cancel` 设置取消意图；同步 runner 通过 context/deadline 感知，远程 runner 通过插件/daemon 通道感知。

第一阶段可以只暴露给插件 runtime action，不一定先做公开 HTTP API。

### 4.4 Result Persistence In Orchestrator

当前 `AgentRunOrchestrator.run()` 已经处理：

```text
event -> binding -> context -> runner invocation -> result normalization
```

需要补齐：

- run 开始时创建 `AgentRun`。
- 每个 `AgentRunResult` 进入 `AgentRunEvent`。
- `run.completed` / 正常 generator 结束时标记 completed。
- `run.failed` / exception / timeout 标记 failed 或 timeout。
- `state.updated`、`artifact.created`、transcript 写入继续走现有 journal，但应与 `AgentRunEvent` 有可追踪关系。

### 4.5 Authorization Snapshot

异步或远程执行时，run 创建时必须固化授权快照：

- runner identity
- binding identity
- caller plugin identity
- resource policy
- allowed tools/models/files/knowledge bases/storage scopes
- state scopes
- conversation/thread/workspace scope

后续 append result、state API、artifact API、history API 都以这个 snapshot 校验，不重新扩大权限。

## 5. SDK 侧应新增的最小能力

SDK 不需要马上定义完整 daemon registry，但需要让插件和 runner 使用 Host run/result 能力。

### 5.1 Entities

新增或补齐：

```text
AgentRun
AgentRunStatus
AgentRunEvent
RunEventPage
RunCreateRequest / RunCreateResult
RunAppendResultRequest
```

这些是 Host control primitives，不替代 `AgentRunContext` / `AgentRunResult`。

### 5.2 Proxy Methods

在 SDK proxy 中提供：

```python
create_run(...)
get_run(run_id)
list_runs(...)
page_run_events(run_id, cursor=None, limit=...)
cancel_run(run_id)
append_run_result(run_id, result, sequence=None)
finalize_run(run_id, status, error=None)
```

访问边界：

- 普通 AgentRunner 在同步 `run(ctx)` 内不一定需要直接调用这些 API；Host orchestrator 可自动记录。
- Platform 插件可以创建/查询/取消 run。
- AgentRunner 插件或 daemon bridge 可以 append/finalize 自己负责的 run。
- 外部 harness 仍不能直接调用 Host；必须经 SDK runtime / proxy / bridge。

### 5.3 Plugin-Daemon Heartbeat

远程 daemon 的初始心跳可以是 SDK / AgentRunner plugin 私有能力：

```text
daemon <-> AgentRunner plugin / SDK remote layer <-> LangBot plugin runtime <-> Host
```

Host 第一阶段只需要知道：

- 相关插件是否在线。
- run 是否有 progress/result。
- run 是否超时或取消。

如果后续需要跨插件共享 daemon 可用性，再把 heartbeat/registry 下沉为 Host 能力。

## 6. Platform 插件应负责什么

Agent Platform 插件可以负责：

- 管理哪些 agent 可用。
- 维护产品层 agent profile、项目、任务板、workflow、team。
- 订阅 EBA event，决定哪些 event 触发哪些 agent。
- 维护业务 queue：优先级、重试策略、人工审批、分配规则。
- 选择 runner / runtime / daemon。
- 调用 Host run API 创建、取消、查询执行。
- 展示 run status、result stream、artifact、失败原因和审计。

Platform 插件不应负责：

- 私有保存通用 run/result 事实源。
- 绕过 Host 直接写 transcript/artifact/state。
- 让外部 harness 直接访问 LangBot DB 或 Host 内部资源。
- 把某个业务队列语义强塞进 AgentRunner Protocol v1。

## 7. 与 EBA 的关系

EBA 做好后，事件流可以进入两种路径。

直接执行路径：

```text
EventGateway
  -> EventRouter resolves AgentBinding
  -> AgentRunOrchestrator.run(event, binding)
  -> Host records AgentRun / AgentRunEvent
  -> delivery
```

Platform 插件编排路径：

```text
EventGateway
  -> Platform plugin receives/subscribes event
  -> plugin applies policy / business queue
  -> plugin creates Host run
  -> runner/plugin/daemon executes
  -> Host records result and state
  -> plugin displays / Host delivers
```

这两条路径共享 Host run/result/artifact/state 事实源。区别在于是否有 Platform 插件参与产品化调度和业务队列。

## 8. 与 AgentRunner Protocol v1 的关系

本设计不改变 v1 的 runner 可见合同：

```text
AgentRunContext -> AgentRunner.run(ctx) -> AgentRunResult stream
```

必须保持：

- `AgentRunContext` 不塞入 daemon/worker/pod 细节。
- `AgentRunResult` 仍是 runner 输出的统一事件流。
- 普通 runner 不需要知道 task queue / runtime registry。
- 远程 harness 可以自管 session、tool loop、MCP、上下文压缩，但访问 LangBot 资源必须通过 SDK proxy / bridge。
- Runtime-managed execution 是 placement / transport 选择，不是普通 runner 协议的强制概念。

## 9. 分阶段实施建议

### Phase 1: Run Ledger

目标：Host 成为执行状态和结果事实源。

范围：

- `AgentRun` 表。
- `AgentRunEvent` 表。
- Orchestrator 自动创建/更新 run。
- Journal 持久化每个 `AgentRunResult`。
- Run 查询和事件分页 API。
- SDK entities + proxy 方法。

复杂度：中等。

预计改动：

```text
Host: 12-20 个文件
SDK: 4-8 个文件
Tests: 8-15 个文件
```

### Phase 2: Platform Plugin Queue On Host Run Primitives

目标：Platform 插件管理业务 queue，Host 提供 run/result/cancel 原语。

范围：

- `run.create`
- `run.cancel`
- `run.append_result`
- `run.finalize`
- result append 的 sequence/idempotency。
- 受权限保护的远程 append/finalize。
- Platform 插件可基于 Host run 构建任务板和调度体验。

复杂度：中等偏高。

预计改动：

```text
Host: 20-35 个文件
SDK: 8-14 个文件
Tests: 15-25 个文件
```

### Phase 3: Optional Host Execution Queue / Claim Lease

目标：当多个插件重复实现 claim/cancel/retry/recovery 时，再下沉执行队列到 Host。

范围：

- `queued/running/completed/failed/cancelled` 状态机扩展。
- `claim_run` / `lease_until`。
- dispatch timeout。
- retry / orphan recovery。
- cancel propagation。
- 并发 claim 防重。

复杂度：高。

预计改动：

```text
Host: 35-55 个文件
SDK: 12-20 个文件
Tests: 25-40 个文件
```

### Phase 4: Optional Runtime Registry

目标：当 Host 需要统一管理多个 daemon / worker 时，再引入 runtime registry。

范围：

- runtime register / heartbeat / deregister。
- capability report：provider、version、login status、workspace access、slot。
- runtime online/offline。
- runtime scoped auth。
- runtime audit。
- runtime gone recovery。
- task wakeup / long polling / websocket。
- 多 Host 实例下的 relay / distributed lock。

复杂度：很高。

预计改动：

```text
Host: 55-80+ 个文件
SDK: 18-30 个文件
Tests: 40+ 个文件
```

不建议现在直接进入此阶段。

## 10. 设计原则

- 先把 run/result 事实源做进 Host，再谈完整 runtime control plane。
- Agent Platform 产品做插件；Host 做基础设施。
- Host 不写业务调度策略，但要保存通用状态、结果、权限和审计。
- EBA event 不是 queue；queue 是执行生命周期问题。
- 业务 queue 可以先在 Platform 插件里；执行 queue 只有在复用需求明确后再下沉 Host。
- Daemon registry 不应污染 AgentRunner Protocol v1。
- 外部 harness 不直接访问 LangBot Host 或 DB。
- 所有 LangBot 资源访问必须走 SDK runtime / `AgentRunAPIProxy` / scoped MCP bridge。
- Docker / remote / local subprocess 只是 runtime placement，不是 runner 协议差异。

## 11. 非目标

当前阶段不做：

- 完整 Multica 式 runtime registry。
- Host 内置项目管理、任务板、agent team、workflow 产品逻辑。
- 把 daemon heartbeat / worker liveness 放进 `AgentRunContext`。
- 把业务 queue 定义为 AgentRunner Protocol 字段。
- 让 Platform 插件私有保存 run/result 事实源。
- 让外部 agent/harness 直连 Host 内部资源。

## 12. 待定问题

- Host 是否需要最小持久 `Agent` / `Binding` 模型，还是继续由 Pipeline / Platform 插件投影运行期 `AgentBinding`。
- Platform 插件创建 run 时，是否传完整 `AgentBinding` snapshot，还是引用 Host-owned binding id。
- `AgentRunEvent` 与现有 `EventLog` / `Transcript` 的查询关系：直接 join，还是通过专门 view 聚合。
- `run.append_result` 的认证粒度：runner plugin identity、run token、scoped capability token，或 SDK runtime 内部 channel。
- 取消语义：同步 runner、external harness runtime/session 如何统一感知 cancel。
- 何时把插件私有 daemon heartbeat 提升为 Host `RuntimeLease`。
- 若未来 Host 做 claim lease，Platform 插件业务 queue 与 Host execution queue 如何避免双队列混乱。
