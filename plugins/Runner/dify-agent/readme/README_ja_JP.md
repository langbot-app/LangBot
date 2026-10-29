# Dify Agent

`remove-think`（真偽値、既定値 `false`）は未完了の内容を含む think タグ内の推論を非表示にします。`app-type` は `chatflow` もサポートします。

## 概要

Dify アプリを LangBot Runner として実行します。

## パッケージ情報

- **Runner ID**: `plugin:langbot-team/DifyAgent/default`
- **バージョン**: `0.1.2`
- **リポジトリ**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/dify-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/dify-agent)

## 主な機能

- **有効**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`
- **未宣言**: `interrupt`

## 設定

| フィールド | 型 | 必須 | 既定値 |
| --- | --- | --- | --- |
| `base-url` | `string` | はい | `https://api.dify.ai/v1` |
| `advanced-settings` | `boolean` | いいえ | false |
| `base-prompt` | `text` | はい | `When the file content is readable, please read the content of this file. When the file is an image, describe the content of this image.` |
| `app-type` | `select` | はい | `chat` |
| `api-key` | `secret` | はい | 空 |
| `timeout` | `integer` | いいえ | `30` |
| `langbot-assets-enabled` | `boolean` | いいえ | false |
| `langbot-assets-gateway-host` | `string` | いいえ | `0.0.0.0` |
| `langbot-assets-gateway-port` | `integer` | いいえ | `8765` |
| `langbot-assets-gateway-request-timeout` | `integer` | いいえ | `60` |
| `langbot-assets-token-ttl` | `integer` | いいえ | `3600` |
| `langbot-assets-input-name` | `string` | いいえ | `langbot_asset_run_token` |

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

### Provider identity compatibility (`user-id-source`)

Per-pipeline Runner parameter, not plugin-global configuration. `sender` remains the default.
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-session` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-session` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-session` uses `conversation.launcher_type` (`group`/`person`) plus `_` plus the exact `conversation.launcher_id`. Host must project the native Query.session launcher into those fields, including interaction/resume runs. Older Hosts that leave these fields empty must be upgraded.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.
