# 官方 AgentRunner 插件迁移计划

本文档描述内置 `RequestRunner` 迁出 LangBot 后，官方 runner 插件如何组织、迁移和验收。
它是 [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md) 和
[AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md) 的下游落地计划，不是 LangBot
宿主协议的设计前提。

官方 `local-agent` 可以外移，也可以重写。设计重点不是保留旧内置 runner 的内部结构，
而是验证一个依附 LangBot host 基础设施的官方 agent 能否完整工作。同时，LangBot 的
host 协议必须服务 Claude Code SDK、Codex、Pi Agent SDK、外部 Agent 平台等自管
context/runtime 的 runner，不能被官方插件的实现细节绑死。

当前实现已经进入过渡阶段：

- LangBot 主聊天路径通过 `AgentRunOrchestrator` 调用插件化 `AgentRunner`。
- 旧 `src/langbot/pkg/provider/runners/*` 仍保留，作为迁移参考和回退分析材料；在官方插件迁移完成前不要求删除。
- 官方 runner 当前以独立插件目录/仓库推进，例如 `langbot-local-agent/` 和 `langbot-agent-runner/*-agent/`。不再要求先落地单一 monorepo。
- `claude-code-agent` 与 `codex-agent` 已作为外部 harness runner MVP 接入，用来验证 Claude Code / Codex / Kimi Code 这类自管 runtime 的边界。

## 1. 为什么新仓库

官方 runner 插件会和 LangBot 主仓库、SDK 仓库以不同节奏迭代：

- LangBot 主仓库只维护宿主协议和调度。
- SDK 仓库维护 AgentRunner 组件和 runtime 协议。
- 官方 runner 插件承载业务 runner 的具体实现和第三方平台适配。

不要把官方 runner 插件重新绑死在 LangBot 主仓库内。允许开发期使用本地路径插件，但运行边界必须保持为：

- LangBot 提供通用宿主能力：当前事件、context handles、资源授权、状态/存储、历史、artifact、模型/工具/知识库调用代理、结果归一。
- 插件消费这些公开能力，实现具体 runner 行为。
- LangBot 默认不把全量历史消息 inline 给 runner；runner 按需通过授权 API 拉取历史和 artifact。
- 旧内置 runner 只作为行为对齐的基准，不作为长期运行路径。

## 2. 仓库结构

当前推荐策略是“官方插件可独立发布，必要时共享 SDK helper”。开发期可以采用本地多目录布局：

```text
langbot-app/
  langbot-local-agent/
    manifest.yaml
    components/agent_runner/default.yaml
    components/agent_runner/default.py
    pkg/
    tests/
  langbot-agent-runner/
    claude-code-agent/
    codex-agent/
    n8n-agent/
    ...
```

后续可以把多个官方 runner 聚合进 monorepo，也可以继续独立发布。这个选择不影响协议设计；协议边界由 SDK 和 LangBot 宿主保证。

如果多个 runner 出现重复逻辑，优先沉淀到 SDK 或一个明确的共享 helper 包，不要把宿主私有结构泄漏给插件。

## 3. 插件命名和 runner id

固定映射：

| 旧 runner | 官方插件 | runner id |
| --- | --- | --- |
| `local-agent` | `langbot/local-agent` | `plugin:langbot/local-agent/default` |
| `dify-service-api` | `langbot/dify-agent` | `plugin:langbot/dify-agent/default` |
| `n8n-service-api` | `langbot/n8n-agent` | `plugin:langbot/n8n-agent/default` |
| `coze-api` | `langbot/coze-agent` | `plugin:langbot/coze-agent/default` |
| - | `langbot/claude-code-agent` | `plugin:langbot/claude-code-agent/default` |
| - | `langbot/codex-agent` | `plugin:langbot/codex-agent/default` |
| `dashscope-app-api` | `langbot/dashscope-agent` | `plugin:langbot/dashscope-agent/default` |
| `langflow-api` | `langbot/langflow-agent` | `plugin:langbot/langflow-agent/default` |
| `tbox-app-api` | `langbot/tbox-agent` | `plugin:langbot/tbox-agent/default` |

