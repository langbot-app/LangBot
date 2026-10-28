# Claude Code Agent

## 概覽

將 Claude Code CLI 作為 LangBot 運行器執行。

## 套件資訊

- **運行器 ID**: `plugin:langbot-team/ClaudeCodeAgent/default`
- **版本**: `0.1.3`
- **程式碼儲存庫**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/claude-code-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/claude-code-agent)

## 主要能力

- **已啟用**: `streaming`, `tool calling`, `knowledge retrieval`, `steering`
- **未宣告**: `multimodal input`, `interrupt`

## 設定

| 欄位 | 類型 | 必填 | 預設值 |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | 否 | false |
| `daemon-host` | `string` | 否 | `127.0.0.1` |
| `daemon-port` | `integer` | 否 | `8767` |
| `daemon-token` | `secret` | 否 | 空 |
| `location` | `select` | 是 | `local` |
| `workspace` | `string` | 否 | 空 |
| `advanced-settings` | `boolean` | 否 | false |
| `command` | `string` | 否 | `claude` |
| `args-json` | `string` | 否 | `[]` |
| `env-json` | `string` | 否 | `{}` |
| `ssh-target` | `string` | 否 | 空 |
| `ssh-port` | `integer` | 否 | `22` |
| `daemon-id` | `string` | 否 | 空 |
| `timeout` | `integer` | 否 | `300` |
| `streaming` | `boolean` | 否 | true |
| `reuse-session` | `boolean` | 否 | true |
| `dangerously-skip-permissions` | `boolean` | 否 | true |
| `knowledge-bases` | `knowledge-base-multi-selector` | 否 | `[]` |
| `langbot-assets-enabled` | `boolean` | 否 | true |
| `mcp-bridge-transport` | `select` | 否 | `auto` |
| `mcp-servers-json` | `string` | 否 | `[]` |

## Host 權限

- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `retrieve`
- **`history`**: `page`

## 安裝與使用

1. 從 LangBot 外掛市場安裝此外掛。
2. 在 Pipeline 的運行器選擇器中選取下方運行器 ID。
3. 依照設定表填入連線資訊；密鑰欄位請使用管理介面保存。

## 安全與限制

- 運行器只能使用本次執行授權的 LangBot 資源。
- LangBot 尚未提供互動式審批流程，因此 Claude Code 預設使用 `--dangerously-skip-permissions`。請只在可信工作區及受限制的系統帳號下使用；設為 false 可恢復 Claude Code 的正常權限檢查。
- 外部服務的可用性、模型能力與速率限制由對應平台決定。
- 完整行為、進階設定與產品特定限制請參閱根目錄中文 README 或英文 README_en_US.md。


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
