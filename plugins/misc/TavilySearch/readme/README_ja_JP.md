# TavilySearch プラグイン

AI エージェント（LLM）専用に構築された Tavily API を使用して、LangBot に検索機能を提供するプラグインです。

## 機能

- Tavily による リアルタイムウェブ検索
- 異なる検索深度のサポート（基本/詳細）
- トピック別検索（一般/ニュース/金融）
- AI 生成の回答を含める
- 関連画像を含める
- 生の HTML コンテンツを含める
- カスタマイズ可能な結果数

## インストール

1. プラグインをインストールします。

2. Tavily API キーを設定します：
   - [Tavily](https://tavily.com/) から API キーを取得します
   - LangBot のプラグイン設定に API キーを追加します

## 使用方法

このプラグインは `tavily_search` ツールを追加し、会話内で LLM によって使用できます。

### パラメータ

- **query**（必須）：検索クエリ文字列
- **search_depth**（オプション）："basic"（デフォルト）または "advanced"
- **topic**（オプション）："general"（デフォルト）、"news"、または "finance"
- **max_results**（オプション）：結果の数（1-20、デフォルト：5）
- **include_answer**（オプション）：AI 生成の回答を含める（デフォルト：false）
- **include_images**（オプション）：関連画像を含める（デフォルト：false）
- **include_raw_content**（オプション）：生の HTML コンテンツを含める（デフォルト：false）

### 例

LangBot とチャットする際、LLM は自動的にこのツールを使用できます：

```
ユーザー：人工知能に関する最新ニュースは何ですか？

ボット：[tavily_search ツールを使用、topic="news"]
```

## 開発

このプラグインを開発または変更するには：

1. `components/tools/tavily_search.py` でツールロジックを編集します
2. `manifest.yaml` で設定を変更します
3. `components/tools/tavily_search.yaml` でツールパラメータを更新します

## 設定

プラグインには以下の設定が必要です：

- **tavily_api_key**：Tavily API キー（必須）

## ライセンス

このプラグインは LangBot プラグインエコシステムの一部です。

## リンク

- [Tavily API ドキュメント](https://docs.tavily.com/)
- [LangBot ドキュメント](https://langbot.app/docs/)
