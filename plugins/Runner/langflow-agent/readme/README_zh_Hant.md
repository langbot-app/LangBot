# Langflow Agent

## 概覽

將 Langflow 流程作為 LangBot 運行器執行。

## 套件資訊

- **運行器 ID**: `plugin:langbot-team/LangflowAgent/default`
- **版本**: `0.1.2`
- **程式碼儲存庫**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/langflow-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/langflow-agent)

## 主要能力

- **已啟用**: `streaming`, `tool calling`, `knowledge retrieval`
- **未宣告**: `multimodal input`, `interrupt`

## 設定

| 欄位 | 類型 | 必填 | 預設值 |
| --- | --- | --- | --- |
| `base-url` | `string` | 是 | `http://localhost:7860` |
| `api-key` | `secret` | 是 | 空 |
| `flow-id` | `string` | 是 | 空 |
| `advanced-settings` | `boolean` | 否 | false |
| `input-type` | `string` | 否 | `chat` |
| `output-type` | `string` | 否 | `chat` |
| `tweaks` | `json` | 否 | `{}` |
| `langbot-assets-enabled` | `boolean` | 否 | false |
| `langbot-assets-gateway-host` | `string` | 否 | `0.0.0.0` |
| `langbot-assets-gateway-port` | `integer` | 否 | `8765` |
| `langbot-assets-gateway-request-timeout` | `integer` | 否 | `60` |
| `langbot-assets-token-ttl` | `integer` | 否 | `3600` |
| `langbot-assets-input-name` | `string` | 否 | `langbot_asset_run_token` |

## Host 權限

- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `retrieve`
- **`history`**: `page`
- **`storage`**: `plugin`

## 安裝與使用

1. 從 LangBot 外掛市場安裝此外掛。
2. 在 Pipeline 的運行器選擇器中選取下方運行器 ID。
3. 依照設定表填入連線資訊；密鑰欄位請使用管理介面保存。

## 安全與限制

- 運行器只能使用本次執行授權的 LangBot 資源。
- 外部服務的可用性、模型能力與速率限制由對應平台決定。
- 完整行為、進階設定與產品特定限制請參閱根目錄中文 README 或英文 README_en_US.md。
