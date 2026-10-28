# WeKnora Agent

`agent-id` 在两种模式下均为可选项。未设置时，`chat` 使用 `builtin-quick-answer`，`agent` 使用 `builtin-smart-reasoning`；显式空值不发送智能体 ID。已保存的 ID 不会被替换。`knowledge-base-ids` 是两种模式均可使用的远端 WeKnora ID，不是 LangBot 知识库 UUID。

WeKnora Agent 将 WeKnora 智能体或知识库问答应用接入 LangBot 运行器。插件支持 Agent 智能推理模式和 Knowledge Base Chat 模式，并在 LangBot 会话状态中维护外部 WeKnora session。

## 运行器 ID

`plugin:langbot-team/WeKnoraAgent/default`

## 主要能力

- 支持 WeKnora Agent API。
- 支持 WeKnora 知识库 Chat API。
- 支持流式输出。
- 支持多个 WeKnora knowledge base ID。
- 支持 Agent 模式下的 Web Search 开关。
- 在 Host 会话状态中持久化 `external.session_id`。

## 配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `base-url` | `string` | 是 | `http://localhost:8080/api/v1` | WeKnora API 地址，需要包含 `/api/v1` |
| `api-key` | `secret` | 是 | 空 | WeKnora Settings 中生成的 API key |
| `app-type` | `select` | 是 | `agent` | `agent` 智能推理或 `chat` 知识库问答 |
| `agent-id` | `string` | 否 | `chat`: `builtin-quick-answer`; `agent`: `builtin-smart-reasoning` |
| `knowledge-base-ids` | `array[string]` | 否 | `[]` | Chat 模式使用的知识库 ID |
| `web-search-enabled` | `boolean` | 否 | `false` | Agent 模式是否启用网络搜索 |
| `advanced-settings` | `boolean` | 否 | `false` | 展开超时和回退提示词调优选项 |
| `timeout` | `integer` | 否 | `120` | 请求超时秒数 |
| `base-prompt` | `string` | 否 | `请回答用户的问题。` | 用户输入为空时使用的默认提示 |

## 模式说明

### Agent 模式

调用 `/agent-chat/{session_id}`，适合智能推理、数据分析和可选网络搜索。内置 Agent ID 包括 `builtin-quick-answer`、`builtin-smart-reasoning` 和 `builtin-data-analyst`，实际可用列表以 WeKnora 部署为准。

### Chat 模式

调用 `/knowledge-chat/{session_id}`，使用 `knowledge-base-ids` 指定一个或多个 WeKnora 知识库。空列表是否可用取决于 WeKnora 服务配置。

## 会话状态

首次运行创建外部 session，并通过 `state.updated` 保存为会话级 `external.session_id`。后续 LangBot 消息复用该 session，实现连续问答。session ID 不应放入静态 pipeline 配置。

## 限制与安全

- API key 使用密钥字段保存。
- 当前 runner 不声明 LangBot Host 知识库检索能力；配置的是 WeKnora 自身知识库。
- 当前不支持图片等多模态输入。
- Web Search 的可用性取决于 WeKnora Agent 与服务端配置。
- 远程 WeKnora 部署需要 LangBot 运行环境可访问其 API 地址。

## 开发检查

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check .
```
