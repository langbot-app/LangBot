# LangRAG

LangRAG は、LangBot 向けの RAG（Retrieval-Augmented Generation）ナレッジエンジンプラグインです。LangBot Host に組み込まれている Embedding モデルとベクトルデータベースを利用して、ドキュメントの取り込み、インデックス作成、ナレッジベース検索を行います。

LangBot の標準的な RAG エンジンとして利用できるほか、独自の KnowledgeEngine プラグインを開発する際の参考実装としても使えます。

## 機能

- **外部 Parser 連携**: GeneralParsers などの Parser プラグインが提供する事前解析済みコンテンツを優先的に利用し、構造化された `sections` と文書 `metadata` を取り込みます
- **内蔵パーサーによるフォールバック**: 外部 Parser が設定されていない場合でも、プラグイン内蔵のパーサーにフォールバックできます
- **複数のインデックス戦略**: フラットチャンク、親子チャンク、LLM 生成の Q&A ペアに対応します
- **柔軟な検索方式**: ベクトル検索、全文検索、ハイブリッド検索に対応します
- **クエリ書き換え**: HyDE、Multi-Query、Step-Back により recall を改善できます
- **設定可能なチャンク分割**: チャンクサイズとオーバーラップを指定した再帰的な文字分割に対応します
- **構造を意識したチャンク分割**: Parser が sections を返す場合、見出し階層、ページ情報、表の境界をできるだけ保持します
- **コンテキスト拡張**: 各ヒットに隣接チャンクを追加し、より完全な検索コンテキストを返せます
- **再ランキング**: LangBot rerank モデルまたは LLM による候補結果の再ランキングに対応します
- **ドキュメント管理**: ドキュメント単位でインデックス済みベクトルを削除できます
- **Observability ページ**: 取り込み、検索、削除、Embedding などの運用指標と診断情報を確認できます

## アーキテクチャ

