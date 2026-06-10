# Agent-owned Context 协议设计

本文档描述插件化 AgentRunner 场景下的上下文边界**设计理由**。结论先行：LangBot 不应成为最终 agentic context manager；它提供 context substrate，AgentRunner 或其背后的 runtime 自己决定如何管理历史、压缩、召回和 KV cache。

> 涉及的数据结构（`AgentRunContext`、`ContextAccess`、`AgentRunAPIProxy` 等）唯一定义在 [PROTOCOL_V1.md](./PROTOCOL_V1.md)。本文只讲语义和约束，不重抄 schema。

## 1. 设计原则

### 1.1 Agent 拥有上下文策略

不同 runner 背后的 runtime 差异很大：

- 官方 local-agent 可能依赖 LangBot 的模型、工具、知识库和存储。
- Claude Code SDK / Codex 类 runtime 有自己的 session、transcript、tool loop 和上下文压缩。
- Pi Agent SDK 或外部 agent 平台可能只需要当前事件和一个外部 conversation key。

因此 LangBot 不应强行决定最终传给模型的历史窗口。Host 只提供：当前事件的完整结构化信息、稳定身份和会话引用、可授权读取的 history / event / artifact / state API、可投影给外部 harness 的 scoped context / SDK-owned MCP bridge / resource handles、payload hard cap 和权限 guardrail。

### 1.2 Host 不定义通用历史窗口

历史窗口策略不是 AgentRunner 协议或 Query entry adapter 的核心概念。Host 只提供 history pull API、cursor、hard cap 和权限边界；runner 自己决定是否读取、读取多少、如何截断和压缩。

正确的问题不是"LangBot 每轮裁几轮历史给 agent"，而是：

- 这类 runner 是否自管 context？
- 事件到来时 host 应 inline 哪些最小信息？
- agent 需要更多上下文时通过什么 API 拉取？
- host 如何保证安全、可审计和可分页？

### 1.3 Host 保存事实源，Agent 管理 working context

三类数据要分开：

- `EventLog`: Host 保存原始事件、工具调用、投递结果、错误和系统事件。
- `Transcript`: Host 从 EventLog 投影出的对话视图，用于 UI、审计和按需历史读取。
- `Working context`: Agent 本轮实际送进模型或 runtime 的上下文，由 AgentRunner 决定。

LangBot 不提供 host-side inline history window。简单 runner 如果需要历史窗口，应在 runner 内部通过 Host history API 拉取并裁剪。

## 2. Event 到来时传什么

默认 `AgentRunContext`（PROTOCOL_V1 §5.2）应尽量小且稳定。默认规则：

- Host MUST NOT inline full history by default.
- Host SHOULD inline only current event / input and context handles.
- Runner owns working-context assembly.
- Runner MAY use Host history / event / artifact / state / storage API when authorized.
- Official runners MUST consume Host infrastructure through the same public API as third-party runners.

### 2.1 必须 inline 的内容

当前 event 的类型/id/时间/source；当前输入文本和结构化内容；附件/文件/图片的 metadata 和 artifact ref；actor / subject / conversation / thread / bot / workspace；delivery 能力；已授权资源列表；context cursors 和可用 API 能力；Agent/runner config。这些是 agent 决定下一步所需的最低信息。

### 2.2 默认不 inline 的内容

完整历史消息、大文件全文、大工具结果、全量知识库内容、平台原始 payload 大对象、每轮重新生成的大段 summary。这些会破坏跨进程序列化成本、泄露范围、KV cache 稳定性，也会迫使 host 替 agent 做 context 策略。

### 2.3 不提供 Host Inline History Window

`AgentRunContext` 不包含 `bootstrap` 字段。Host 不下发历史窗口，也不通过 Pipeline 配置决定窗口大小。runner 若需要类似 `recent_tail` 的策略，应在自己的 manifest/config schema 中声明参数，并在 runner 内部通过 history API 读取、裁剪和压缩。Host 只负责权限、分页、hard cap 和事实源。

## 3. ContextAccess 的作用

`ContextAccess`（PROTOCOL_V1 §5.8）是 host 交给 agent 的上下文读取入口描述，告诉 agent：当前事件位于哪条 conversation / thread、若需要更多历史从哪个 cursor 开始拉、host inline 了什么没 inline 什么、当前 run 有哪些 context API 权限。