每个插件可以后续提供多个 runner，但迁移目标的默认 runner 统一叫 `default`。

## 4. 迁移优先级

### Batch 1：打通协议

1. `local-agent`
2. `claude-code-agent`
3. `codex-agent`
4. `dify-agent`

原因：

- `local-agent` 覆盖模型、工具、知识库、流式、会话历史，是能力最完整的基准。
- `claude-code-agent` / `codex-agent` 代表 Claude Code / Codex / Kimi Code 这类本地或外部 code-agent harness：它们通常自带 session、tool loop、上下文压缩和权限模型，LangBot 主要提供 IM 事件、资源投影、审计和状态指针。
- `dify-agent` 代表外部 Agent 平台调用，配置和错误处理能验证传统 service API runner 的迁移方式。

### Batch 2：迁移外部 workflow runner

1. `n8n-agent`
2. `langflow-agent`

这批主要验证 webhook/workflow 输入输出、timeout、外部 conversation id。

### Batch 3：迁移平台 Agent API

1. `coze-agent`
2. `dashscope-agent`
3. `tbox-agent`

这批主要验证平台特有响应格式、引用资料、文件/图片输入。

## 5. 每个官方插件的组件要求

每个插件至少包含：

```yaml
apiVersion: langbot/v1
kind: AgentRunner
metadata:
  name: default
  label:
    en_US: Dify Agent
    zh_Hans: Dify Agent
  description:
    en_US: Run a Dify application as a LangBot AgentRunner.
    zh_Hans: 将 Dify 应用作为 LangBot AgentRunner 运行。
spec:
  config: []
  capabilities:
    streaming: true
    tool_calling: false
    knowledge_retrieval: false
    multimodal_input: false
    event_context: true
    platform_api: false
    interrupt: false
    stateful_session: true
  permissions:
    models: []
    tools: []
    knowledge_bases: []
    storage: ["plugin"]
    files: []
    platform_api: []
execution:
  python:
    path: ./main.py
    attr: DefaultAgentRunner
```

## 6. local-agent 插件方向

`local-agent` 是官方插件中的重要消费者，但不是宿主协议的设计中心。它可以选择复用
旧实现，也可以完全重写。它需要证明：一个主要依附 LangBot host 能力的 agent runner
可以通过公开协议完成模型、工具、知识库、状态、history、artifact、上下文压缩和消息投递。

LangBot core 不应为了 local-agent 保留业务编排逻辑。local-agent 的 prompt 组装、history
拉取、summary/checkpoint、tool loop、RAG 编排、fallback、多模态处理都应在插件内完成。

迁移或重写时需要覆盖旧内置 runner 的用户可见能力：

- model primary/fallback 选择
- prompt
- knowledge-bases
- rerank-model
- rerank-top-k
- function calling
- streaming
- multimodal input
- conversation history
- monitoring metadata

与 LangBot 主仓库的责任边界：

- LangBot 构造当前事件、结构化输入、资源授权、context handles、state/storage 能力和 delivery 能力
- LangBot 不默认 inline 全量历史，不替插件组装最终模型上下文
- 插件负责选择模型、拼请求、调用 LLM、处理 tool call loop、输出 result stream
- 插件不能绕过 `ctx.resources` 调用未授权模型、工具或知识库

为了保持旧内置 runner 的用户可见行为，`local-agent` 插件应消费宿主处理后的有效输入和
受限 API，而不是读取宿主内部私有结构：

