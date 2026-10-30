# DeerFlow Agent

## 概要

DeerFlow LangGraph エージェントを LangBot Runner として実行します。

## パッケージ情報

- **Runner ID**: `plugin:langbot-team/DeerFlowAgent/default`
- **バージョン**: `0.1.2`
- **リポジトリ**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/deerflow-agent)

## 主な機能

- **有効**: `streaming`, `multimodal input`
- **未宣言**: `tool calling`, `knowledge retrieval`, `interrupt`

## 設定

| フィールド | 型 | 必須 | 既定値 |
| --- | --- | --- | --- |
| `api-base` | `string` | はい | `http://127.0.0.1:2026` |
| `api-key` | `secret` | いいえ | 空 |
| `auth-header` | `secret` | いいえ | 空 |
| `assistant-id` | `string` | はい | `lead_agent` |
| `advanced-settings` | `boolean` | いいえ | false |
| `model-name` | `string` | いいえ | 空 |
| `thinking-enabled` | `boolean` | いいえ | false |
| `plan-mode` | `boolean` | いいえ | false |
| `subagent-enabled` | `boolean` | いいえ | false |
| `max-concurrent-subagents` | `integer` | いいえ | `3` |
| `timeout` | `integer` | いいえ | `300` |
| `recursion-limit` | `integer` | いいえ | `1000` |

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
