# Dify Agent

`remove-think`（布林值，預設 `false`）隱藏 think 標籤中的推理內容，包括未結束的思考。`app-type` 也支援 `chatflow`。

## 概覽

將 Dify 應用程式作為 LangBot 運行器執行。

## 套件資訊

- **運行器 ID**: `plugin:langbot-team/DifyAgent/default`
- **版本**: `0.1.2`
- **程式碼儲存庫**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/dify-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/dify-agent)

## 主要能力

- **已啟用**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`
- **未宣告**: `interrupt`

## 設定

| 欄位 | 類型 | 必填 | 預設值 |
| --- | --- | --- | --- |
| `base-url` | `string` | 是 | `https://api.dify.ai/v1` |
| `advanced-settings` | `boolean` | 否 | false |
| `base-prompt` | `text` | 是 | `When the file content is readable, please read the content of this file. When the file is an image, describe the content of this image.` |
| `app-type` | `select` | 是 | `chat` |
| `api-key` | `secret` | 是 | 空 |
| `timeout` | `integer` | 否 | `30` |
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

### Provider identity compatibility (`user-id-source`)

Per-pipeline Runner parameter, not plugin-global configuration. `sender` remains the default.
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-session` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-session` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-session` uses `conversation.launcher_type` (`group`/`person`) plus `_` plus the exact `conversation.launcher_id`. Host must project the native Query.session launcher into those fields, including interaction/resume runs. Older Hosts that leave these fields empty must be upgraded.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.
