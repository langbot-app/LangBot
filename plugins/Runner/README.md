# LangBot 官方运行器插件

本目录包含 LangBot 官方维护的外部服务运行器插件。每个插件负责把第三方智能体、工作流或应用平台接入 LangBot 运行器协议 v1。

这些插件是协议消费者。LangBot 宿主端负责运行封套、资源授权、事实存储、拉取接口、结果归一化和投递生命周期；插件只负责对应服务的请求/响应映射和状态交接。

## 兼容分支

本仓库跟随 LangBot 4.11.x Runner 集成工作。联合测试时使用：

- `langbot-app/LangBot` 分支 `dev/4.11.x`
- `langbot-app/langbot-plugin-sdk` 分支 `dev/4.11.x`
- 本仓库 `plugins/Runner/LocalAgent` 目录，与 Core 同一提交联调
- `langbot-app/langbot-agent-control-plane` 分支 `main`

## 仓库边界

本目录不实现 LangBot EventGateway、事件订阅、事件通知、调度器或事件分发。这些系统属于 LangBot 宿主端或独立的事件相关分支。

本目录中的插件消费 LangBot 传入的 `RunnerContext`：

- `ctx.event`：事件优先的触发元数据。
- `ctx.conversation`、`ctx.actor`、`ctx.subject`：当前运行范围的元数据。
- `ctx.input`：当前用户或事件输入，包含多模态内容和 sandbox path / URL 等附件引用。
- `ctx.context`：上下文访问句柄、游标、内联策略和可用的拉取接口。
- `ctx.resources`：当前运行范围内已授权的模型、工具、知识库和存储能力。
- `ctx.state`：宿主端投影给当前运行的小型状态。
- `ctx.runtime`：截止时间、追踪标识、迁移适配路径中的查询标识，以及宿主端运行时元数据。
- `ctx.delivery`：当前投递面和流式输出 / 编辑能力。
- `ctx.config`：运行器绑定配置。
- `ctx.adapter`：迁移期入口适配字段；它不是协议 v1 核心字段。当前仅允许承载一次性入口元数据，例如 `ctx.adapter.extra.params` 里的业务参数；不应承载提示词、历史、RAG 结果、工具结构或已授权资源。

LangBot 默认不会内联完整历史。如果运行器需要更多上下文，应使用已授权的拉取接口，例如历史、事件、状态或存储接口。

## 外部执行器访问 LangBot 资产

进程内运行器，例如 `local-agent`，应直接调用 `RunnerAPIProxy`。

进程外执行器运行器，例如 ACP 兼容的编码智能体，可以通过 SDK 提供的 run-scoped MCP bridge 回访 LangBot 资产。该 bridge 只暴露当前 LangBot 授权的工具、知识库和历史访问入口，所有请求仍会被宿主端按 `run_id`、资源授权快照和调用方插件身份校验。

这不是全局 LangBot MCP 服务，运行器插件也不需要手写维护 LangBot 工具结构。单个运行器只负责把 LangBot 的 run 级指令、gateway 连接信息和输入转交给目标平台；如果目标平台需要 `langbot_history_page` 等桥接工具，LangBot 宿主端必须在本次运行的 `ctx.context.available_apis` / run authorization snapshot 中授权。

## 插件列表

| 插件 | 运行器标识 | 替代对象 | 说明 |
| --- | --- | --- | --- |
| `acp-agent-runner` | `plugin:langbot-team/ACPAgentRunner/default` | - | Agent Client Protocol 统一编码智能体集成 |
| `claude-code-agent` | `plugin:langbot-team/ClaudeCodeAgent/default` | - | Claude Code CLI 专属集成 |
| `codex-agent` | `plugin:langbot-team/CodexAgent/default` | - | Codex CLI 专属集成 |
| `deerflow-agent` | `plugin:langbot-team/DeerFlowAgent/default` | `deerflow-api` | DeerFlow LangGraph 集成 |
| `dify-agent` | `plugin:langbot-team/DifyAgent/default` | `dify-service-api` | Dify 应用集成 |
| `n8n-agent` | `plugin:langbot-team/N8nAgent/default` | `n8n-service-api` | n8n 工作流 webhook 集成 |
| `coze-agent` | `plugin:langbot-team/CozeAgent/default` | `coze-api` | Coze（扣子）机器人集成 |
| `dashscope-agent` | `plugin:langbot-team/DashScopeAgent/default` | `dashscope-app-api` | 阿里云 DashScope（百炼）集成 |
| `langflow-agent` | `plugin:langbot-team/LangflowAgent/default` | `langflow-api` | Langflow 流程集成 |
| `tbox-agent` | `plugin:langbot-team/TboxAgent/default` | `tbox-app-api` | 蚂蚁 Tbox（百宝箱）集成 |
| `weknora-agent` | `plugin:langbot-team/WeKnoraAgent/default` | `weknora-api` | WeKnora 智能体和知识库问答集成 |

官方 [LocalAgent](LocalAgent/README.md) 与 [RunnerDemo](RunnerDemo/README.md) 也维护在本目录。LocalAgent 直接调用 LangBot 托管的模型和工具，并保留独立测试。

## 协议 v1 对齐

外部服务运行器通常把 LangBot 输入映射为远端平台调用：

