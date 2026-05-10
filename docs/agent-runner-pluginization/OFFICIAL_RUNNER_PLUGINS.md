# 官方 AgentRunner 插件仓库计划

本文档描述内置 `RequestRunner` 迁出 LangBot 后，官方 runner 插件仓库应如何组织。建议新建仓库：

```text
/home/glwuy/langbot-app/langbot-official-agent-runners
```

远端仓库名建议：`langbot-official-agent-runners`。

## 1. 为什么新仓库

官方 runner 插件会和 LangBot 主仓库、SDK 仓库以不同节奏迭代：

- LangBot 主仓库只维护宿主协议和调度。
- SDK 仓库维护 AgentRunner 组件和 runtime 协议。
- 官方 runner 插件承载业务 runner 的具体实现和第三方平台适配。

不要把官方 runner 插件继续留在 LangBot 主仓库，否则容易重新形成“宿主和业务 runner 绑死”的结构。

## 2. 仓库结构

建议采用 monorepo：

```text
langbot-official-agent-runners/
  README.md
  pyproject.toml
  packages/
    local-agent/
      manifest.yaml
      components/default.yaml
      main.py
      src/
      tests/
    dify-agent/
    n8n-agent/
    coze-agent/
    dashscope-agent/
    langflow-agent/
    tbox-agent/
  shared/
    langbot_agent_runner_utils/
      __init__.py
      context.py
      config.py
      streaming.py
      tool_calling.py
      errors.py
  tests/
    fixtures/
    integration/
```

先用一个仓库统一迁移，避免每个 runner 复制 SDK helper、测试夹具、发布脚本。

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

- LangBot 构造 `ctx.messages`、`ctx.input`、`ctx.resources`
- 插件负责选择模型、拼请求、调用 LLM、处理 tool call loop、输出 result stream
- 插件不能绕过 `ctx.resources` 调用未授权模型、工具或知识库

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

## 9. 验收标准

- 每个旧 runner 都有对应官方 AgentRunner 插件。
- 旧 runner 配置能无损复制到新 `runner_config[id]`。
- LangBot 主仓库不再通过 `RequestRunner` 执行业务 runner。
- 官方插件测试覆盖非流式、流式、错误、timeout、配置缺失。
- `local-agent` 插件能完成模型 fallback、tool calling、知识库检索。
