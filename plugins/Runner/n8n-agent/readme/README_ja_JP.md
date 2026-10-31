# n8n ワークフローエージェント

[English](../README.md) · [简体中文](README_zh_Hans.md)

## 概要

n8n ワークフローの Webhook を LangBot Runner として実行します。

## パッケージ情報

- **Runner ID**: `plugin:langbot-team/N8nAgent/default`
- **バージョン**: `0.1.2`
- **リポジトリ**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/n8n-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/n8n-agent)

## 主な機能

- **有効**: `streaming`, `tool calling`, `knowledge retrieval`
- **未宣言**: `multimodal input`, `interrupt`

## 設定

| フィールド | 型 | 必須 | 既定値 |
| --- | --- | --- | --- |
| `webhook-url` | `string` | はい | 空 |
| `auth-type` | `select` | はい | `none` |
| `basic-username` | `string` | いいえ | 空 |
| `basic-password` | `secret` | いいえ | 空 |
| `basic-encoding` (旧非 ASCII 認証: `latin1`) | `select` | いいえ | `utf-8` |
| `jwt-secret` | `secret` | いいえ | 空 |
| `jwt-algorithm` | `string` | いいえ | `HS256` |
| `header-name` | `string` | いいえ | 空 |
| `header-value` | `secret` | いいえ | 空 |
| `advanced-settings` | `boolean` | いいえ | false |
| `timeout` | `integer` | いいえ | `120` |
| `output-key` | `string` | いいえ | `response` |
| `response-handling` | `select` | いいえ | `reply` |
| `langbot-assets-enabled` | `boolean` | いいえ | false |
| `langbot-assets-gateway-host` | `string` | いいえ | `0.0.0.0` |
| `langbot-assets-gateway-port` | `integer` | いいえ | `8765` |
| `langbot-assets-gateway-request-timeout` | `integer` | いいえ | `60` |
| `langbot-assets-token-ttl` | `integer` | いいえ | `3600` |
| `langbot-assets-input-name` | `string` | いいえ | `langbot_asset_run_token` |

## レスポンス処理と旧版からの移行

既定の `reply` は HTTP 200 の出力を返信します。`ignore` は応答ヘッダーを待ち、
すべての HTTP 2xx を受け入れ、本文を読み取らず接続を閉じます。返信や空返信エラーは
発生しません。Webhook を **Respond Immediately（即時応答）** に設定してください。
バックグラウンド送信ではなく、非 2xx とタイムアウトは引き続き失敗になります。
既定の `timeout=120` 秒はリクエスト全体に適用され、返信本文は 1,048,576 文字までです。
リクエスト終了時にアセットトークンは失効するため、後続の非同期処理では利用できません。

旧 `ai.n8n-service-api` の 11 フィールドは同じ名前で
`ai.runner_config["plugin:langbot-team/N8nAgent/default"]` に移ります。
Webhook URL は空が既定値で、明示設定が必要です。アセットアクセスは既定で無効です。
JSON に `output-key` がない場合はオブジェクト全体を返し、空の返信はエラーとします。
資格情報を保護するため、エラー本文や例外の詳細は返信・ログに出力しません。

会話 ID は Host の状態で管理し、`user_id` は旧 launcher/chat ではなく SDK actor に
基づきます。これらを証明済みのセキュリティ改善とは扱いません。旧会話の継続には
明示的な ID・状態の移行、または承認されたリセットが必要です。業務パラメータは
`adapter.extra.params` から読み、予約済み ID は上書きしません。`msg_create_time` の
既定値は空文字で、明示的なゼロも保持します。HTTP リダイレクトは自動追従しません。
旧 n8n は現在の入力のみを送信していたため、local-agent の履歴ラウンド制限は追加しません。

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
