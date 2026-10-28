# DashScope Agent

`remove-think` 为严格布尔值（默认 `false`）。设为 `true` 可隐藏推理字段和 `<think>` 块，支持跨流式分块边界，保留正文及工具内容。

DashScope Agent 将阿里云百炼 Agent 或 Workflow 应用接入 LangBot 运行器。插件调用 DashScope Application API，并把流式文本、引用信息和错误转换为 Runner Protocol v1 事件。

## 运行器 ID

`plugin:langbot-team/DashScopeAgent/default`

## 主要能力

- 支持百炼 Agent 与 Workflow 两种应用类型。
- 支持流式响应。
- 支持引用信息拼接。
- 可把 LangBot 本次运行的短期资产 token 注入 `biz_params`。
- 可通过百炼应用配置的外部 MCP 服务访问 LangBot 工具、知识库和历史。

## 配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `app-type` | `select` | 是 | `agent` | `agent` 或 `workflow` |
| `api-key` | `secret` | 是 | 空 | DashScope API Key |
| `app-id` | `string` | 是 | 空 | 百炼应用 ID |
| `advanced-settings` | `boolean` | 否 | `false` | 展开引用格式和超时调优选项 |
| `references_quote` | `string` | 否 | `参考资料来自:` | 引用信息前缀 |
| `timeout` | `number` | 否 | `120` | 请求超时秒数 |
| `langbot-assets-enabled` | `boolean` | 否 | `false` | 是否启用 LangBot 资产回调 |
| `langbot-assets-gateway-host` | `string` | 否 | `0.0.0.0` | Asset Gateway 监听地址 |
| `langbot-assets-gateway-port` | `integer` | 否 | `8765` | Asset Gateway 端口 |
| `langbot-assets-gateway-request-timeout` | `integer` | 否 | `60` | 网关工具调用超时 |
| `langbot-assets-token-ttl` | `integer` | 否 | `3600` | 运行 token 有效期 |
| `langbot-assets-input-name` | `string` | 否 | `langbot_asset_run_token` | `biz_params` 中的 token 字段名 |

## LangBot 资产回调

启用后，runner 将短期 token 放入 DashScope 请求的 `biz_params`。百炼应用需要挂载一个指向 Asset Gateway `/mcp` 的外部 MCP 服务，并确保应用 prompt 或工具参数把 `biz_params` 中的值作为 `run_token` 传给 LangBot MCP 工具。

发布前应在百炼控制台验证 MCP `initialize`、`tools/list` 和真实工具调用。若百炼应用未把 `biz_params` 转发到工具参数，LangBot 侧会拒绝无 token 的调用。

## 限制与安全

- API key 使用密钥字段保存。
- 远程百炼服务需要可公开访问的 HTTPS 网关。
- token 只在当前运行有效，不能作为长期凭据。
- 多模态能力取决于百炼应用和模型配置；当前 runner 主要面向文本应用。

## 开发检查

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check .
```
