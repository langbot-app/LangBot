# WeKnora Agent

`agent-id` は両モードで任意です。省略時は `chat` が `builtin-quick-answer`、`agent` が `builtin-smart-reasoning` を使用します。明示的な空値は ID を送信しません。保存済み ID は置き換えません。`knowledge-base-ids` は両モードで使える WeKnora のリモート ID であり、LangBot の UUID ではありません。

## 概要

WeKnora エージェントまたはナレッジベースチャットを LangBot Runner として実行します。

## パッケージ情報

- **Runner ID**: `plugin:langbot-team/WeKnoraAgent/default`
- **バージョン**: `0.1.2`
- **リポジトリ**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/weknora-agent)

## 主な機能

- **有効**: `streaming`
- **未宣言**: `tool calling`, `knowledge retrieval`, `multimodal input`, `interrupt`

## 設定

| フィールド | 型 | 必須 | 既定値 |
| --- | --- | --- | --- |
| `base-url` | `string` | はい | `http://localhost:8080/api/v1` |
| `api-key` | `secret` | はい | 空 |
| `app-type` | `select` | はい | `agent` |
| `agent-id` | `string` | いいえ | `chat`: `builtin-quick-answer`; `agent`: `builtin-smart-reasoning` |
| `knowledge-base-ids` | `array[string]` | いいえ | `[]` |
| `web-search-enabled` | `boolean` | いいえ | false |
| `advanced-settings` | `boolean` | いいえ | false |
| `timeout` | `integer` | いいえ | `120` |
| `base-prompt` | `string` | いいえ | `请回答用户的问题。` |

## Host 権限

- **`storage`**: `plugin`

## インストールと使用方法

1. LangBot プラグインマーケットからこのプラグインをインストールします。
2. Pipeline の Runner セレクターで下記 Runner ID を選択します。
3. 設定表に従って接続情報を入力し、機密値は管理画面の secret フィールドに保存します。

## セキュリティと制約

- Runner が利用できるのは、現在の実行で許可された LangBot リソースだけです。
- 外部サービスの可用性、モデル機能、レート制限は各プラットフォームに依存します。
- 高度な動作と製品固有の制約は、ルートの中国語 README または英語版 README_en_US.md を参照してください。
