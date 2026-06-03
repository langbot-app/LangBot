# 官方 AgentRunner 插件迁移计划

本文档描述内置 `RequestRunner` 迁出 LangBot 后，官方 runner 插件如何组织、迁移和验收。它是 [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md) 和 [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md) 的下游落地计划，不是 LangBot 宿主协议的设计前提。验收状态见 [PROGRESS.md](./PROGRESS.md)，QA 入口见 [PHASE1_QA_ACCEPTANCE_MATRIX.md](./PHASE1_QA_ACCEPTANCE_MATRIX.md)。

官方 `local-agent` 可以外移，也可以重写。设计重点不是保留旧内置 runner 的内部结构，而是验证一个依附 LangBot host 基础设施的官方 agent 能否完整工作。同时，LangBot host 协议必须服务 Claude Code SDK、Codex、Pi Agent SDK、外部 Agent 平台等自管 context/runtime 的 runner，不能被官方插件的实现细节绑死。

## 1. 仓库组织

官方 runner 插件与 LangBot 主仓库、SDK 仓库以不同节奏迭代：LangBot 主仓库只维护宿主协议和调度，SDK 仓库维护 AgentRunner 组件和 runtime 协议，官方 runner 插件承载业务 runner 的具体实现和第三方平台适配。

当前推荐"官方插件可独立发布，必要时共享 SDK helper"。开发期采用本地多目录布局：

```text
langbot-app/
  langbot-local-agent/                # plugin:langbot/local-agent/default
    manifest.yaml
    components/agent_runner/default.{yaml,py}
  langbot-agent-runner/               # 外部服务 runner 仓库
    claude-code-agent/  codex-agent/  dify-agent/  n8n-agent/  ...
```

后续可聚合进 monorepo，也可继续独立发布——这个选择不影响协议设计。重复逻辑优先沉淀到 SDK 或明确的共享 helper 包，不要把宿主私有结构泄漏给插件。旧 `src/langbot/pkg/provider/runners/*` 在官方插件迁移完成前保留作为行为对齐基准，不作为长期运行路径。

## 2. 插件命名和 runner id

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

每个插件可后续提供多个 runner，但迁移目标的默认 runner 统一叫 `default`。

## 3. 迁移批次

- **Batch 1（打通协议）**：`local-agent`（能力最完整基准）、`claude-code-agent` / `codex-agent`（外部 code-agent harness 边界）、`dify-agent`（传统 service API runner）。
- **Batch 2（外部 workflow）**：`n8n-agent`、`langflow-agent`（webhook/workflow 输入输出、timeout、外部 conversation id）。
- **Batch 3（平台 Agent API）**：`coze-agent`、`dashscope-agent`、`tbox-agent`（平台特有响应格式、引用资料、文件/图片输入）。

## 4. 每个官方插件的组件要求

每个插件至少包含一个 `AgentRunner` 组件，manifest 示例：

```yaml
apiVersion: langbot/v1
kind: AgentRunner
metadata:
  name: default
  label: { en_US: Dify Agent, zh_Hans: Dify Agent }
  description:
    en_US: Run a Dify application as a LangBot AgentRunner.
    zh_Hans: 将 Dify 应用作为 LangBot AgentRunner 运行。
spec:
  protocol_version: "1"
  config: []
  capabilities:        # 字段语义见 PROTOCOL_V1 §4.3
    streaming: true
    event_context: true
    stateful_session: true
  permissions:         # 字段语义见 PROTOCOL_V1 §4.4
    storage: ["plugin"]
  context:             # 字段语义见 PROTOCOL_V1 §4.5
    supports_history_pull: true
    owns_compaction: true
execution:
  python: { path: ./main.py, attr: DefaultAgentRunner }
```

## 5. local-agent 插件方向

`local-agent` 是官方插件中能力最完整的消费者，但不是宿主协议的设计中心。它需要证明：一个主要依附 LangBot host 能力的 agent runner 可以通过公开协议完成模型、工具、知识库、状态、history、artifact、上下文压缩和消息投递。

迁移或重写需覆盖旧内置 runner 的用户可见能力：model primary/fallback 选择、prompt、knowledge-bases、rerank-model、rerank-top-k、function calling、streaming、multimodal input、conversation history、monitoring metadata。

责任边界与 Host API 消费方式见 AGENT_CONTEXT_PROTOCOL §8。关键约束：

- 从 `ctx.config` 读取静态绑定 `prompt`，**不**读取 `ctx.adapter.extra["prompt"]`；不消费 Query entry adapter 生成的历史窗口。
- 通过 `AgentRunAPIProxy.history` 拉取 transcript，而不是依赖 host 每轮强塞历史窗口。
- `ctx.input.contents` 保留图片/文件等多模态内容；RAG 只替换/插入文本部分，不丢图片/文件。
- 不能绕过 `ctx.resources` 调用未授权模型、工具或知识库。
- manifest 声明自管上下文能力（`context.supports_history_pull/search`、`owns_compaction` 等）。

### 5.1 Native Execution / Skills 后续接入

本阶段不把 sandbox/skills 做成 AgentRunner 协议字段。后续 sandbox/skills 分支合并后，命令执行、文件操作、skill、MCP managed process 应先由 Host 封装成 scoped tools，再通过 `ctx.resources.tools` 暴露给 runner。这让 local-agent 只消费授权后的 Host 基础设施，而不是直接持有宿主机执行能力。

## 6. 外部 runner 插件要求

