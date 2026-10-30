# Langflow Agent

Tweaks 必须是 JSON 对象（JSON 字符串或对象）。缺失、null、空字符串或仅空白表示无覆盖；非法 JSON 和其他值会返回 `langflow.config_invalid`，不会记录参数内容。仅空白可用是插件的便利行为，旧原生运行器不接受。`external.session_id` 保持跨轮会话历史，迁移不会恢复旧的每次新建会话行为。

Langflow Agent 将 Langflow flow 接入 LangBot 运行器。插件调用 Langflow Run API，把 LangBot 输入映射到 flow，并从 Langflow 响应中提取最终消息。启用 Asset Gateway 后，还可以向 flow 注入当前运行的短期 LangBot 资产 token。

## 运行器 ID

`plugin:langbot-team/LangflowAgent/default`

## 主要能力

- 支持 Langflow 本地或远程部署。
- 支持 flow input/output 类型和 tweaks 配置。
- 支持流式结果适配。
- 可通过 tweak 向指定组件注入 LangBot 运行 token。
- 可让 flow 中的 Agent 通过 MCP 工具访问 LangBot 授权资源。

## 配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `base-url` | `string` | 是 | `http://localhost:7860` | Langflow 服务地址 |
| `api-key` | `secret` | 是 | 空 | Langflow API key |
| `flow-id` | `string` | 是 | 空 | 目标 flow ID |
| `advanced-settings` | `boolean` | 否 | `false` | 展开输入、输出和流程 tweak 调优选项 |
| `input-type` | `string` | 否 | `chat` | Langflow input type |
| `output-type` | `string` | 否 | `chat` | Langflow output type |
| `tweaks` | `json` | 否 | `{}` | 发送给 flow 的 tweaks JSON |
| `langbot-assets-enabled` | `boolean` | 否 | `false` | 是否启用 LangBot 资产回调 |
| `langbot-assets-gateway-host` | `string` | 否 | `0.0.0.0` | Asset Gateway 监听地址 |
| `langbot-assets-gateway-port` | `integer` | 否 | `8765` | 网关端口 |
| `langbot-assets-gateway-request-timeout` | `integer` | 否 | `60` | 网关调用超时 |
| `langbot-assets-token-ttl` | `integer` | 否 | `3600` | 运行 token 有效期 |
| `langbot-assets-input-name` | `string` | 否 | `langbot_asset_run_token` | 接收 token 的 flow 组件名称或 ID |

## LangBot 资产回调

启用后，runner 会修改本次请求的 tweaks，把短期 token 写入 `langbot-assets-input-name` 对应组件的 `input_value`。flow 需要包含：

1. 一个名称或 ID 与配置相同的 Text Input 组件。
2. 一个使用 Streamable HTTP、指向 Asset Gateway `/mcp` 的 MCP Tools 组件。
3. 一个连接 MCP Tools 的 Agent 组件。
4. 明确要求 Agent 在每次 LangBot 工具调用中传递 `run_token` 的 prompt。

## 限制与安全

- 远程 Langflow 无法访问本机 `localhost` 时，需要公开 HTTPS 网关。
- flow 中不存在目标 token 组件时，tweak 注入不会生效。
- token 只在当前 flow 请求期间有效。
- `tweaks` 必须是合法 JSON；错误组件 ID 会由 Langflow 返回诊断信息。
- API key 使用密钥字段保存。

## 开发检查

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check .
```
