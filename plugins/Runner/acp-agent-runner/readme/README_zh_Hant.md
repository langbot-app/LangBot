# ACP Runner

## 概覽

將任何相容 Agent Client Protocol 的程式設計代理作為 LangBot 運行器執行。

## 套件資訊

- **運行器 ID**: `plugin:langbot-team/ACPAgentRunner/default`
- **版本**: `0.1.4`
- **程式碼儲存庫**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/acp-agent-runner](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/acp-agent-runner)

## 主要能力

- **已啟用**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`, `steering`
- **未宣告**: `interrupt`

## 設定

| 欄位 | 類型 | 必填 | 預設值 |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | 否 | false |
| `daemon-host` | `string` | 否 | `127.0.0.1` |
| `daemon-port` | `integer` | 否 | `8766` |
| `daemon-token` | `secret` | 否 | 空 |
| `provider` | `select` | 是 | `claude-code` |
| `location` | `select` | 是 | `local` |
| `workspace` | `string` | 否 | 空 |
| `advanced-settings` | `boolean` | 否 | false |
| `ssh-target` | `string` | 否 | 空 |
| `daemon-id` | `string` | 否 | 空 |
| `daemon-connect-timeout` | `integer` | 否 | `30` |
| `ssh-port` | `integer` | 否 | `22` |
| `ssh-identity-file` | `string` | 否 | 空 |
| `acp-command` | `string` | 否 | 空 |
| `knowledge-bases` | `knowledge-base-multi-selector` | 否 | `[]` |
| `langbot-assets-enabled` | `boolean` | 否 | true |
| `langbot-assets-mode` | `select` | 否 | `auto` |
| `langbot-assets-gateway-host` | `string` | 否 | `127.0.0.1` |
| `langbot-assets-gateway-port` | `integer` | 否 | `0` |
| `langbot-assets-gateway-public-url` | `string` | 否 | 空 |
| `langbot-assets-token-ttl` | `integer` | 否 | `3600` |
| `timeout` | `integer` | 否 | `300` |
| `reuse-session` | `boolean` | 否 | true |
| `env-json` | `text` | 否 | 空 |
| `ssh-connect-timeout` | `integer` | 否 | `10` |
| `ssh-extra-options` | `string` | 否 | 空 |
| `startup-timeout` | `integer` | 否 | `30` |
| `initialize-timeout` | `integer` | 否 | `120` |
| `create-session-if-missing` | `boolean` | 否 | true |
| `streaming` | `boolean` | 否 | true |
| `append-run-scope-prompt` | `boolean` | 否 | true |
| `mcp-servers-json` | `text` | 否 | 空 |

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


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