## 4. Agent 如何获取更多上下文

所有 API 都走 `AgentRunAPIProxy`（PROTOCOL_V1 §8），由 host 用 `run_id` 校验。

外部 harness 不能直接访问 LangBot 资源。无论是 history、event、artifact、state、model、tool、knowledge base，还是 LangBot skills，都必须通过 SDK runtime 转发到 Host API，并由 Host 按 active `run_id`、runner identity、binding resource policy 和 caller plugin identity 校验。harness 自己的 native tools 只属于 harness 执行环境，不能绕过 SDK runtime 访问 LangBot 内部资源。

### 4.1 History

```python
await api.history_page(conversation_id=ctx.context.conversation_id,
                       before_cursor=ctx.context.latest_cursor,
                       limit=50, direction="backward", include_artifacts=False)
```

返回 `HistoryPage`（schema 见 PROTOCOL_V1 §8）。

约束：`limit` 有 host hard cap；默认只能读当前 conversation / thread；跨会话读取需 binding policy / run authorization snapshot 授权；返回 artifact ref，不默认返回大文件内容。

### 4.2 Search

```python
await api.history_search(query="用户之前提到的数据库连接信息",
                         filters={"conversation_id": ..., "event_types": ["message.received"]},
                         top_k=10)
```

Search 可先用数据库全文索引，后续接 embedding recall。它是 host 检索能力，不等于 agent 的长期记忆策略。

### 4.3 Event / Artifact / State

- Event API（`events.get` / `events.page`）用于读取非消息事件、工具事件、系统事件。Agent 不应把所有事件都当成 user/assistant message。
- Artifact API（`artifact_metadata` / `artifact_read` / `artifact_read_range`）必须校验 artifact 所属 conversation / run / binding，校验 MIME / 大小 / 过期 / 权限，大文件按 range/file-key 读取，工具大结果也应 artifact 化。
- State API（`state.get` / `set`）是可选寄宿能力。自管 runtime 可以完全不用；依附 LangBot 的官方 runner 可以使用，例如 `external.session_id`、`summary.checkpoint`。

### 4.4 大文件与工具协作

大文件、多模态输入和工具产物不要内联进 prompt 或 tool result：message/content 里只放小文本和必要摘要；大文件、图片、音频、长工具输出返回 artifact ref（`artifact_id`、`mime_type`、`size`、`digest`、`summary`、`expires_at`、`permissions`）。工具之间传递大结果时传 artifact ref，不传完整 blob。Host 校验 artifact 是否属于当前 run / scope，默认不允许插件直接读任意本地路径；临时文件应有 TTL 和清理机制。

### 4.5 External harness context projection

外部 harness 的总体边界以 [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md) §4.8 为准。本节只描述 context projection 的推荐形态。

Claude Code、Codex、Kimi Code 这类 runtime 通常已有自己的 session、工具 loop、MCP 加载、上下文压缩和工作目录。LangBot 不应把它们改造成"host prompt assembler"，而应提供可审计的事件和资源投影。推荐 projection 形态：

- `agent-context.json`：结构化 JSON，包含 `run_id`、`event`、`actor`、`subject`、`input`、`delivery`、`resources`、`context`、`state`、`runtime`。
- `LANGBOT_CONTEXT.md`：人类可读摘要。
- `resources`：只包含本次 run 授权后的资源句柄和能力摘要，不暴露 Host 内部私有对象、secret 或资源内容。
- `skills`：LangBot skills 不是直接投影给 harness native tool loop 的文件能力；已授权 skill 应由 Host / sandbox 封装成 scoped tools，再通过 `ctx.resources.tools`、`AgentRunAPIProxy` 或 SDK-owned MCP bridge 暴露。
- `MCP config`：只投影 per-run、scoped 的 SDK-owned bridge 或外部 MCP 连接配置；LangBot 资源访问必须回到 SDK runtime / Host API，不允许 harness 通过自带 MCP/native tool 直接读 Host 内部资源。
- `state pointers`：外部 session id、working directory、checkpoint 等小型 JSON 状态通过 Host state API 保存。

