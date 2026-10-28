# n8n 工作流 Agent

[English](../README.md) · [日本語](README_ja_JP.md)

n8n 工作流 Agent 将 n8n Webhook 工作流接入 LangBot 运行器。插件把当前输入和会话标识发送到 Webhook，支持 Basic、JWT 和自定义 Header 鉴权，并可向工作流注入短期 LangBot 资产 token。

## 运行器 ID

`plugin:langbot-team/N8nAgent/default`

## 主要能力

- 支持任意可返回文本或 JSON 的 n8n Webhook。
- 支持无鉴权、Basic Auth、JWT 和自定义 Header。
- 支持流式或普通响应解析。
- 为外部工作流生成并持久化独立 conversation/session ID。
- 可让 n8n AI Agent 通过 MCP Client Tool 访问 LangBot 授权资源。

## 配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `webhook-url` | `string` | 是 | 空 | n8n Webhook URL |
| `auth-type` | `select` | 是 | `none` | `none`、`basic`、`jwt` 或 `header` |
| `basic-username` | `string` | 否 | 空 | Basic Auth 用户名 |
| `basic-password` | `secret` | 否 | 空 | Basic Auth 密码 |
| `basic-encoding` | `select` | 否 | `utf-8` | 原生非 ASCII Basic 凭据使用 `latin1`；`utf-8` 保持插件默认值 |
| `jwt-secret` | `secret` | 否 | 空 | JWT 签名密钥 |
| `jwt-algorithm` | `string` | 否 | `HS256` | JWT 算法 |
| `header-name` | `string` | 否 | 空 | 自定义鉴权 Header 名称 |
| `header-value` | `secret` | 否 | 空 | 自定义鉴权 Header 值 |
| `advanced-settings` | `boolean` | 否 | `false` | 展开超时和响应映射调优选项 |
| `timeout` | `integer` | 否 | `120` | Webhook 请求超时秒数 |
| `output-key` | `string` | 否 | `response` | JSON 响应中的输出字段 |
| `response-handling` | `select` | 否 | `reply` | `reply` 转发 HTTP 200 输出；`ignore` 接受任意 HTTP 2xx 且不读取、转发正文 |
| `langbot-assets-enabled` | `boolean` | 否 | `false` | 是否启用 LangBot 资产回调 |
| `langbot-assets-gateway-host` | `string` | 否 | `0.0.0.0` | Asset Gateway 监听地址 |
| `langbot-assets-gateway-port` | `integer` | 否 | `8765` | 网关端口 |
| `langbot-assets-gateway-request-timeout` | `integer` | 否 | `60` | 网关调用超时 |
| `langbot-assets-token-ttl` | `integer` | 否 | `3600` | 运行 token 有效期 |
| `langbot-assets-input-name` | `string` | 否 | `langbot_asset_run_token` | Webhook payload 中的 token 字段名 |

## 响应模式与旧版迁移

`reply` 为默认模式，只接受 HTTP 200。`ignore` 等待响应头后立即关闭正文，接受所有
HTTP 2xx，不生成聊天回复，也不触发空回复错误。请将 n8n Webhook 设为 **立即响应
（Respond Immediately）**；这不是后台发出即返回，非 2xx 和超时仍会失败。
`timeout` 默认 120 秒，限制整个请求；回复正文上限为 1,048,576 个字符。
资产 token 会在请求返回时注销，异步工作流不能继续使用本次运行的资产权限。

原 `ai.n8n-service-api` 的 11 个字段保持名称，移入
`ai.runner_config["plugin:langbot-team/N8nAgent/default"]`。新默认 Webhook URL 为空，
必须明确配置；`langbot-assets-enabled` 默认关闭，不因迁移自动授权资源访问。
普通 JSON 没有 `output-key` 时返回整个对象；回复模式的空输出仍作为错误处理。
错误正文及异常详情不回显，以免泄露凭据。

会话 ID 的持久化与原生运行器不同，`user_id` 使用 SDK actor 而非旧 launcher/chat；
这不是已证明的安全改进。迁移须明确处理旧远端身份与会话状态，或批准重置，不能承诺
自动续接旧会话。业务参数由 `adapter.extra.params` 提供，不能覆盖保留的身份字段；
`msg_create_time` 默认空字符串且保留显式零值。默认不自动跟随 HTTP 重定向。
不恢复 local-agent 历史轮数设置，n8n 原生请求本身仅发送当前输入。

## Webhook Payload 与状态

runner 会为外部系统维护独立的 conversation ID 和 session ID，不直接复用 LangBot 内部 ID。新生成的 ID 通过 Host 会话状态持久化，后续请求保持一致。Webhook 可以使用这些字段关联工作流状态。

## LangBot 资产回调

n8n 工作流应包含：

1. Webhook Trigger，并在最后一个节点完成后返回响应。
2. 使用 HTTP Streamable transport 的 MCP Client Tool，地址指向 Asset Gateway `/mcp`。
3. 连接 MCP Client Tool 的 AI Agent。
4. prompt 中从 Webhook payload 读取 token，并在每次 LangBot MCP 调用中作为 `run_token` 传入。

因为 n8n credentials 是静态的，不适合携带每次运行变化的 Header，所以推荐使用工具参数传递 `run_token`。

## 限制与安全

- n8n Cloud 需要可公开访问的 HTTPS Asset Gateway。
- 工作流必须在 Webhook 请求结束前完成资产回调。
- Basic 密码、JWT secret 和自定义 Header 值使用密钥字段。
- JSON 对象不存在 `output-key` 时会回传整个对象；该字段为空时，回复模式报告空回复错误。
- token 在当前运行结束后立即注销。

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
`legacy-session` uses `conversation.launcher_type` (`group`/`person`) plus `_` plus the exact `conversation.launcher_id`. Host must project the native Query.session launcher into those fields, including interaction/resume runs. Older Hosts that leave these fields empty must be upgraded.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.
