# DeerFlow Agent

凭据和服务端标识是不透明值：`api-key`、`auth-header`、`assistant-id`、`model-name` 保留显式空白和空值。非空 `auth-header` 优先于 Bearer `api-key`。字符串、布尔或整数类型错误会返回仅含字段名的配置错误，不会静默替换。

DeerFlow Agent 将 DeerFlow LangGraph HTTP API 接入 LangBot 运行器。插件负责创建或恢复 LangGraph thread、发送运行请求、解析 SSE 事件，并把结果转换为 LangBot 流式消息和状态更新。

## 运行器 ID

`plugin:langbot-team/DeerFlowAgent/default`

## 主要能力

- 支持创建和复用 DeerFlow thread。
- 支持 `values`、`messages-tuple`、`messages`、`message`、`custom`、`error` 和 `end` SSE 事件。
- 支持图片 URL 与 data URL 多模态输入。
- 支持 thinking、plan mode 和并行 subagent 开关。
- 在 Host 会话状态中保存 `external.thread_id`。

## 配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `api-base` | `string` | 是 | `http://127.0.0.1:2026` | DeerFlow API 地址 |
| `api-key` | `secret` | 否 | 空 | 可选 API key |
| `auth-header` | `secret` | 否 | 空 | 完整 Authorization 头，设置后优先于 `api-key` |
| `assistant-id` | `string` | 是 | `lead_agent` | Assistant 或 graph ID |
| `advanced-settings` | `boolean` | 否 | `false` | 展开模型、超时和递归调优选项 |
| `model-name` | `string` | 否 | 空 | 可选模型覆盖 |
| `thinking-enabled` | `boolean` | 否 | `false` | 是否启用 thinking |
| `plan-mode` | `boolean` | 否 | `false` | 是否启用 plan mode |
| `subagent-enabled` | `boolean` | 否 | `false` | 是否启用并行 subagent |
| `max-concurrent-subagents` | `integer` | 否 | `3` | 最大并发 subagent 数 |
| `timeout` | `integer` | 否 | `300` | 请求超时秒数 |
| `recursion-limit` | `integer` | 否 | `1000` | 单次 LangGraph 运行递归上限 |

## 会话状态

首次运行创建 DeerFlow thread，成功后通过 `state.updated` 把 thread ID 写入 LangBot 会话状态。后续运行从状态中读取该 ID，实现跨消息连续对话。静态 pipeline 配置中不应保存 thread ID。

## SSE 处理

runner 会容忍心跳、空行和多种 DeerFlow 消息事件结构，对文本增量进行去重，并把明确的 error 事件转换为 `run.failed`。若流结束但没有有效文本，会返回可诊断错误而不是静默完成。

## 限制与安全

- `api-key` 和完整 Authorization header 均使用密钥字段。
- 图片能否被最终模型处理取决于 DeerFlow graph 和模型能力。
- subagent 并发数应结合 DeerFlow 服务资源设置。
- recursion limit 设置过高可能导致长时间运行和资源消耗。

## 开发检查

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check .
```