外部平台 runner 迁移遵循：旧配置字段尽量保持同名便于 migration 复制；输出统一转换为 `AgentRunResult`；外部 API timeout 从 runner config 读取；平台 conversation id 存 plugin storage 或 context runtime state，不依赖 LangBot 内置 conversation uuid 私有结构；流式按平台能力声明，没有流式就只发 `message.completed`。

### 6.1 Code-agent harness runner

Claude Code、Codex、Kimi Code 这类 runner 不一定通过 LangBot 的模型/工具 loop 执行，可以依赖自己的 harness，但仍必须遵守 Host 边界：输入来自 `ctx.event` / `ctx.input`，不依赖 Pipeline 私有 `Query`；授权资源投影为 harness 可读的 context 文件、MCP 配置、skill 目录、环境变量或 CLI 参数（投影形态见 AGENT_CONTEXT_PROTOCOL §4.5）；外部 session id / workspace / checkpoint 写入 Host state 或 plugin storage，插件实例保持无状态；CLI / subprocess runner 必须处理 timeout、取消、空输出、非零退出和 stderr 映射；harness 的 permission mode / allow-deny / MCP 配置只是一层执行约束，Host 仍负责调用前的资源授权、路径策略、secret 过滤和审计（发布级要求见 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md)）。

### 6.2 SDK-owned LangBot MCP bridge

外部 harness 不能直接持有进程内的 `plugin_runtime_handler`，因此不能像 `local-agent` 一样直接调用 `AgentRunAPIProxy`。当前轻量方案是由 SDK 提供一层 per-run MCP bridge：

- `AgentRunner.create_external_mcp_bridge(ctx)` 是 runner 父类入口。
- Bridge 由 `AgentRunAPIProxy` 和 `AgentRunContext` 构造，生命周期只覆盖当前 run。
- Bridge 暴露 SDK 中显式注解的 `AgentRunExternalTools`，而不是导出全部 SDK action；MCP tool schema 由注解和 Pydantic args model 生成。
- stdio MCP proxy 只把外部 harness 的 MCP 调用转发回当前 run 的本地 bridge；run 结束后 bridge 关闭。

第一批工具保持很小：当前事件快照、history page、knowledge retrieve、authorized tool call。新增工具必须先进入 SDK-owned annotated surface，再由 MCP adapter 自动投影。

## 7. Claude Code / Codex runner 当前形态

`claude-code-agent` 与 `codex-agent` 是最小可运行 MVP，用来证明外部 harness runner 可以接入同一套 AgentRunner 协议。本地 smoke 验收记录见 [PROGRESS.md](./PROGRESS.md) 与 [PHASE1_QA_ACCEPTANCE_MATRIX.md](./PHASE1_QA_ACCEPTANCE_MATRIX.md)。

### 7.1 Claude Code runner

- Runner ID：`plugin:langbot/claude-code-agent/default`，执行方式：本地 Claude Code CLI print mode（默认 `claude -p`）。
- 默认输出 `message.completed` + `run.completed`；默认权限 `permission-mode=plan`、`max-turns=1`、`disallowedTools=AskUserQuestion`。
- 投影：写入 `agent-context.json`（schema `langbot.agent_runner.external_harness_context.v1`）和 `LANGBOT_CONTEXT.md`；可把 `skills-json` 投影到 `.claude/skills/<name>/SKILL.md`；可把 `mcp-config-json` 写成每次 run 的 MCP config 经 `--mcp-config` / `--strict-mcp-config` 传入；可通过 `enable-langbot-mcp=true` 启用 SDK-owned per-run LangBot MCP bridge。
- 状态：Claude Code 返回 `session_id` 时通过 `state.updated` 写回 `external.session_id`；工作目录优先用 config 的 `working-directory`，其次用 Host state 的 `external.working_directory`。

### 7.2 Codex runner

- Runner ID：`plugin:langbot/codex-agent/default`，执行方式：本地 Codex CLI，读取 LangBot event context。
- Codex `thread_id` 写回 host-owned state；支持 SDK-owned per-run LangBot MCP bridge；需要代理的本地环境可通过 config 的 `environment-json` 显式传递非 secret 环境变量。

### 7.3 当前限制

不是发布级安全边界实现；默认只做本地 CLI 调用，不实现完整执行隔离或 workspace 生命周期；不实现 issue-centric 队列、复杂 workflow engine 或长期任务调度；Codex 仅验证协议形态，不代表 Codex 发布级能力或 Kimi runner 已完成。runtime 管控面方向见 [RUNTIME_CONTROL_PLANE_V2.md](./RUNTIME_CONTROL_PLANE_V2.md)。

## 8. 发布和安装策略

最终 LangBot 安装/升级时需保证官方 runner 插件可用，可选方案：首次启动检测缺失并提示安装；打包发行版预装；migration 前检查插件存在性。建议顺序：开发阶段用本地路径插件 → 发布前支持 marketplace 安装 → 历史配置 migration 只在官方插件可用时执行 → 迁移期间保留旧内置 runner 文件，直到对应官方插件通过 parity 验收。

## 9. 验收标准

- 每个旧 runner 都有对应官方 AgentRunner 插件，旧配置能无损复制到新 `runner_config[id]`。
- LangBot 主聊天路径不再通过 `RequestRunner` 执行业务 runner。
- 官方插件测试覆盖非流式、流式、错误、timeout、配置缺失。
- `local-agent` 能完成模型 fallback、tool calling、知识库检索、多模态输入、静态绑定 prompt 消费、history API 拉取、rerank。
- `claude-code-agent` 或同类 code-agent harness runner 能消费 event-first context、投影 scoped resources、保存 external session state，并通过 WebUI Debug Chat smoke。
- 对外行为与旧内置 local-agent runner 一致；代码结构不需要相同。