```text
┌─────────────────────────────────┐
│         LangBot Core            │
│  (Embedding / VDB / Storage)    │
└──────────┬──────────────────────┘
           │ RPC (IPC)
┌──────────▼──────────────────────┐
│          LangRAG                │
│  ┌───────────────────────────┐  │
│  │       Knowledge Engine    │  │
│  │  Parse → Chunk → Embed   │  │
│  │      → Store / Search    │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

## ドキュメント取り込みフロー

LangRAG は、LangBot Host が提供する Parser 出力を優先して利用します。

1. LangBot がアップロードされたファイルを読み取ります。
2. GeneralParsers などの Parser プラグインが `text`、`sections`、`metadata` を抽出します。
3. LangRAG がその構造化された解析結果を直接取り込みます。
4. Parser 出力がない場合は、LangRAG の内蔵パーサーにフォールバックします。
5. 選択されたインデックス戦略に従って chunks または Q&A ペアを作成します。
6. LangBot Host が embedding を生成し、ベクトルデータベースへ保存します。

そのため、LangRAG は外部 Parser プラグインと組み合わせて使うことを推奨します。PDF、表、多ページ文書、OCR、画像説明を含むケースでは、外部 Parser によりチャンク品質と検索品質が向上しやすくなります。

## 設定

### ナレッジベース作成

| パラメータ | 説明 | デフォルト |
| --- | --- | --- |
| `embedding_model_uuid` | テキストをベクトル化する Embedding モデル | 必須 |
| `index_type` | インデックス戦略: `chunk`、`parent_child`、または `qa` | `chunk` |
| `chunk_size` | 1 チャンクあたりの文字数 | `512` |
| `overlap` | チャンク間のオーバーラップ文字数 | `50` |
| `parent_chunk_size` | 親チャンクサイズ。`parent_child` モードのみで使用 | `2048` |
| `child_chunk_size` | 子チャンクサイズ。`parent_child` モードのみで使用 | `256` |
| `qa_llm_model_uuid` | Q&A ペア生成に使う LLM。`qa` モードのみで使用 | 空 |
| `questions_per_chunk` | 1 チャンクあたりに生成する質問数。`qa` モードのみで使用 | `1` |

### 検索

| パラメータ | 説明 | デフォルト |
| --- | --- | --- |
| `top_k` | 返す検索結果の件数 | `5` |
| `search_type` | 検索モード: `vector`、`full_text`、または `hybrid` | `vector` |
| `vector_weight` | ハイブリッド検索におけるベクトル検索の重み。`0.0` はキーワードのみ、`1.0` はベクトルのみ | `0.7` |
| `query_rewrite` | クエリ書き換え戦略: `off`、`hyde`、`multi_query`、または `step_back` | `off` |
| `rewrite_llm_model_uuid` | クエリ書き換えに使う LLM。書き換え有効時に使用 | 空 |
| `rerank` | 再ランキング戦略: `off`、`rerank_model`、または `llm` | `off` |
| `rerank_model_uuid` | 候補結果の再ランキングに使う LangBot rerank モデル | 空 |
| `rerank_llm_model_uuid` | LLM 再ランキングに使うモデル | 空 |
| `context_window` | 各ヒットに追加する隣接チャンク数 | `0` |

## インデックス戦略

- **chunk**: デフォルトのフラットチャンク方式です。ドキュメントを固定サイズの chunk に分割し、各 chunk を直接 embedding します。Parser が sections を提供している場合は、文書全体を平坦化せず section 境界に沿って分割します。
- **parent_child**: 親子 2 段階のチャンク方式です。まず大きな親チャンクへ分割し、次に小さな子チャンクへ分割します。子チャンクを embedding し、検索ヒット時にはより広い文脈を含む親チャンクのテキストを返します。sections がある場合は自然な親チャンク境界として利用します。
- **qa**: LLM による Q&A ペア生成方式です。テキストを chunk に分割した後、LLM で各 chunk から質問と回答のペアを生成し、質問を embedding します。ユーザーの問い合わせが質問形式に近い場合や、原文が長く答えが分散している場合に有効です。

## クエリ書き換え

- **hyde**: Hypothetical Document Embedding。クエリに対する仮説的な回答を LLM で生成し、その回答を embedding して検索します。
- **multi_query**: 3 つのクエリバリエーションを生成し、それぞれで検索した結果をスコアで統合します。
- **step_back**: より抽象的な質問を生成し、元のクエリと抽象化されたクエリの両方で検索します。

クエリ書き換えは LLM 呼び出しコストを増やします。recall が不足する場合、ユーザーの質問表現が不安定な場合、またはナレッジベースが複雑な場合に有効化するのが適しています。

## GeneralParsers との組み合わせ

現時点では、LangRAG と組み合わせる Parser として GeneralParsers を推奨します。GeneralParsers は次のような情報を提供できます。

- よりクリーンな PDF テキスト抽出
- 構造化された sections
- 表構造を保持したテキスト
- 文書レベルの metadata
- 視覚モデルを使った任意の OCR と画像説明

LangRAG は取り込み時にこれらの Parser 出力を直接利用します。内蔵 fallback parser だけを使う場合と比べて、より良い chunk 構造、より正確な検索結果、より明確な引用コンテキストを得られることが多いです。

## Observability ページ

LangRAG には **Observability** という WebUI ページがあります。最近の取り込み、検索、削除、embedding イベントに加えて、本番運用向けの診断情報を表示します。

- 1 分、5 分、1 時間のウィンドウにおける操作数、レート、エラー率、ゼロ結果率
- 平均レイテンシ、および p50 / p95 / p99 / max レイテンシ
- 取り込みと検索の各ステージの所要時間。parser、chunking、embedding、vector search、rerank、context expansion、vector upsert などを含みます
- 検索品質シグナル。ゼロ結果率、Top-K 充足率、参照カバレッジ、rerank 使用状況、フィルタ付きクエリ率などを含みます
- アクティブなアラート。高エラー率、検索ゼロ結果の増加、p95 レイテンシ悪化、永続化問題などを検出します
- プライバシーに配慮したイベントデータ。元の query テキストは保存せず、query、document、collection の識別子は可能な限り hash で表します

直近の診断データは SDK のインストール単位のストレージに保存され、プラグインの再起動後も保持されます。履歴は最大 100 件、192 KiB に制限され、診断専用です。課金や監査の台帳には使用しないでください。このバージョンでは以前のローカル JSONL 履歴を読み込まず、`LANGRAG_OBSERVABILITY_DIR` も使用しません。ナレッジのドキュメントやベクトルには影響しません。

ページバックエンドは LangBot Page API 経由で `/snapshot`、`/export`、`/clear`、`/metrics` も提供します。`/metrics` は Prometheus text format を返すため、外部監視スタックへ接続できます。

## 開発

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env` に `DEBUG_RUNTIME_WS_URL` と `PLUGIN_DEBUG_KEY` を設定し、IDE のデバッガーから起動してください。

### テスト

```bash
python3 -m unittest discover -s tests
```

### オフライン Benchmark

```bash
python3 -m benchmarks.run
```

Benchmark データセット、実験設定、決定的なローカルアダプター、メトリクスコードは `benchmarks/` にあります。実行結果は `benchmarks/runs/` 配下の追跡可能な `results.json` に書き込まれます。

このリポジトリの `misc/GeneralParsers` と組み合わせて Parser 連携を benchmark できます。

```bash
python3 -m benchmarks.run \
  --dataset benchmarks/datasets/parser_compare_zh.json \
  --config benchmarks/configs/parser_compare.json
```

より難しい multi-hop 検索ケースも利用できます。

```bash
python3 -m benchmarks.run \
  --dataset benchmarks/datasets/hard_multihop_zh.json \
  --config benchmarks/configs/hard_retrieval.json
```

## リンク

- [LangBot ドキュメント](https://langbot.app/docs/)

## コントリビューション

issue、pull request、ドキュメント改善、利用フィードバックを歓迎します。このプラグインが役に立った場合は、リポジトリへの star も歓迎します。
