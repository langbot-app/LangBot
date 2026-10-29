# DifyDatasetsConnector

Dify APIを使用してDifyナレッジベースから知識を取得またはファイルを保存します。

## 設定

LangBotで外部ナレッジベースを追加し、ナレッジリトリーバータイプとして「DifyDatasetsConnector」を選択してください。

### 作成設定（ナレッジベース作成時に設定）

- **api_base_url**：Dify APIのベースURL
  - Dify Cloudの場合：`https://api.dify.ai/v1`（デフォルト）
  - セルフホストインスタンスの場合：サーバーのURL（例：`http://localhost/api` または `https://your-domain.com/api`）
- **dify_apikey**：DifyインスタンスのAPIキー
- **dataset_id**：Difyナレッジベース/データセットのID

### 検索設定（クエリごとに調整可能）

- **search_method**（デフォルト：semantic_search）：使用する検索方法
  - `keyword_search`：キーワードベースの検索
  - `semantic_search`：セマンティック類似度検索（デフォルト）
  - `full_text_search`：全文検索
  - `hybrid_search`：ハイブリッド検索（セマンティック検索と全文検索の組み合わせ）
- **top_k**（デフォルト：5）：取得する結果の最大数
- **score_threshold_enabled**（デフォルト：オフ）：スコア閾値フィルタリングを有効にするかどうか
- **score_threshold**（デフォルト：0.5）：最小関連度スコア（0-1）、スコア閾値が有効な場合のみ表示
- **reranking_enable**（デフォルト：オフ）：リランキングを有効にして結果の品質を向上。リランキングモデルはDifyデータセット設定から自動的に取得されます。先にDifyコンソールでリランキングモデルを設定してください

## 設定値の取得方法

### Dify APIキーの取得

1. https://cloud.dify.ai/ にアクセス
2. ナレッジベースページに移動
3. 左サイドバーの「API ACCESS」をクリック
4. 「API Keys」セクションからAPIキーを作成またはコピー

### データセットIDの取得

1. Difyナレッジベース一覧でナレッジベースをクリック
2. データセットIDはURLに含まれています：`https://cloud.dify.ai/datasets/{dataset_id}`
3. またはナレッジベースのAPIドキュメントページで確認できます

### リランキングの設定

1. Difyコンソールでデータセット設定に移動
2. リランキングを有効にし、リランキングモデルを選択（例：`cohere/rerank-v3.5`）
3. 設定を保存
4. LangBotで「リランキングを有効化」トグルをオンにすると、プラグインがDifyで設定されたモデルを自動的に使用します

## APIリファレンス

このプラグインはDify Dataset APIを使用します：
- 検索：`POST /v1/datasets/{dataset_id}/retrieve`
- データセット情報：`GET /v1/datasets/{dataset_id}`
- ドキュメントアップロード：`POST /v1/datasets/{dataset_id}/document/create-by-file`
- ドキュメント削除：`DELETE /v1/datasets/{dataset_id}/documents/{document_id}`
- ドキュメント：https://docs.dify.ai/
