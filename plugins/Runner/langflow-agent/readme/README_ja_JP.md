# Langflow Agent

## 概要

Langflow フローを LangBot Runner として実行します。

## パッケージ情報

- **Runner ID**: `plugin:langbot-team/LangflowAgent/default`
- **バージョン**: `0.1.2`
- **リポジトリ**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/langflow-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/langflow-agent)

## 主な機能

- **有効**: `streaming`, `tool calling`, `knowledge retrieval`
- **未宣言**: `multimodal input`, `interrupt`

## 設定

| フィールド | 型 | 必須 | 既定値 |
| --- | --- | --- | --- |
| `base-url` | `string` | はい | `http://localhost:7860` |
| `api-key` | `secret` | はい | 空 |
| `flow-id` | `string` | はい | 空 |
| `advanced-settings` | `boolean` | いいえ | false |
| `input-type` | `string` | いいえ | `chat` |
| `output-type` | `string` | いいえ | `chat` |
| `tweaks` | `json` | いいえ | `{}` |
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
