# MCP Resources PR #2215 Review

> 更新日期: 2026-06-29
> 分支: `mcp_resources`
> PR: langbot-app/LangBot#2215
> 主题: MCP Resources 在 LangBot 中的产品价值、AgentRunner 集成方式与后续架构方向

## 结论

PR #2215 对 LangBot 有明确价值：它补齐了 MCP 协议中 Resources 这一重要能力，让 MCP server 不再只暴露 tools，也可以暴露文档、代码片段、配置、日志、图片等上下文资源。管理端可以发现和预览资源，Agent 也可以通过当前实现按需列出和读取资源。

但当前 AgentRunner 层的接入方式更接近一个可用的第一阶段方案，而不是最终架构。现在 MCP Resources 被包装成两个 synthetic tools：

- `langbot_mcp_list_resources`
- `langbot_mcp_read_resource`

这让模型可以通过 function calling 主动探索资源，落地成本低，也复用了已有 `ToolManager` / `LocalAgentRunner` 的工具调用链路。不过从 MCP 规范和主流实现来看，Resources 更适合作为一种一等上下文来源，而不是长期隐藏在工具列表里。

建议保留当前 synthetic tools 作为探索能力，同时把后续主线设计调整为：MCP Resources 是 pipeline / conversation / message 级别可选择、可固定、可审计的上下文输入。

## 当前实现判断

当前 AgentRunner 集成路径如下：

```text
Pipeline 绑定 MCP server
  -> query.variables['_pipeline_bound_mcp_servers']
  -> Preproc 为 local-agent 加载工具
  -> ToolManager.get_all_tools()
  -> MCPLoader 注入 synthetic resource tools
  -> LocalAgentRunner 将工具 schema 传给模型
  -> 模型发起 list/read tool call
  -> ToolManager.execute_func_call()
  -> MCPLoader 调 MCP session.list_resources/read_resource
  -> tool result 回灌给模型
```

这个路径的优点是：

- 复用现有工具调用机制，改动范围小。
- Agent 可以按需探索资源，不需要每轮预先读取所有资源。
- 可以沿用 pipeline 绑定的 MCP server 范围，避免越权读取未绑定 server。
- 对已有 MCP tools 行为影响较小。

主要问题是：

- Resources 在语义上被降级成 tools，和 MCP 规范里的 resource primitive 不完全一致。
- 模型必须先理解并主动调用 `list/read`，资源不会自然成为上下文。
- pipeline 不能配置“默认携带某些资源”或“本轮附加某些资源”。
- UI 资源 tab 目前是管理端预览能力，和 Agent 上下文选择没有打通。
- 对 blob、图片、大文件、结构化资源的处理还比较粗糙。
- 缺少 resource templates、订阅更新、缓存、chunk、token budget、trace 与审计策略。

## 主流项目做法

### MCP 官方规范

MCP Resources 是 server 暴露上下文数据的协议能力。规范没有要求 resources 必须以 tool call 形式给模型使用，而是把如何选择、过滤、读取和纳入上下文交给 Host application。

这意味着比较正统的集成方式是：LangBot 作为 Host，在 pipeline、会话或消息层决定哪些 resources 进入模型上下文。

参考: https://modelcontextprotocol.io/specification/2025-06-18/server/resources

### VS Code Copilot

VS Code 把 MCP Resources 做成 chat context 的一部分。用户可以通过 `Add Context > MCP Resources` 或命令浏览 MCP resources，并把选中的资源附加到一次 chat request。

这是目前最值得 LangBot 参考的产品形态：资源不是模型工具，而是用户和 Host 可控的上下文附件。

参考: https://code.visualstudio.com/docs/agent-customization/mcp-servers

### Anthropic SDK

Anthropic 的 client-side MCP helpers 提供资源读取和转换能力，例如把 MCP resource 转为 Claude message content 或 file。也就是说，应用先读取 resource，再显式放进模型消息。

这同样是 application-owned context injection，而不是把 resource 伪装成模型工具。

参考: https://platform.claude.com/docs/en/agents-and-tools/mcp-connector

### LangChain MCP Adapters

LangChain 把 MCP Resources 更像 data loader / document input 来处理，可以把资源加载成 `Blob`，再进入 LangChain 的文档、检索或上下文处理链路。

这说明 Resources 很适合作为知识源、文档源或上下文源，而不只是即时工具调用。

