# Tbox Agent

`remove-think` 为严格布尔值（默认 `false`）。设为 `true` 可隐藏推理字段和 `<think>` 块，支持跨流式分块边界，保留正文及工具内容。

Tbox Agent 将蚂蚁百宝箱应用接入 LangBot 运行器。插件调用 Tbox SDK，把 LangBot 文本和图片输入发送给目标应用，并将流式结果转换为 Runner Protocol v1 消息。

它适合已经在百宝箱中完成应用编排、希望通过 LangBot 统一接入聊天渠道的场景。

## 运行器 ID

`plugin:langbot-team/TboxAgent/default`

## 主要能力

- 支持蚂蚁百宝箱应用调用。
- 支持流式输出。
- 支持文本和图片多模态输入。
- 支持请求超时和错误映射。
- 在 Host 管理的插件存储范围内运行。

## 配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `api-key` | `secret` | 是 | 空 | Tbox API key |
| `app-id` | `string` | 是 | 空 | 百宝箱应用 ID |
| `timeout` | `number` | 否 | `120` | 请求超时秒数 |

## 多模态输入

runner 会把 LangBot 输入中的图片 URL 或 base64 图片转换为 Tbox SDK 支持的消息结构。最终能否正确识别图片取决于目标百宝箱应用及其模型能力。无法转换的附件会以可诊断方式处理，不会直接暴露运行机器文件路径。

## LangBot 资产回调限制

当前插件不支持通过 SDK Asset Gateway 让 Tbox 反向调用 LangBot 工具。原因是：

- Tbox 外部 MCP 插件目前要求旧版 HTTP+SSE 传输。
- LangBot SDK Asset Gateway 实现的是 Streamable HTTP `POST /mcp`。
- Tbox 的 MCP URL 是静态配置，也没有已确认的每次运行 token 注入通道。

因此两端传输和授权模型不兼容。未来需要 Asset Gateway 增加 SSE endpoint，或 Tbox 支持 Streamable HTTP 和动态运行 token 后，才能安全接入。

## 安全说明

- API key 使用密钥字段保存。
- 不要在 prompt、日志或普通字符串字段中写入长期凭据。
- `timeout` 应根据应用复杂度设置，避免长任务过早终止。
- 插件不会把未授权的 LangBot 工具或 Host 内部 API 暴露给 Tbox。

## 开发检查

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check .
```

### Provider identity compatibility (`user-id-source`)

Per-pipeline Runner parameter, not plugin-global configuration. `sender` remains the default.
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-bot` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-bot` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-bot` uses `conversation.bot_id` (or Host runtime `bot_id` when there is no conversation), exactly, without a prefix.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.