当前 Claude Code runner 使用 schema `langbot.agent_runner.external_harness_context.v1`（现状见 OFFICIAL_RUNNER_PLUGINS §7）。这类 projection 是"把 LangBot 事实源和授权资源句柄交给 harness"，不是"把 LangBot 资源本体或内部权限交给 harness"，也不是"由 LangBot 决定最终模型上下文"。

## 5. Runner 上下文边界

Host 只给当前事件、当前输入和 context handles。Runner 是否能拉取历史、事件、artifact、state 或 storage，以运行时 `ctx.context.available_apis` 为准；runner 自己决定是否拉取历史、是否搜索、何时摘要、如何构造最终 prompt。

## 6. KV cache 友好的上下文管理

支持 Claude Code SDK、Codex、Pi Agent SDK 等 runtime 时，必须避免每轮由 LangBot 重组大块 prompt：

- 稳定 session key：`workspace/bot/binding/runner/conversation/thread`。
- 每轮只传 delta：当前 event、artifact refs、少量 runtime metadata。
- 历史 append-only：不要每轮改写同一段 history 文本。
- Summary checkpoint 稳定：只有压缩发生时产生新 checkpoint。
- 大文件和工具结果 artifact 化。
- Tool/context API schema 稳定，数据通过 API 拉取而非塞入 prompt。
- 对自管 runtime，优先让它复用自身 session/cache，而不是强制 LangBot 每轮重放 transcript。
- LiteLLM 接入后，模型窗口元信息应作为 resource/runtime metadata 暴露给 runner，由 runner 决定预算和压缩策略。

稳定 session key 的用途是隔离外部 runtime 的 resume/cache/state，不是改变 PROTOCOL_V1 §13 定义的 Agent 复用和 dispatch 边界。只有当某个外部 harness 的同一 native session 不支持并发 turn 时，runner 或 future runtime control plane 才应按 external session key 做 turn-level 串行化。

对长期运行的 external harness / daemon，推荐运行形态是 reader 与 writer 分离：一个 session reader 独占读取 stdout/SSE/native event stream，并把 native event 转成 `AgentRunResult` 或 task progress；用户输入只作为 turn write 进入该 session。当前一次性 CLI subprocess runner 可以继续在单次 `run(ctx)` 内同步收集 stdout，但后续改成长连接时不应让多个 request 同时读取同一 native stream。

## 7. Host guardrail

Agent 自管 context 不代表无限制访问。LangBot 仍必须控制：每次 run 的 active `run_id`、runner identity、当前 binding 的 resource policy、conversation / actor / subject scope、page size / artifact read size / API rate limit、跨会话读取权限、数据脱敏和敏感变量过滤、审计日志。Host 不负责"最佳上下文策略"，但负责"不越权、不爆内存、不不可审计"。

外部 harness 的 native tools、shell、MCP 或 skill 机制不构成 LangBot 资源授权边界。只要访问的是 LangBot 持有的资源，就必须经 SDK runtime 转发并接受 Host 校验；完整边界见 HOST_SDK §4.8。

## 8. 官方 runner 与业务编排边界

官方 runner 插件可以把状态寄宿在 LangBot，但必须和第三方 runner 一样通过公开 Host API 消费。LangBot core 不内置官方 agent 的业务流程（prompt 组装、tool loop、RAG 编排、summary/compaction、"local-agent 专用"状态字段）。

官方 local-agent 应作为"依附 LangBot 基础设施的复杂 runner 参考实现"：transcript/history 通过 `api.history_page()` / `api.history_search()` 读取，summary/checkpoint/外部 session id/用户偏好通过 `api.state_get()` / `api.state_set()` 或 storage 方法保存，图片/文件/工具大结果通过 `api.artifact_metadata()` / `api.artifact_read_range()` 读取，模型/工具/知识库通过 `api.invoke_llm()` / `api.call_tool()` / `api.retrieve_knowledge()` 调用。这样 LangBot 保持为通用 agent host，不变成内置 agent 框架。具体迁移要求见 [OFFICIAL_RUNNER_PLUGINS.md](./OFFICIAL_RUNNER_PLUGINS.md)。
