# 官方 AgentRunner 插件迁移计划

本文档描述内置 `RequestRunner` 迁出 LangBot 后，官方 runner 插件如何组织、迁移和验收。它是 [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md) 和 [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md) 的下游落地计划，不是 LangBot 宿主协议的设计前提。QA 入口和 smoke 记录见 [AGENT_RUNNER_QA_GUIDE.md](./AGENT_RUNNER_QA_GUIDE.md)。

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
    acp-agent-runner/  claude-code-agent/  codex-agent/  dify-agent/  n8n-agent/  ...
```

后续可聚合进 monorepo，也可继续独立发布——这个选择不影响协议设计。重复逻辑优先沉淀到 SDK 或明确的共享 helper 包，不要把宿主私有结构泄漏给插件。旧 `src/langbot/pkg/provider/runners/*` 只作为历史行为对齐基准；当前未发布分支不提供旧内置 runner 的运行时 fallback。

## 2. 插件命名和 runner id

| 旧 runner | 官方插件 | runner id |
| --- | --- | --- |
| `local-agent` | `langbot/local-agent` | `plugin:langbot/local-agent/default` |
| `dify-service-api` | `langbot/dify-agent` | `plugin:langbot/dify-agent/default` |
| `n8n-service-api` | `langbot/n8n-agent` | `plugin:langbot/n8n-agent/default` |
| `coze-api` | `langbot/coze-agent` | `plugin:langbot/coze-agent/default` |
| - | `langbot/acp-agent-runner` | `plugin:langbot/acp-agent-runner/default` |
| - | `langbot/claude-code-agent` | `plugin:langbot/claude-code-agent/default` |
| - | `langbot/codex-agent` | `plugin:langbot/codex-agent/default` |
| `dashscope-app-api` | `langbot/dashscope-agent` | `plugin:langbot/dashscope-agent/default` |
| `deerflow-api` | `langbot/deerflow-agent` | `plugin:langbot/deerflow-agent/default` |
| `langflow-api` | `langbot/langflow-agent` | `plugin:langbot/langflow-agent/default` |
| `tbox-app-api` | `langbot/tbox-agent` | `plugin:langbot/tbox-agent/default` |
| `weknora-api` | `langbot/weknora-agent` | `plugin:langbot/weknora-agent/default` |

每个插件可后续提供多个 runner，但迁移目标的默认 runner 统一叫 `default`。

## 3. 迁移批次

- **Batch 1（打通协议）**：`local-agent`（能力最完整基准）、`acp-agent-runner` / `claude-code-agent` / `codex-agent`（外部 code-agent harness 路径）、`dify-agent`（传统 service API runner）。
- **Batch 2（外部 workflow）**：`n8n-agent`、`langflow-agent`（webhook/workflow 输入输出、timeout、外部 conversation id）。
- **Batch 3（平台 Agent API）**：`coze-agent`、`dashscope-agent`、`tbox-agent`、`deerflow-agent`、`weknora-agent`（平台特有响应格式、引用资料、文件/图片输入、外部 thread/session 状态）。

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
  config: []
  capabilities:        # 字段语义见 PROTOCOL_V1 §4.3
    streaming: true
execution:
  python: { path: ./main.py, attr: DefaultAgentRunner }
```

## 5. local-agent 插件方向

`local-agent` 是官方插件中能力最完整的消费者，但不是宿主协议的设计中心。它需要证明：一个主要依附 LangBot host 能力的 agent runner 可以通过公开协议完成模型、工具、知识库、状态、history、sandbox 文件访问、上下文压缩和消息投递。

迁移或重写需覆盖旧内置 runner 的用户可见能力：model primary/fallback 选择、prompt、knowledge-bases、rerank-model、rerank-top-k、function calling、streaming、multimodal input、conversation history、monitoring metadata。

责任边界与 Host API 消费方式见 AGENT_CONTEXT_PROTOCOL §8。关键约束：

- 从 `ctx.config` 读取静态绑定 `prompt`，**不**读取 `ctx.adapter.extra["prompt"]`；不消费 Query entry adapter 生成的历史窗口。
- 通过 `AgentRunAPIProxy.history` 拉取 transcript，而不是依赖 host 每轮强塞历史窗口。
- `ctx.input.contents` 保留图片/文件等多模态内容；RAG 只替换/插入文本部分，不丢图片/文件。
- 不能绕过 `ctx.resources` 调用未授权模型、工具或知识库。
- manifest 声明功能能力、LangBot 资源 permissions 和配置表单；实际授权来自 manifest permissions 与 binding resource policy、runner config、`ctx.context.available_apis` 和 Host run session snapshot 的交集。

### 5.1 Native Execution / Skills 后续接入

本阶段不把 sandbox/skills 做成 AgentRunner 协议字段。后续 sandbox/skills 分支合并后，命令执行、文件操作、skill、MCP managed process 应先由 Host / sandbox 封装成 scoped tools，再通过 `ctx.resources.tools` 和 SDK runtime 转发暴露给 runner。这让 local-agent 只消费授权后的 Host 基础设施，而不是直接持有宿主机执行能力。

## 6. 外部 runner 插件要求

外部平台 runner 迁移遵循：旧配置字段尽量保持同名便于 migration 复制；输出统一转换为 `AgentRunResult`；外部 API timeout 从 runner config 读取；平台 conversation id 存 plugin storage 或 context runtime state，不依赖 LangBot 内置 conversation uuid 私有结构；流式按平台能力声明，没有流式就只发 `message.completed`。

### 6.1 Code-agent harness runner

Claude Code、Codex、Kimi Code 这类 runner 不一定通过 LangBot 的模型/工具 loop 执行，可以依赖自己的 harness，但仍必须遵守统一 Host 边界。总体边界见 [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md) §4.8；context projection 形态见 [AGENT_CONTEXT_PROTOCOL.md](./AGENT_CONTEXT_PROTOCOL.md) §4.5；发布级要求见 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md)。

本文件只补充官方 runner 的实现要求：输入来自 `ctx.event` / `ctx.input`，不依赖 Pipeline 私有 `Query`；外部 session id / workspace / checkpoint 写入 Host state 或 plugin storage；插件实例边界见 PROTOCOL_V1 §13；CLI / subprocess runner 必须处理 timeout、取消、空输出、非零退出和 stderr 映射。

实现结构应把 provider-native output 解析与 LangBot result stream 组装分开：Claude stream-json、Codex JSONL、Kimi / OpenCode 事件等只在 runner adapter 内解析，输出统一归一为 `AgentRunResult`（`message.completed` / `message.delta`、`state.updated`、`run.completed` / `run.failed`）。文件和工具大结果留在当前 run 的 sandbox/workspace，通过消息 metadata、attachment ref 或 path 指向。未知 native event 不应导致 run 崩溃；应记录诊断 metadata 或 warning。新增 harness 时优先补 native fixture -> `AgentRunResult` 的转换测试，再接 WebUI smoke。

并发约束应按外部 session 粒度表达，而不是按 Agent / runner id / 插件实例表达；Agent 复用和全局锁边界见 PROTOCOL_V1 §13。若 runner 使用 `external.session_id` / `thread_id` resume 到同一 native session，且该 harness 不支持并发 turn，runner 应按稳定 external session key 串行写入；一次性 subprocess runner 可以只在单次 `run(ctx)` 内处理，长连接/daemon runner 则应采用 reader 独占 native stream、turn writer 串行写入的结构。

### 6.2 LangBot MCP gateway

外部 harness 不能直接持有进程内的 `plugin_runtime_handler`，也不能用自己的 native tools 直接访问 LangBot 资源。外部 harness runner 应通过稳定 HTTP MCP gateway 或 SDK-owned bridge 把 harness 的工具请求转回 SDK runtime / Host API：

- Gateway 由 runner 插件启动，暴露稳定的 `langbot_history_page`、`langbot_retrieve_knowledge`、`langbot_call_tool` 等最小工具面。
- Harness 每次调用必须携带当前 LangBot `run_id`；Host 仍按 run session、caller identity 和授权快照校验。
- Gateway 只转发 LangBot 资产访问，不承担外部 harness 的文件、进程或 native tool 权限边界。

第一批工具保持很小：history page、knowledge retrieve、authorized tool call。新增工具必须先有 Host action 权限与 run-scoped authorization，再由 gateway 投影。

## 7. Code-agent harness runner 当前形态

外部 code-agent harness 由直接 runner 插件承接，例如 `acp-agent-runner`、`claude-code-agent`、`codex-agent`，每个 runner 负责把目标 harness 的 native session、workspace、MCP bridge 和输出事件转换为统一 `AgentRunResult`。本地 smoke 验收入口与记录见 [AGENT_RUNNER_QA_GUIDE.md](./AGENT_RUNNER_QA_GUIDE.md)。

当前形态：

- Runner ID 示例：`plugin:langbot/acp-agent-runner/default`、`plugin:langbot/claude-code-agent/default`、`plugin:langbot/codex-agent/default`。
- Runner 可通过 ACP、远端 daemon、本机 subprocess 或外部 HTTP API 调用 harness；harness 的安装、登录态、workspace 和 provider-native 权限由该运行环境负责。
- Runner 会把当前 LangBot `run_id`、可访问资源摘要和 gateway 使用规则注入本次消息；harness 通过 gateway 回填 `run_id` 后访问 LangBot 资产。
- 外部 session id / workspace / checkpoint 写回 Host state 或 plugin storage，后续轮次可复用目标 harness 会话。

### 7.1 当前限制

这不是发布级安全边界实现；LangBot 只约束 LangBot 持有资产的访问，外部 harness 的文件、进程、workspace、provider-native MCP 和模型凭据由对应 runner 的运行环境承担。当前 `run_id` 可由系统提示词、ACP metadata 或 runner 自有 session metadata 传递给 harness 并由 gateway 校验。runtime 管控面方向见 [RUNTIME_CONTROL_PLANE_V2.md](./RUNTIME_CONTROL_PLANE_V2.md)。

## 8. 发布和安装策略

最终 LangBot 安装/升级时需保证官方 runner 插件可用，可选方案：首次启动检测缺失并提示安装；打包发行版预装；migration 前检查插件存在性。当前分支未发布，因此不把历史配置兼容或旧内置 runner fallback 写入运行时协议面。建议顺序：开发阶段用本地路径插件 → 发布前支持 marketplace 安装 → 若发布升级需要迁移历史配置，再在 release gate 中实现一次性 migration 并要求官方插件已可用。

## 9. 验收标准

- 每个目标 runner 都有对应官方 AgentRunner 插件和稳定 runner id；当前配置只使用 `ai.runner.id` + `ai.runner_config[id]`。
- LangBot 主聊天路径不再通过 `RequestRunner` 执行业务 runner。
- 官方插件测试覆盖非流式、流式、错误、timeout、配置缺失。
- `local-agent` 能完成模型 fallback、tool calling、知识库检索、多模态输入、静态绑定 prompt 消费、history API 拉取、rerank。
- 外部 code-agent harness runner 能消费 event-first context、投影 scoped resources、保存 external session state，并通过 WebUI Debug Chat smoke。
- `local-agent` 覆盖旧内置 runner 的用户可见核心能力；代码结构和运行路径不需要相同。
