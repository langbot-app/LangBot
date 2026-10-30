# FastGPTConnector

FastGPT APIを使用してFastGPTナレッジベースから知識を取得します。

## FastGPTについて

FastGPTは、LLM大規模言語モデルに基づくオープンソースのナレッジベース質疑応答システムです。複雑な質疑応答シナリオに対応する、すぐに使えるデータ処理とモデル呼び出し機能を提供します。

## 機能

- FastGPTデータセット/ナレッジベースから知識を検索・取得
- 複数の検索モードをサポート（埋め込み検索、全文検索、混合検索）
- 設定可能な類似度しきい値とトークン制限
- より良い結果を得るためのオプションのリランキング機能
- 拡張モデルによるクエリ最適化

## 設定

このプラグインには以下の設定パラメータが必要です：

### 必須パラメータ

- **api_base_url**：FastGPT APIのベースURL
  - ローカルデプロイの場合：`http://localhost:3000`（デフォルト）
  - リモートサーバーの場合：サーバーのURL（例：`https://your-domain.com`）
- **api_key**：FastGPT APIキー
  - フォーマット：`fastgpt-xxxxx`
- **dataset_id**：FastGPTナレッジベース/データセットのID

### オプションパラメータ

- **limit**（デフォルト：5000）：取得する最大トークン数
- **similarity**（デフォルト：0.0）：最小類似度スコア（0-1）
- **search_mode**（デフォルト：embedding）：使用する検索方法
  - `embedding`：セマンティックベクトル検索
  - `fullTextRecall`：全文キーワード検索
  - `mixedRecall`：両方の方法を組み合わせた混合検索
- **using_rerank**（デフォルト：false）：リランキングを使用するかどうか
- **dataset_search_using_extension_query**（デフォルト：false）：クエリ最適化を使用するかどうか
- **dataset_search_extension_model**（オプション）：クエリ最適化に使用するモデル
- **dataset_search_extension_bg**（オプション）：クエリ最適化の背景説明

## 設定値の取得方法

### FastGPT APIキーの取得

1. FastGPTインスタンスにアクセス（例：`http://localhost:3000`）
2. API管理または設定セクションに移動
3. APIキーを作成またはコピー（フォーマット：`fastgpt-xxxxx`）

### データセットIDの取得

1. FastGPTで、ナレッジベース一覧に移動
2. ナレッジベースをクリックして詳細を表示
3. データセットIDはURLまたはデータセットの詳細ページで確認できます

## APIリファレンス

このプラグインはFastGPT Dataset Search Test APIを使用します：
- エンドポイント：`POST /api/core/dataset/searchTest`
- ドキュメント：https://doc.fastgpt.io/docs/introduction/development/openapi/dataset

## 検索方法

### 埋め込み検索（Embedding Search）
ベクトル埋め込みに基づくセマンティック類似度を使用します。クエリの意図を理解し、意味的に関連するコンテンツを見つけるのに最適です。

### 全文検索（Full-Text Recall）
従来のキーワードベースの全文検索。正確な一致や特定の用語を見つけるのに最適です。

### 混合検索（Mixed Recall）
埋め込み検索と全文検索の両方を組み合わせます。セマンティック理解とキーワードマッチングの両方を備えたバランスの取れた結果を提供します。
