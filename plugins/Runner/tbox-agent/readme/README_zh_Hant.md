# Tbox Agent

`remove-think` 為嚴格布林值（預設 `false`）。設為 `true` 可隱藏推理欄位和 `<think>` 區塊，支援跨串流分塊邊界，保留正文及工具內容。

## 概覽

將螞蟻 Tbox 應用程式作為 LangBot 運行器執行。

## 套件資訊

- **運行器 ID**: `plugin:langbot-team/TboxAgent/default`
- **版本**: `0.1.0`
- **程式碼儲存庫**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/tbox-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/tbox-agent)

## 主要能力

- **已啟用**: `streaming`, `multimodal input`
- **未宣告**: `tool calling`, `knowledge retrieval`, `interrupt`

## 設定

| 欄位 | 類型 | 必填 | 預設值 |
| --- | --- | --- | --- |
| `api-key` | `secret` | 是 | 空 |
| `app-id` | `string` | 是 | 空 |
| `timeout` | `number` | 否 | `120` |

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

### Provider identity compatibility (`user-id-source`)

Per-pipeline Runner parameter, not plugin-global configuration. `sender` remains the default.
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-bot` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-bot` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-bot` uses `conversation.bot_id` (or Host runtime `bot_id` when there is no conversation), exactly, without a prefix.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.
