# Claude Code Agent

## 概要

Claude Code CLI を LangBot Runner として実行します。

## パッケージ情報

- **Runner ID**: `plugin:langbot-team/ClaudeCodeAgent/default`
- **バージョン**: `0.1.3`
- **リポジトリ**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/claude-code-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/claude-code-agent)

## 主な機能

- **有効**: `streaming`, `tool calling`, `knowledge retrieval`, `steering`
- **未宣言**: `multimodal input`, `interrupt`

## 設定

| フィールド | 型 | 必須 | 既定値 |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | いいえ | false |
| `daemon-host` | `string` | いいえ | `127.0.0.1` |
| `daemon-port` | `integer` | いいえ | `8767` |
| `daemon-token` | `secret` | いいえ | 空 |
| `location` | `select` | はい | `local` |
| `workspace` | `string` | いいえ | 空 |
| `advanced-settings` | `boolean` | いいえ | false |
| `command` | `string` | いいえ | `claude` |
| `args-json` | `string` | いいえ | `[]` |
| `env-json` | `string` | いいえ | `{}` |
| `ssh-target` | `string` | いいえ | 空 |
| `ssh-port` | `integer` | いいえ | `22` |
| `daemon-id` | `string` | いいえ | 空 |
| `timeout` | `integer` | いいえ | `300` |
| `streaming` | `boolean` | いいえ | true |
| `reuse-session` | `boolean` | いいえ | true |
| `dangerously-skip-permissions` | `boolean` | いいえ | true |
| `knowledge-bases` | `knowledge-base-multi-selector` | いいえ | `[]` |
| `langbot-assets-enabled` | `boolean` | いいえ | true |
| `mcp-bridge-transport` | `select` | いいえ | `auto` |
| `mcp-servers-json` | `string` | いいえ | `[]` |

## Host 権限

- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `retrieve`
- **`history`**: `page`

## インストールと使用方法

1. LangBot プラグインマーケットからこのプラグインをインストールします。
2. Pipeline の Runner セレクターで下記 Runner ID を選択します。
3. 設定表に従って接続情報を入力し、機密値は管理画面の secret フィールドに保存します。

## セキュリティと制約

- Runner が利用できるのは、現在の実行で許可された LangBot リソースだけです。
- LangBot はまだ対話的な承認フローを提供していないため、Claude Code はデフォルトで `--dangerously-skip-permissions` を使用します。信頼できるワークスペースと制限された OS アカウントでのみ使用し、通常の権限確認に戻す場合は false に設定してください。
- 外部サービスの可用性、モデル機能、レート制限は各プラットフォームに依存します。
- 高度な動作と製品固有の制約は、ルートの中国語 README または英語版 README_en_US.md を参照してください。


> Shared runtime / daemon upgrade: [required setup and safety contract](../README.md#shared-worker-candidate--daemon-upgrade). Shared 模式必须配置独立强 token 和端口；默认本地工作目录为 `/data/workspace`。请同时升级 daemon.py 与完整 pkg 目录；旧客户端不兼容。
