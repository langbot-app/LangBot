# RAGFlowConnector

RAGFlow APIを使用してRAGFlowナレッジベースから知識を取得、またはファイルを保存します。

## RAGFlowについて

RAGFlowは、深いドキュメント理解に基づくオープンソースのRAG（検索拡張生成）エンジンです。さまざまな複雑な形式のデータから、十分な根拠のある引用を伴う真実の質疑応答機能を提供します。

## 機能

- RAGFlowデータセット/ナレッジベースから知識チャンクを取得
- RAGFlowデータセットにファイルをアップロードし、自動的に解析をトリガー
- 1回のクエリで複数のデータセットをサポート
- 設定可能な類似度しきい値とベクトル重み
- キーワードとベクトル類似度を組み合わせたハイブリッド検索
- ファイル取り込み後にGraphRAGナレッジグラフを自動構築
- ファイル取り込み後にRAPTOR階層要約を自動構築
- ナレッジベース作成時にデータセットIDの有効性を自動検証
- 用語およびベクトル類似度スコアを含むリッチなメタデータ結果を返却

## 設定

このプラグインには以下の設定パラメータが必要です：

### 必須パラメータ（作成設定）

- **api_base_url**：RAGFlow APIのベースURL
  - ローカルデプロイの場合：`http://localhost:9380`（デフォルト）
  - リモートサーバーの場合：サーバーのURL（例：`http://your-domain.com:9380`）
- **api_key**：RAGFlowインスタンスのAPIキー
- **dataset_ids**：検索するデータセットIDをカンマ区切りで指定
  - フォーマット：`"dataset_id1,dataset_id2,dataset_id3"`
  - 例：`"b2a62730759d11ef987d0242ac120004,a3b52830859d11ef887d0242ac120005"`

### オプションパラメータ（作成設定）

- **auto_graphrag**（デフォルト：false）：ファイル取り込み後にGraphRAGナレッジグラフを自動構築
- **auto_raptor**（デフォルト：false）：ファイル取り込み後にRAPTOR階層要約を自動構築

### オプションパラメータ（検索設定）

- **top_k**（デフォルト：1024）：取得する結果の最大数
- **similarity_threshold**（デフォルト：0.2）：最小類似度スコア（0-1）
- **vector_similarity_weight**（デフォルト：0.3）：ハイブリッド検索におけるベクトル類似度の重み（0-1）
- **page_size**（デフォルト：30）：1ページあたりの結果数
- **keyword**（デフォルト：false）：LLMでクエリからキーワードを抽出して検索を強化
- **rerank_id**：RAGFlowで設定されたリランクモデルID（例：`BAAI/bge-reranker-v2-m3`）
- **use_kg**（デフォルト：false）：ナレッジグラフ検索を有効化

## 設定値の取得方法

### RAGFlow APIキーの取得

1. RAGFlowインスタンスにアクセス（例：`http://localhost:9380`）
2. **ユーザー設定** > **API** セクションに移動
3. APIキーを生成またはコピー（フォーマット：`ragflow-xxxxx`）

### データセットIDの取得

1. RAGFlowで、ナレッジベース/データセット一覧に移動
2. データセットをクリックして詳細を表示
3. データセットIDは通常、URLまたはデータセットの詳細に表示されます
4. 複数のデータセットの場合は、すべてのIDを収集してカンマで結合

## APIリファレンス

このプラグインは以下のRAGFlow APIを使用します：
- 検索：`POST /api/v1/retrieval`
- ドキュメントアップロード：`POST /api/v1/datasets/{dataset_id}/documents`
- ドキュメント解析：`POST /api/v1/datasets/{dataset_id}/chunks`
- ドキュメント削除：`DELETE /api/v1/datasets/{dataset_id}/documents`
- ナレッジグラフ構築：`POST /api/v1/datasets/{dataset_id}/run_graphrag`
- RAPTOR構築：`POST /api/v1/datasets/{dataset_id}/run_raptor`
- データセット一覧（検証）：`GET /api/v1/datasets`
- ドキュメント：https://ragflow.io/docs/dev/http_api_reference

## 検索方法

RAGFlowはハイブリッド検索アプローチを採用しています：
- **キーワード類似度**：従来のキーワードベースのマッチング
- **ベクトル類似度**：埋め込みを使用したセマンティック類似度
- **重み付け結合**：設定可能な重みで両方の方法を組み合わせ
- **ナレッジグラフ**：関係認識による回答のためのオプショナルなグラフベース検索
- **リランキング**：結果品質向上のためのオプショナルなリランクモデル

`vector_similarity_weight` パラメータがキーワードとベクトル方法のバランスを制御します。
