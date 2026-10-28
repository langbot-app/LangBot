# Coze Agent

`remove-think` 为严格布尔值（默认 `false`）。设为 `true` 可隐藏推理字段和 `<think>` 块，支持跨流式分块边界，保留正文及工具内容。

Coze Agent 将 Coze（扣子）机器人接入 LangBot 运行器，负责把 LangBot 输入转换为 Coze Chat API 请求，并将 Coze 的流式回复、会话状态和错误事件转换为 Runner Protocol v1 结果。

## 运行器 ID

`plugin:langbot-team/CozeAgent/default`

## 主要能力

- 支持 Coze 中国站和全球站 API。
- 支持流式回复。
- 支持文本和图片输入。
- 支持在 LangBot 会话状态中持久化 Coze conversation ID。
- 可自动保存 Coze 对话历史。
- 可通过 SDK Asset Gateway 向 Coze Agent 暴露本次运行授权的 LangBot 工具、知识库和历史。

## 配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `api-key` | `secret` | 是 | 空 | Coze Personal Access Token 或 API Token |
| `bot-id` | `string` | 是 | 空 | Coze Bot ID |
| `api-base` | `string` | 是 | `https://api.coze.cn` | 中国站或全球站 API 地址 |
| `advanced-settings` | `boolean` | 否 | `false` | 展开历史和超时调优选项 |
| `auto-save-history` | `boolean` | 否 | `true` | 是否让 Coze 保存会话历史 |
| `timeout` | `number` | 否 | `120` | 请求超时秒数 |
| `langbot-assets-enabled` | `boolean` | 否 | `false` | 是否启用 LangBot 资产回调 |
| `langbot-assets-gateway-host` | `string` | 否 | `0.0.0.0` | Asset Gateway 监听地址 |
| `langbot-assets-gateway-port` | `integer` | 否 | `8765` | Asset Gateway 端口 |
| `langbot-assets-gateway-request-timeout` | `integer` | 否 | `60` | 网关工具调用超时 |
| `langbot-assets-token-ttl` | `integer` | 否 | `3600` | 运行令牌有效期秒数 |
| `langbot-assets-input-name` | `string` | 否 | `langbot_asset_run_token` | 注入 Coze `custom_variables` 的字段名 |

## LangBot 资产回调

启用后，runner 会为每次运行生成短期 token，并通过 Coze `custom_variables` 发送给 Bot。Coze Bot 需要提前配置可访问 Asset Gateway `/mcp` 的 MCP 工具，并在每次工具调用中把该变量作为 `run_token` 传入。

远程 Coze 服务无法访问 `localhost`。生产环境应使用稳定的 HTTPS 域名反向代理网关；临时 tunnel 只适合测试。运行结束后 token 会立即注销，Coze 工具调用必须在当前 Chat API 请求生命周期内完成。

## 状态与安全

外部 conversation ID 存放在 Host 管理的会话状态中，不写入静态配置。API key 使用密钥输入框保存。Asset Gateway 只暴露当前运行授权的事件、历史、知识库与工具能力，不能跨运行访问其他资源。

## 开发检查

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check .
```

### Provider identity compatibility (`user-id-source`)

Per-pipeline Runner parameter, not plugin-global configuration. `sender` remains the default.
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-session` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-session` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-session` uses `conversation.launcher_type` (`group`/`person`) plus `_` plus the exact `conversation.launcher_id`. Host must project the Query launcher for Coze into those fields, including interaction/resume runs. Older Hosts that leave these fields empty must be upgraded.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.