- `ctx.event` / `ctx.input`：当前结构化输入，必须保留图片、文件等多模态内容。
- `ctx.context`：history cursor、inline policy、可用 context API。
- `AgentRunAPIProxy.history`：按需读取 transcript，而不是依赖 host 每轮强塞历史窗口。
- `AgentRunAPIProxy.artifacts`：按需读取图片、文件、工具大结果。
- `AgentRunAPIProxy.state` / storage：保存 summary、外部 conversation id、用户偏好等可选状态。
- `ctx.resources`：已授权模型、工具、知识库、文件和 storage。
- `ctx.runtime.metadata.streaming_supported`：当前 adapter 是否能消费流式输出。
- 宿主代理 action：模型、工具、知识库、rerank 调用必须通过 `run_id` 校验资源权限。

`local-agent` 不应消费 Pipeline adapter 生成的 `max-round` / `bootstrap`
窗口，也不应读取 `ctx.adapter.extra.prompt`。它应从绑定配置读取静态
`prompt`，并通过 Host history API 拉取 transcript。Pipeline adapter 可以继续为旧入口
保留 `max-round` 兼容逻辑，但这不是 official local-agent 的行为契约。

建议 local-agent manifest 使用 hybrid 或 self-managed context：

```yaml
context:
  ownership: hybrid
  bootstrap: current_event
  max_inline_events: 0
  max_inline_bytes: 0
  supports_history_pull: true
  supports_history_search: true
  supports_artifact_pull: true
  owns_compaction: true
  wants_static_context_refs: true
```

这表示：LangBot 只给当前事件和 context handles；local-agent 自己决定是否拉取历史、是否搜索、
何时摘要、如何构造最终 prompt。

### 6.1 Native Execution / Skills 后续接入

本阶段不把 sandbox/skills 做成 AgentRunner 协议字段，也不预留 runner 可见字段。
后续 sandbox/skills 分支合并后，命令执行、文件操作、skill、MCP managed process
等能力应先由 LangBot Host 封装成 scoped tools，再通过 `ctx.resources.tools`
暴露给 runner。

这让 local-agent 只消费授权后的 Host 基础设施，而不是直接持有宿主机执行能力。
Claude Code / Codex 这类外部 harness runner 仍可先保留自己的执行模型，但要在文档和
配置中明确它们是否使用 LangBot 提供的工具投影。

## 7. 外部 runner 插件要求

外部平台 runner 迁移时遵循：

- 旧配置字段尽量保持同名，便于 migration 复制
- 输出统一转换为 `AgentRunResult`
- 外部 API timeout 从 runner config 读取
- 平台 conversation id 存 plugin storage 或 context runtime state，不能依赖 LangBot 内置 conversation uuid 私有结构
- 流式支持按平台能力声明，没有流式就只发 `message.completed`

### 7.1 Code-agent harness runner 要求

Claude Code、Codex、Kimi Code 这类 runner 不一定通过 LangBot 的模型/工具 loop 执行。它们可以依赖自己的 harness，但仍必须遵守 LangBot 的宿主边界：

- 输入来自 `ctx.event` / `ctx.input`，不能直接依赖 Pipeline 私有 `Query`。
- LangBot 授权后的资源应被投影为 harness 可读的 context 文件、MCP 配置、skill 目录、环境变量或 CLI 参数。
- 外部 session id、workspace、checkpoint 等跨轮次指针应写入 Host state 或 plugin storage；插件实例本身保持无状态。
- CLI / subprocess runner 必须处理 timeout、取消、空输出、非零退出和 stderr 映射。
- 如果外部 harness 选择使用 LangBot 托管执行能力，它应通过 scoped MCP/tool
  投影消费 Host 授权资源；否则它属于 external harness mode，不能声称具备
  LangBot-managed 执行隔离。
- 外部 harness 的 permission mode、allowed/disallowed tools、MCP 配置只是一层执行约束；LangBot 仍负责调用前的资源授权、路径策略、secret 过滤和审计。发布级要求见 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md)。

## 8. Claude Code runner 当前形态

当前 `claude-code-agent` 是最小可运行 MVP，用来证明外部 harness runner 可以接入同一套 AgentRunner 协议。

### 8.1 基本行为

