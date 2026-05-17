# 官方 AgentRunner 插件迁移计划

本文档描述内置 `RequestRunner` 迁出 LangBot 后，官方 runner 插件如何组织、迁移和验收。

当前实现已经进入过渡阶段：

- LangBot 主聊天路径通过 `AgentRunOrchestrator` 调用插件化 `AgentRunner`。
- 旧 `src/langbot/pkg/provider/runners/*` 仍保留，作为迁移参考和回退分析材料；在官方插件迁移完成前不要求删除。
- 官方 runner 当前以独立插件目录/仓库推进，例如 `langbot-local-agent/` 和 `langbot-agent-runner/*-agent/`。不再要求先落地单一 monorepo。

## 1. 为什么新仓库

官方 runner 插件会和 LangBot 主仓库、SDK 仓库以不同节奏迭代：

- LangBot 主仓库只维护宿主协议和调度。
- SDK 仓库维护 AgentRunner 组件和 runtime 协议。
- 官方 runner 插件承载业务 runner 的具体实现和第三方平台适配。

不要把官方 runner 插件重新绑死在 LangBot 主仓库内。允许开发期使用本地路径插件，但运行边界必须保持为：

- LangBot 提供通用宿主能力：上下文、资源授权、模型/工具/知识库调用代理、结果归一。
- 插件消费这些能力，实现具体 runner 行为。
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
| `dashscope-app-api` | `langbot/dashscope-agent` | `plugin:langbot/dashscope-agent/default` |
| `langflow-api` | `langbot/langflow-agent` | `plugin:langbot/langflow-agent/default` |
| `tbox-app-api` | `langbot/tbox-agent` | `plugin:langbot/tbox-agent/default` |

每个插件可以后续提供多个 runner，但迁移目标的默认 runner 统一叫 `default`。

## 4. 迁移优先级

### Batch 1：打通协议

1. `local-agent`
2. `dify-agent`

原因：

- `local-agent` 覆盖模型、工具、知识库、流式、会话历史，是能力最完整的基准。
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
  protocol_version: "1"
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

## 6. local-agent 插件要求

`local-agent` 是最关键的官方插件，应等价迁移当前：

- model primary/fallback 选择
- prompt
- max-round
- knowledge-bases
- rerank-model
- rerank-top-k
- function calling
- streaming
- multimodal input
- conversation history
- monitoring metadata

与 LangBot 主仓库的责任边界：

- LangBot 构造 `ctx.prompt`、`ctx.messages`、`ctx.input`、`ctx.resources`
- 插件负责选择模型、拼请求、调用 LLM、处理 tool call loop、输出 result stream
- 插件不能绕过 `ctx.resources` 调用未授权模型、工具或知识库

为了保持旧内置 runner 行为，`local-agent` 插件必须优先消费宿主处理后的有效上下文：

- `ctx.prompt`：PreProcessor 和 `PromptPreProcessing` 插件事件处理后的有效 prompt；不是静态 `ctx.config["prompt"]` 的同义词。
- `ctx.messages`：已由宿主加载并经过 prompt preprocessing 的历史消息。
- `ctx.input.contents`：当前结构化输入，必须保留图片、文件等多模态内容。
- `ctx.runtime.metadata.streaming_supported`：当前 adapter 是否能消费流式输出。
- 宿主代理 action：模型、工具、知识库、rerank 调用应通过 `run_id/query_id` 找回当前 Query，以复用旧 runner 拥有的上下文能力。

## 7. 外部 runner 插件要求

外部平台 runner 迁移时遵循：

- 旧配置字段尽量保持同名，便于 migration 复制
- 输出统一转换为 `AgentRunResult`
- 外部 API timeout 从 runner config 读取
- 平台 conversation id 存 plugin storage 或 context runtime state，不能依赖 LangBot 内置 conversation uuid 私有结构
- 流式支持按平台能力声明，没有流式就只发 `message.completed`

## 8. 发布和安装策略

最终 LangBot 安装或升级时需要保证官方 runner 插件可用。可选方案：

1. 首次启动检测缺失官方 runner 插件并提示安装。
2. 打包发行版时预装官方 runner 插件。
3. 在 migration 前检查对应插件是否存在，不存在则自动安装或阻止迁移。

建议实现顺序：

- 开发阶段使用本地路径插件。
- 发布前支持 marketplace 安装。
- 历史配置 migration 只在官方插件可用时执行。
- 迁移期间保留旧内置 runner 文件，直到对应官方插件通过 parity 验收。

## 9. 验收标准

- 每个旧 runner 都有对应官方 AgentRunner 插件。
- 旧 runner 配置能无损复制到新 `runner_config[id]`。
- LangBot 主聊天路径不再通过 `RequestRunner` 执行业务 runner。
- 官方插件测试覆盖非流式、流式、错误、timeout、配置缺失。
- `local-agent` 插件能完成模型 fallback、tool calling、知识库检索、多模态输入、prompt preprocessing 后的有效 prompt 消费、rerank。
- 对外行为与旧内置 local-agent runner 保持一致；代码结构不需要相同。