- 从 `ctx.input` 读取文本和多模态输入。
- 当目标平台需要时，从 `ctx.event`、`ctx.actor` 和 `ctx.subject` 读取事件、操作者和对象元数据。
- 从 `ctx.delivery` 和 `ctx.runtime` 读取投递和运行时决策。
- 从 `ctx.config` 读取静态运行器绑定配置。
- 尊重 `ctx.resources`，并通过 `RunnerAPIProxy` 访问任何由宿主端代理的模型、工具、知识、历史、事件、状态或存储。
- 使用 `ctx.context` 判断是否可以拉取更多历史或状态。
- 当第三方平台的完成事件或响应元数据提供 token usage 时，在 terminal `run.completed` 的 `usage` 字段上报最终聚合 usage；失败前已知的部分 usage 可随 `run.failed` 上报。不能观测 usage 时应省略该字段，表示 unknown，而不是 0。

Pipeline 适配字段只用于适配层：

- 业务参数可以出现在 `ctx.adapter.extra.params`。
- 不应从 `ctx.adapter.extra.prompt` 读取提示词数据。
- 如果运行器有静态绑定提示词，这类配置属于 `ctx.config.prompt`。如果需要有效提示词 / 指令数据，应在 `ctx.context.available_apis.prompt_get` 可用时通过宿主端提示词接口拉取。
- 历史不会通过 `ctx.bootstrap` 投递；需要更多上下文时应使用已授权的历史拉取接口。

不要依赖顶层 `ctx.params`、`ctx.prompt`、`ctx.messages` 或 `ctx.bootstrap` 作为协议 v1 字段。新的运行器代码应优先使用事件优先字段和拉取接口。

第三方智能体平台通常有自己的提示词、应用、机器人或工作流配置。除非某个具体平台集成明确需要这种映射，运行器不应把 LangBot 提示词重新解释为第三方平台提示词。

## 状态和历史

外部会话标识、会话期标识、工作流运行标识和检查点应存储在插件存储或宿主端状态接口中。运行器不应依赖 LangBot 内部会话 UUID 结构作为私有实现细节。

推荐模式：

- 使用 `RunnerAPIProxy.state_set(...)` 等宿主端状态接口或插件存储保存外部会话期标识。
- 只在需要时分页或搜索转录历史。
- 大型载荷应由 sandbox 或目标平台保存为 path、URL 或平台原生引用，不应通过 LangBot 额外维护一套文件持久化接口。
- 当运行器希望 LangBot 持久化小型 JSON 状态时，返回 `state.updated`。
- 当运行器生成文件或大型输出时，返回 sandbox path、URL 或平台原生引用。

## 运行中转向（Steering / 多轮追问）

当一次运行仍在进行时，用户继续发来的消息可以被「吸收进当前运行」，而不是排队等待后另起一次运行。这一能力称为 steering。

机制（宿主端已完整实现）：

- 运行器在 Runner 组件 manifest 中声明 `spec.capabilities.steering: true`。
- 宿主端在运行仍活跃时，将后续用户消息按 `run_id` 入队到该运行的 steering 队列（仅当本次运行有会话范围 `conversation_id`）。
- 运行器在轮次边界通过 `RunnerAPIProxy.steering_pull(mode="all"|"one")` 拉取这些追问，并把它们作为后续轮次喂给目标 agent。
- 宿主端只在 `ctx.context.available_apis.steering_pull` 为真时授权该接口；不可用时 SDK 抛出 `PermissionDeniedError`，运行器应回退为单轮行为。

重要约束：**一旦声明了 `steering` 能力，运行器必须在其所有传输路径上排空 steering 队列**。否则被「吸收进当前运行」的消息会在运行结束时被宿主端标记为 `steering.dropped` 而丢失——这比不声明该能力（消息会另起一次运行）更糟。

官方 `acp-agent-runner`、`claude-code-agent`、`codex-agent` 已实现 steering：它们在 `run()` 层用统一的轮次循环，在每个轮次完成后排空 `steering_pull`，并复用各自的会话恢复机制（ACP `session/resume`、Codex `thread/resume`、Claude Code `--session-id`）让追问延续同一会话，最终只发出一个终止性 `run.completed`。

当前实现的取舍：

- 注入发生在**轮次边界**（当前轮次完成后），不是 token 级别的中途打断。
- 追问以文本形式延续（`item.input.to_text()`）；追问自带的附件暂不转发。
- daemon 传输下追问不会丢失（仍会被排空并作为后续轮次执行），但会话连续性是尽力而为。

## 开发

### 环境要求

- Python 3.11+
- `uv` 包管理器

### 安装依赖

```bash
cd Runner  # from the repository root
uv sync --dev
```

### 运行测试

```bash
uv run pytest
```

### 运行代码检查

```bash
uv run ruff check .
```

## 架构

- 每个运行器插件都是 `Runner/` 下的独立目录，不使用 `packages/<plugin>` 结构。
- 本仓库作为插件集合分发，不作为可导入的 `langbot_runner` Python 包使用。
- 每个插件声明一个或多个 Runner 组件。
- 所有运行器都使用 Runner 协议 v1。
- 宿主端授权限定在单次运行范围内，并通过 `run_id`、`ctx.resources` 和调用方插件身份执行校验。
- Pipeline 适配转换由 LangBot 宿主端在调用运行器前完成；本仓库不拥有 Pipeline 内部逻辑。

## 相关仓库

- [LangBot Plugin SDK](https://github.com/langbot-app/langbot-plugin-sdk)：插件开发 SDK 和运行时。
- [LangBot](https://github.com/langbot-app/LangBot)：LangBot 主应用和 Host 实现。
- Runner Protocol v1：见 LangBot 仓库中的 `LangBot/docs/agent-runner-pluginization/PROTOCOL_V1.md`。
