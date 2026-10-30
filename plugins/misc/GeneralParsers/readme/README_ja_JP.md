# GeneralParsers

LangBot 公式の汎用ドキュメント parser プラグインです。ファイルから構造化テキストを抽出し、LangRAG などの KnowledgeEngine プラグインで利用できる形に変換します。

## 対応フォーマット

| フォーマット | MIME Type | 解析方式 |
|-------------|-----------|---------|
| PDF | `application/pdf` | PyMuPDF ベースのレイアウト認識解析。表、ページ区切り、任意の視覚モデル強化に対応 |
| DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | python-docx による段落抽出 |
| Markdown | `text/markdown` | HTML に変換してから構造化抽出（見出し、リスト、コードブロック、表） |
| HTML | `text/html` | BeautifulSoup による抽出（script/style を自動除去） |
| TXT | `text/plain` | 文字コード自動判定（chardet） |

## アーキテクチャ

```
┌──────────────────────────────────────────────┐
│  KnowledgeEngine Plugin (例: LangRAG)        │
│  Chunk → Embedding → Store → Retrieve        │
└──────────────────┬───────────────────────────┘
                   │ invoke_parser (RPC)
┌──────────────────▼───────────────────────────┐
│          GeneralParsers                      │
│                                              │
│  ファイル bytes → 形式判定 → 解析            │
│                                              │
│  ParseResult:                                │
│    ├── text: 抽出された全文                   │
│    ├── sections: 見出しベースの section 群    │
│    │   └── TextSection(content, heading,      │
│    │                   level)                 │
│    └── metadata: ファイル名、MIME Type など   │
└──────────────────────────────────────────────┘
```

## 機能

- **視覚モデルの任意利用** - 視覚対応 LLM を設定すると、スキャン PDF の OCR や埋め込み画像の説明を実行できます
- **強化された PDF 解析** - PyMuPDF ベースでページ境界を保ちながら、表を本文に統合し、より豊富な文書 metadata を出力します
- **スキャン PDF 対応** - スキャンページらしきページを検出し、視覚モデルが設定されていれば OCR を行います
- **埋め込み画像の説明** - PDF 内の画像を抽出し、後段の検索に使いやすい短い説明文に変換できます
- **ヘッダー / フッター除去** - PDF 内で繰り返し出現するヘッダーやフッターを検出して除去します
- **構造化 section 認識** - Markdown 風見出し（`# ~ ######`）を検出し、階層付き sections に分割します
- **表の Markdown 化** - PDF / HTML / Markdown 内の表を Markdown テーブル形式へ変換します
- **非同期解析** - イベントループをブロックしないよう、ファイル解析はスレッドプールで実行されます
- **文字コード自動判定** - chardet により GBK、UTF-8 などを自動判定します
- **フォールバック解析** - 未対応フォーマットはプレーンテキストとして解析を試みます

## 設定

このプラグインには 1 つの任意設定があります。

- `vision_llm_model_uuid`: スキャンページ OCR と PDF 画像説明に使う視覚対応 LLM

この設定を空のままにしても GeneralParsers は通常通り動作しますが、PDF はテキスト / レイアウト解析のみになり、視覚強化は行われません。

## 使い方

1. LangBot にこのプラグインをインストールします
2. スキャン PDF OCR や画像説明が必要な場合は、視覚モデルを追加で設定します
3. ナレッジベースにファイルをアップロードする際、parser として GeneralParsers を選択します
4. 解析結果はそのまま KnowledgeEngine プラグインへ渡され、後続処理に使われます

## 出力構造

GeneralParsers は構造化された `ParseResult` を返します。

- `text`: 抽出された全文
- `sections`: 見出しを考慮した text sections。構造を活かす chunk 戦略で利用できます
- `metadata`: ファイル名、MIME Type、ページ数、表の有無、スキャンページ検出結果、視覚モデル利用状況などの metadata

最近の PDF parser が追加する主な metadata フィールドは次の通りです。

- `page_count`
- `word_count`
- `has_tables`
- `has_scanned_pages`
- `headers_footers_removed`
- `vision_used`
- `vision_tasks_count`
- `vision_scanned_pages_count`
- `vision_images_described_count`

## 開発

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env` に `DEBUG_RUNTIME_WS_URL` と `PLUGIN_DEBUG_KEY` を設定し、IDE デバッガーで起動してください。