参考: https://docs.langchain.com/oss/python/langchain/mcp

### OpenAI Agents SDK

OpenAI Agents SDK 主路径仍偏向 MCP tools，但底层 MCP server API 已经有 `list_resources`、`list_resource_templates`、`read_resource` 等能力。当前形态说明 resources 是 client 能力，但并未默认变成 agent-visible tools。

参考: https://openai.github.io/openai-agents-python/mcp/

### Cline

Cline 会拉取 MCP tools、resources、resourceTemplates、prompts，并通过类似 `access_mcp_resource` 的内置访问方式让模型读取资源。这个方向和 LangBot 当前 synthetic tools 比较接近。

这种模式适合让 Agent 自主探索，但更像 Host 自定义的模型访问协议，不应成为唯一集成路径。

参考: https://github.com/cline/cline/blob/main/src/services/mcp/McpHub.ts

## 建议架构方向

### 1. 保留探索型工具

保留当前两个 synthetic tools：

- `langbot_mcp_list_resources`
- `langbot_mcp_read_resource`

它们适合处理“用户没有显式选择资源，但 Agent 判断需要探索 MCP server 上下文”的场景。后续可以优化工具描述、返回格式、资源大小限制和错误信息。

### 2. 增加一等 Resource Context

新增一个 Host 层资源上下文概念，例如：

```text
PipelineResourceBinding
ConversationResourceAttachment
MessageResourceAttachment
```

Preproc 或独立的 `ResourceContextProvider` 在模型调用前读取这些资源，按 MIME 类型、大小、token budget 转为模型可消费的上下文。

### 3. 打通 UI 与 Agent 上下文

当前 MCP 详情页的 Resources tab 可以继续作为资源发现和预览入口。建议增加操作：

- 添加到本轮上下文
- 固定到当前 pipeline
- 固定到当前 bot / conversation
- 查看资源读取历史和错误

这样 UI 资源管理能力才能真正影响 Agent 行为。

### 4. 支持 resource templates

MCP resource templates 允许 server 暴露参数化资源，例如：

```text
repo://{owner}/{repo}/file/{path}
log://{service}/{date}
```

LangBot 后续应支持模板发现、参数填写、实例化和绑定。否则只能使用静态 resources，覆盖面会受限。

### 5. 增加资源处理策略

建议补齐：

- 文本资源 token budget 与截断策略。
- 大文件 chunk 与摘要策略。
- 图片/blob 的模型能力判断与 fallback。
- MIME 类型白名单与安全限制。
- 缓存与过期策略。
- `resources/listChanged` 或订阅更新。
- resource read trace，便于审计 Agent 读取了什么上下文。

## 推荐落地顺序

### Phase 1: 完成当前 PR 可用性

- 保留 synthetic tools。
- 明确文档说明当前 Agent 集成是 tool-mediated。
- 完善资源工具描述，降低模型误用概率。
- 给 read/list 增加大小限制和更清晰的 MIME 处理。
- 前端 Resources tab 与 Tools tab 分离，保持管理端清晰。

### Phase 2: 做 Host-owned context attachments

- 在 pipeline 或 conversation 层新增 resource attachment 配置。
- Preproc 读取已绑定 resources，注入模型上下文。
- UI 支持“添加到上下文 / 固定到 pipeline”。
- 记录每轮实际注入的 resource URI 和 token 消耗。

### Phase 3: 做完整 MCP Resources 能力

- 支持 resource templates。
- 支持资源订阅更新。
- 支持 chunk、summary、RAG 化接入。
- 为 DifyAgentRunner、LocalAgentRunner 等不同 runner 定义统一资源上下文接口。

## 最终建议

PR #2215 可以作为 MCP Resources 的第一阶段实现继续推进。它让 LangBot 快速拥有“资源发现、预览、按需读取”的闭环，也给 Agent 探索资源提供了可运行路径。

但在正式设计上，不建议把 “Resources == Tools” 固化为长期抽象。LangBot 更应该把 MCP Resources 定位为上下文来源，与 tools、prompts、knowledge base 并列：

```text
Tools      -> Agent 可以执行的动作
Resources  -> Host/用户/Agent 可以选择的上下文数据
Prompts    -> 可复用的任务模板
Knowledge  -> 可检索、可索引的长期知识
```

这样既尊重 MCP 协议语义，也能让 LangBot 在 Agent 工作流、企业知识接入和多 MCP server 管理上走得更稳。
