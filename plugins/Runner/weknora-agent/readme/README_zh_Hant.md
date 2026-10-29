# WeKnora Agent

`agent-id` 在兩種模式下均為選填。未設定時，`chat` 使用 `builtin-quick-answer`，`agent` 使用 `builtin-smart-reasoning`；明確留空時不傳送智能體 ID。已儲存的 ID 不會被替換。`knowledge-base-ids` 是兩種模式均可使用的遠端 WeKnora ID，不是 LangBot 知識庫 UUID。

## 概覽

將 WeKnora 代理或知識庫聊天應用程式作為 LangBot 運行器執行。

## 套件資訊

- **運行器 ID**: `plugin:langbot-team/WeKnoraAgent/default`
- **版本**: `0.1.2`
- **程式碼儲存庫**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent)

## 主要能力

- **已啟用**: `streaming`
- **未宣告**: `tool calling`, `knowledge retrieval`, `multimodal input`, `interrupt`

## 設定

| 欄位 | 類型 | 必填 | 預設值 |
| --- | --- | --- | --- |
| `base-url` | `string` | 是 | `http://localhost:8080/api/v1` |
| `api-key` | `secret` | 是 | 空 |
| `app-type` | `select` | 是 | `agent` |
| `agent-id` | `string` | 否 | `chat`: `builtin-quick-answer`; `agent`: `builtin-smart-reasoning` |
| `knowledge-base-ids` | `array[string]` | 否 | `[]` |
| `web-search-enabled` | `boolean` | 否 | false |
| `advanced-settings` | `boolean` | 否 | false |
| `timeout` | `integer` | 否 | `120` |
| `base-prompt` | `string` | 否 | `请回答用户的问题。` |

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
