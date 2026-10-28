# 內建 Agent

## 概覽

內建 Agent，支援模型備援、工具呼叫與知識庫檢索。

## 套件資訊

- **運行器 ID**: `plugin:langbot-team/LocalAgent/default`
- **版本**: `0.1.0`
- **程式碼儲存庫**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/LocalAgent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/LocalAgent)

## 主要能力

- **已啟用**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`, `skill authoring`, `interrupt`, `steering`
- **未宣告**: 空

## 設定

| 欄位 | 類型 | 必填 | 預設值 |
| --- | --- | --- | --- |
| `model` | `model-fallback-selector` | 是 | `{fallbacks: [], primary: '', reasoning: {}}` |
| `timeout` | `integer` | 否 | `300` |
| `prompt` | `prompt-editor` | 是 | `[{content: You are a helpful assistant., role: system}]` |
| `remove-think` | `boolean` | 否 | false |
| `knowledge-bases` | `knowledge-base-multi-selector` | 否 | `[]` |
| `advanced-settings` | `boolean` | 否 | `false` |
| `date-grounding` | `boolean` | 否 | `true` |
| `retrieval-top-k` | `integer` | 否 | `5` |
| `rerank-model` | `rerank-model-selector` | 否 | 空 |
| `rerank-top-k` | `integer` | 否 | `5` |
| `max-tool-iterations` | `integer` | 否 | `100` |
| `tool-execution-mode` | `select` | 否 | `parallel` |
| `max-tool-result-chars` | `integer` | 否 | `20000` |
| `context-history-fetch-limit` | `integer` | 否 | `50` |
| `context-window-tokens` | `integer` | 否 | `200000` |
| `context-reserve-tokens` | `integer` | 否 | `16384` |
| `context-keep-recent-tokens` | `integer` | 否 | `20000` |
| `context-summary-tokens` | `integer` | 否 | `8000` |

## Host 權限

- **`models`**: `count_tokens`, `invoke`, `stream`, `rerank`
- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `list`, `retrieve`
- **`history`**: `page`

## 安裝與使用

1. 從 LangBot 外掛市場安裝此外掛。
2. 在 Pipeline 的運行器選擇器中選取下方運行器 ID。
3. 依照設定表填入連線資訊；密鑰欄位請使用管理介面保存。

## 安全與限制

- 運行器只能使用本次執行授權的 LangBot 資源。
- 外部服務的可用性、模型能力與速率限制由對應平台決定。
- 完整行為、進階設定與產品特定限制請參閱根目錄中文 README 或英文 README_en_US.md。

## Box

`box-enabled` 控制是否使用沙箱。`box-session-id-template` 預設 `{launcher_type}_{launcher_id}` 按聊天重用；`{global}` 在工作區共用。也支援 `{sender_id}`、`{bot_id}`、`{run_id}` 與請求變數。執行器選擇 Box 並匯入附件，成功完成後明確匯出本次執行 outbox 的檔案。