- Runner ID：`plugin:langbot/claude-code-agent/default`
- 执行方式：本地 Claude Code CLI print mode，默认命令为 `claude -p`
- 默认输出：`message.completed` + `run.completed`
- 默认权限：`permission-mode=plan`、`max-turns=1`、`disallowedTools=AskUserQuestion`
- 默认状态：如果 Claude Code 返回 `session_id`，runner 通过 `state.updated` 写回 `external.session_id`
- 工作目录：优先使用 binding config 的 `working-directory`，其次使用 Host state 中的 `external.working_directory`

### 8.2 Context / skill / MCP 投影

Claude Code runner 当前把 LangBot event-first context 投影给外部 harness：

- 写入 `agent-context.json`，schema 为 `langbot.agent_runner.external_harness_context.v1`
- 写入 `LANGBOT_CONTEXT.md`，作为人类可读摘要
- 将 prompt prefix 指向 context 文件路径
- 可把 binding 提供的 `skills-json` 写入 Claude Code 原生 `.claude/skills/<name>/SKILL.md`
- 可把 binding 提供的 `mcp-config-json` 写成每次 run 的 MCP config，并通过 `--mcp-config` / `--strict-mcp-config` 传给 Claude Code

这些投影目前由 runner adapter 完成；长期更理想的形态是 LangBot Host 负责生成 scoped resource projection，runner 只负责适配 Claude Code 的原生目录和 CLI 参数。

### 8.3 已验证能力

2026-05-29 本地验证：

- WebUI Debug Chat 能通过 Pipeline adapter 调用 `claude-code-agent`
- Claude Code 能读取 LangBot context 文件并按指令输出 sentinel
- Skill 文件可以投影到 `.claude/skills/`
- MCP config 可以通过 binding config 投影为 Claude Code CLI 参数
- `external.session_id` 与 `external.working_directory` 可以写入 host-owned state，用于后续 resume
- `codex-agent` 可通过 WebUI Debug Chat 调用本机 Codex CLI，读取 LangBot event context，并把 Codex `thread_id` 写入 host-owned state
- 对需要代理的本地运行环境，`codex-agent` 可通过 binding config 的 `environment-json` 显式传递非 secret 环境变量

下一轮测试入口见 [PHASE1_QA_ACCEPTANCE_MATRIX.md](./PHASE1_QA_ACCEPTANCE_MATRIX.md)。

### 8.4 当前限制

- 不是发布级安全边界实现。
- 默认只做本地 CLI 调用，不实现完整执行隔离或 workspace 生命周期。
- 不实现 issue-centric 队列、复杂 workflow engine 或长期任务调度。
- 不代表 Codex 发布级能力或 Kimi runner 已完成；当前只验证外部 harness runner 的协议形态。

## 9. 发布和安装策略

最终 LangBot 安装或升级时需要保证官方 runner 插件可用。可选方案：

1. 首次启动检测缺失官方 runner 插件并提示安装。
2. 打包发行版时预装官方 runner 插件。
3. 在 migration 前检查对应插件是否存在，不存在则自动安装或阻止迁移。

建议实现顺序：

- 开发阶段使用本地路径插件。
- 发布前支持 marketplace 安装。
- 历史配置 migration 只在官方插件可用时执行。
- 迁移期间保留旧内置 runner 文件，直到对应官方插件通过 parity 验收。

## 10. 验收标准

- 每个旧 runner 都有对应官方 AgentRunner 插件。
- 旧 runner 配置能无损复制到新 `runner_config[id]`。
- LangBot 主聊天路径不再通过 `RequestRunner` 执行业务 runner。
- 官方插件测试覆盖非流式、流式、错误、timeout、配置缺失。
- `local-agent` 插件能完成模型 fallback、tool calling、知识库检索、多模态输入、静态绑定 prompt 消费、history API 拉取、rerank。
- `claude-code-agent` 或同类 code-agent harness runner 能消费 event-first context、投影 scoped resources、保存 external session state，并通过 WebUI Debug Chat smoke。
- 对外行为与旧内置 local-agent runner 保持一致；代码结构不需要相同。
