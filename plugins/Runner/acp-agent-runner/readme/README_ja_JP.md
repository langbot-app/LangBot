# ACP Runner

## 概要

Agent Client Protocol 対応のコーディングエージェントを LangBot Runner として実行します。

## パッケージ情報

- **Runner ID**: `plugin:langbot-team/ACPAgentRunner/default`
- **バージョン**: `0.1.4`
- **リポジトリ**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/acp-agent-runner](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/acp-agent-runner)

## 主な機能

- **有効**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`, `steering`
- **未宣言**: `interrupt`

## 設定

| フィールド | 型 | 必須 | 既定値 |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | いいえ | false |
| `daemon-host` | `string` | いいえ | `127.0.0.1` |
| `daemon-port` | `integer` | いいえ | `8766` |
| `daemon-token` | `secret` | いいえ | 空 |
| `provider` | `select` | はい | `claude-code` |
| `location` | `select` | はい | `local` |
| `workspace` | `string` | いいえ | 空 |
| `advanced-settings` | `boolean` | いいえ | false |
| `ssh-target` | `string` | いいえ | 空 |
| `daemon-id` | `string` | いいえ | 空 |
| `daemon-connect-timeout` | `integer` | いいえ | `30` |
| `ssh-port` | `integer` | いいえ | `22` |
| `ssh-identity-file` | `string` | いいえ | 空 |
| `acp-command` | `string` | いいえ | 空 |
| `knowledge-bases` | `knowledge-base-multi-selector` | いいえ | `[]` |
| `langbot-assets-enabled` | `boolean` | いいえ | true |
| `langbot-assets-mode` | `select` | いいえ | `auto` |
| `langbot-assets-gateway-host` | `string` | いいえ | `127.0.0.1` |
| `langbot-assets-gateway-port` | `integer` | いいえ | `0` |
| `langbot-assets-gateway-public-url` | `string` | いいえ | 空 |
| `langbot-assets-token-ttl` | `integer` | いいえ | `3600` |
| `timeout` | `integer` | いいえ | `300` |
| `reuse-session` | `boolean` | いいえ | true |
| `env-json` | `text` | いいえ | 空 |
| `ssh-connect-timeout` | `integer` | いいえ | `10` |
| `ssh-extra-options` | `string` | いいえ | 空 |
| `startup-timeout` | `integer` | いいえ | `30` |
| `initialize-timeout` | `integer` | いいえ | `120` |
| `create-session-if-missing` | `boolean` | いいえ | true |
| `streaming` | `boolean` | いいえ | true |
| `append-run-scope-prompt` | `boolean` | いいえ | true |
| `mcp-servers-json` | `text` | いいえ | 空 |

## Host 権限

- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `retrieve`
- **`history`**: `page`
- **`storage`**: `plugin`

## インストールと使用方法

1. LangBot プラグインマーケットからこのプラグインをインストールします。
2. Pipeline の Runner セレクターで下記 Runner ID を選択します。
3. 設定表に従って接続情報を入力し、機密値は管理画面の secret フィールドに保存します。

## セキュリティと制約

- Runner が利用できるのは、現在の実行で許可された LangBot リソースだけです。
- 外部サービスの可用性、モデル機能、レート制限は各プラットフォームに依存します。
- 高度な動作と製品固有の制約は、ルートの中国語 README または英語版 README_en_US.md を参照してください。


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
