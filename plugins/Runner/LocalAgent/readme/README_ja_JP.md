# 組み込みエージェント

## 概要

モデルのフォールバック、ツール呼び出し、ナレッジ検索に対応する組み込みエージェントです。

## パッケージ情報

- **Runner ID**: `plugin:langbot-team/LocalAgent/default`
- **バージョン**: `0.1.0`
- **リポジトリ**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/LocalAgent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/LocalAgent)

## 主な機能

- **有効**: `streaming`, `tool calling`, `knowledge retrieval`, `multimodal input`, `skill authoring`, `interrupt`, `steering`
- **未宣言**: 空

## 設定

| フィールド | 型 | 必須 | 既定値 |
| --- | --- | --- | --- |
| `model` | `model-fallback-selector` | はい | `{fallbacks: [], primary: '', reasoning: {}}` |
| `timeout` | `integer` | いいえ | `300` |
| `prompt` | `prompt-editor` | はい | `[{content: You are a helpful assistant., role: system}]` |
| `remove-think` | `boolean` | いいえ | false |
| `knowledge-bases` | `knowledge-base-multi-selector` | いいえ | `[]` |
| `advanced-settings` | `boolean` | いいえ | `false` |
| `date-grounding` | `boolean` | いいえ | `true` |
| `retrieval-top-k` | `integer` | いいえ | `5` |
| `rerank-model` | `rerank-model-selector` | いいえ | 空 |
| `rerank-top-k` | `integer` | いいえ | `5` |
| `max-tool-iterations` | `integer` | いいえ | `100` |
| `tool-execution-mode` | `select` | いいえ | `parallel` |
| `max-tool-result-chars` | `integer` | いいえ | `20000` |
| `context-history-fetch-limit` | `integer` | いいえ | `50` |
| `context-window-tokens` | `integer` | いいえ | `200000` |
| `context-reserve-tokens` | `integer` | いいえ | `16384` |
| `context-keep-recent-tokens` | `integer` | いいえ | `20000` |
| `context-summary-tokens` | `integer` | いいえ | `8000` |

## Host 権限

- **`models`**: `count_tokens`, `invoke`, `stream`, `rerank`
- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `list`, `retrieve`
- **`history`**: `page`

## インストールと使用方法

1. LangBot プラグインマーケットからこのプラグインをインストールします。
2. Pipeline の Runner セレクターで下記 Runner ID を選択します。
3. 設定表に従って接続情報を入力し、機密値は管理画面の secret フィールドに保存します。

## セキュリティと制約

- Runner が利用できるのは、現在の実行で許可された LangBot リソースだけです。
- 外部サービスの可用性、モデル機能、レート制限は各プラットフォームに依存します。
- 高度な動作と製品固有の制約は、ルートの中国語 README または英語版 README_en_US.md を参照してください。

## Box

`box-enabled` でサンドボックスを有効にします。`box-session-id-template` の既定値 `{launcher_type}_{launcher_id}` はチャット単位で再利用し、`{global}` はワークスペース内で共有します。`{sender_id}`、`{bot_id}`、`{run_id}` とリクエスト変数も使えます。Runner が Box を選択し、入力をインポートし、正常終了時に今回の outbox をエクスポートします。
