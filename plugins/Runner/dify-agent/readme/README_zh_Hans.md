# Dify Agent

`remove-think`（布尔值，默认 `false`）隐藏 think 标签中的推理内容，包括未结束的思考。`app-type` 也支持 `chatflow`。

Dify Agent 将 Dify 的 Chat、Agent、Chatflow 或 Workflow 应用接入 LangBot 运行器。插件负责组装输入、管理 Dify conversation ID、解析阻塞或流式响应，并可通过 SDK Asset Gateway 让 Dify Agent 在当前运行范围内调用 LangBot 工具、知识库和历史。

## 运行器 ID

`plugin:langbot-team/DifyAgent/default`

## 主要能力

- 支持 Dify Chat/Chatflow、Agent 和 Workflow API。
- 支持流式回复。
- 支持文本与图片输入映射。
- 在 Host 会话状态中保存合法的 Dify conversation ID。
- 可向 Dify inputs 注入短期 LangBot 资产 token。
- 可通过 Dify MCP 工具回调 LangBot 的当前事件、历史、知识库和工具。

## 配置

配置必须保持静态，不要把外部 conversation ID 写进 pipeline 配置。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `base-url` | `string` | 是 | `https://api.dify.ai/v1` | Dify Service API 地址，通常保留 `/v1` |
| `advanced-settings` | `boolean` | 否 | `false` | 展开提示词和超时调优选项 |
| `base-prompt` | `text` | 是 | 文件处理提示词 | 加在 LangBot 输入前的指令 |
| `app-type` | `select` | 是 | `chat` | `chat`、`agent` 或 `workflow` |
| `api-key` | `secret` | 是 | 空 | 目标 Dify 应用的 Service API key |
| `timeout` | `integer` | 否 | `30` | 请求超时秒数；长工作流建议至少 `120` |
| `langbot-assets-enabled` | `boolean` | 否 | `false` | 是否启用 LangBot 资产回调 |
| `langbot-assets-gateway-host` | `string` | 否 | `0.0.0.0` | Asset Gateway 监听地址 |
| `langbot-assets-gateway-port` | `integer` | 否 | `8765` | Asset Gateway 端口 |
| `langbot-assets-gateway-request-timeout` | `integer` | 否 | `60` | 单次网关工具调用超时 |
| `langbot-assets-token-ttl` | `integer` | 否 | `3600` | 运行 token 有效期秒数 |
| `langbot-assets-input-name` | `string` | 否 | `langbot_asset_run_token` | 接收 token 的 Dify input 名称 |

## 会话状态

runner 从 `ctx.state.conversation["external.conversation_id"]` 读取 Dify conversation ID。只有合法的 Dify UUID 才会发送给 Dify；LangBot 自己的 conversation ID 不会直接复用，因为 Dify 会拒绝非 UUID 值。

Dify 返回新 conversation ID 后，runner 通过会话级 `state.updated` 交给 Host 持久化，下一次运行自动恢复。

## LangBot Asset Gateway

启用资产回调时，runner 为当前运行注册短期 token，并写入名为 `langbot-assets-input-name` 的 Dify input。Dify Agent 需要提前配置指向网关 `/mcp` 的 MCP provider，并在每次 LangBot MCP 工具调用中把该 input 值作为 `run_token` 参数。

网关提供的工具包括当前事件、历史分页、知识库检索、工具详情和工具调用。具体可见资源仍由 LangBot 当前运行的授权策略决定。

### Dify Cloud 配置要点

1. 在 Dify Tools 中创建 Streamable HTTP MCP provider。
2. URL 指向可公开访问的 Asset Gateway `/mcp`。
3. 在目标 Agent 应用中挂载 LangBot MCP 工具。
4. 新增与 `langbot-assets-input-name` 同名的文本 input。
5. 在 prompt 中要求每次工具调用传入该 input 作为 `run_token`。
6. 使用支持工具调用且兼容 Dify 工具消息格式的模型。

## 限制与安全

- Dify Cloud 无法访问 `localhost` 或私网地址，生产环境需要稳定 HTTPS 域名。
- token 在运行结束后注销，异步延迟任务不能继续使用。
- Dify Workflow 必须把目标输出放在可解析字段中。
- API key 使用密钥输入框，且必须是应用 Service API key，不是控制台登录 token。
- Asset Gateway 只暴露当前运行授权资源，不能跨会话复用 token。

## 验证建议

使用 LangBot Debug Chat 发起真实运行，让 Dify Agent 先调用 `langbot_list_assets`，成功后返回固定标记。不要只在 Dify Cloud Preview 中验证，因为 Preview 不会自动收到 LangBot 生成的实时 token。

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
