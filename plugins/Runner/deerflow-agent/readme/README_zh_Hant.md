# DeerFlow Agent

## 概覽

將 DeerFlow LangGraph 代理作為 LangBot 運行器執行。

## 套件資訊

- **運行器 ID**: `plugin:langbot-team/DeerFlowAgent/default`
- **版本**: `0.1.2`
- **程式碼儲存庫**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent)

## 主要能力

- **已啟用**: `streaming`, `multimodal input`
- **未宣告**: `tool calling`, `knowledge retrieval`, `interrupt`

## 設定

| 欄位 | 類型 | 必填 | 預設值 |
| --- | --- | --- | --- |
| `api-base` | `string` | 是 | `http://127.0.0.1:2026` |
| `api-key` | `secret` | 否 | 空 |
| `auth-header` | `secret` | 否 | 空 |
| `assistant-id` | `string` | 是 | `lead_agent` |
| `advanced-settings` | `boolean` | 否 | false |
| `model-name` | `string` | 否 | 空 |
| `thinking-enabled` | `boolean` | 否 | false |
| `plan-mode` | `boolean` | 否 | false |
| `subagent-enabled` | `boolean` | 否 | false |
| `max-concurrent-subagents` | `integer` | 否 | `3` |
| `timeout` | `integer` | 否 | `300` |
| `recursion-limit` | `integer` | 否 | `1000` |

## Host 權限

- **`storage`**: `plugin`

## 安裝與使用

1. 從 LangBot 外掛市場安裝此外掛。
2. 在 Pipeline 的運行器選擇器中選取下方運行器 ID。
3. 依照設定表填入連線資訊；密鑰欄位請使用管理介面保存。

## 安全與限制

- 運行器只能使用本次執行授權的 LangBot 資源。
- 外部服務的可用性、模型能力與速率限制由對應平台決定。
- 完整行為、進階設定與產品特定限制請參閱根目錄中文 README 或英文 README_en_US.md。
