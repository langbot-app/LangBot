# LongTermMemory

LangBot 向けの長期記憶プラグインです。二層構造の記憶モデルを採用しています。

- L1 コアプロフィール: system prompt に注入
- L2 エピソード記憶: ベクトル検索で想起してコンテキストへ注入

## 役割

- `remember` ツールでエピソード記憶を書き込みます
- `recall_memory` ツールで制御された条件付きの記憶検索を行います
- `update_profile` ツールで安定したプロフィール情報を更新します
- `forget` ツールで指定 ID のエピソード記憶を削除できます
- EventListener でプロフィールと現在の話者情報を自動注入します
- EventListener によりモデル呼び出し前に関連する記憶を自動検索して注入します
- `!memory` コマンドで状態確認とデバッグができます
- 視覚的に確認できる Web 版**メモリコンソール**ページを提供します（プロファイル、情景記憶（ページネーション対応）、監査ログ、エクスポート、metadata 分離のヘルスチェック、直近のメモリ注入スナップショット）
- `!memory list [page]` でエピソード記憶をページ単位で一覧できます
- `!memory forget <episode_id>` で特定のエピソードを削除できます
- `!memory search <query>` でエピソード記憶を検索できます（結果には episode ID を含みます）
- `!memory export` コマンドで現在の会話スコープ内の L1 プロフィールを JSON として出力できます
- `correction` / `fact-update` / `clarification` タグ付きの新規記憶が保存されると、関連する古い記憶を自動で superseded 扱いにします

## 全体設計

このプラグインは「会話履歴を全部 prompt に入れる」方式ではありません。長期記憶を 2 層に分け、それぞれ異なる役割を持たせています。

- **L1 コアプロフィール**: 名前、好み、役割、長期メモのような安定した事実
- **L2 エピソード記憶**: 最近の出来事、計画、体験のような時系列性を持つ記憶

この分離には理由があります。

- 安定プロフィールは system prompt に入れる方が安定して効く
- エピソード記憶は増え続けるため、毎回全部入れるのではなく必要時に検索すべき
- Agent による更新方法も、安定プロフィールと出来事記憶では異なる

## OpenClaw のような個人アシスタント型記憶方式との違い

最近の Agent システムでは、OpenClaw のように長期記憶を `MEMORY.md` のような人間が直接読めるテキストファイルとして持ち、要約・反省・軽い検索ロジックを組み合わせる設計がよく議論されています。

この方式には明確な利点があります。

- 記憶がユーザーに対して完全に透明
- プレーンテキストなのでバックアップ、同期、バージョン管理が容易
- 単一ユーザー・単一アシスタント・強い連続性を持つ個人用途に非常に自然
- 記憶量が小さいうちは全文理解で十分なことも多い

しかし、LangBot の LongTermMemory が解いている問題はそれと同じではありません。LangBot では典型的に次のような運用が前提になります。

- 1 つの bot が複数のグループチャットや個人チャットを扱う
- 1 つのプラグインインスタンスが複数セッション・複数話者を扱う
- 記憶には「共有グループ文脈」「現在話者の安定プロフィール」「会話単位の出来事記憶」が混在する
- セッション、bot、話者の境界を明示的に守る必要がある

そのため、私たちは「単一のテキスト記憶ファイルを真実源にする」方式をそのまま採用していません。LangBot のマルチセッション実行環境に合うように、より分層的な設計を選んでいます。

### OpenClaw 型記憶が最適化しているもの

抽象化すると、この設計は次のような条件に最適化されています。

- **単一ユーザーの個人アシスタント**
- **人間可読テキストを長期記憶の主形態とする**
- **透明性・編集可能性・物語的連続性を重視する**
- **記憶量は管理可能で、ユーザー自身が直接メンテナンスする前提**

これは、個人 AI アシスタント、研究補助、日誌型パートナーのような用途には非常に合理的です。

### LangBot がそのまま採用しない理由

LongTermMemory は、複数セッション、複数話者、明示的な隔離、制御された注入、検索可能な出来事記憶という条件に合わせて設計されています。

もし長期記憶を `MEMORY.md` のような 1 つの叙事テキストにまとめると、すぐに次の問題が出ます。

- **隔離が難しい**
  - グループ A、グループ B、個人チャット C の記憶をどう安全に共存させるか
  - 共有ログの中から、ある話者の安定プロフィールだけをどう正確に分離するか
- **注入粒度が不安定**
  - system prompt に必要なのは安定プロフィールであり、時系列の日記全文ではない
  - 自動 recall に必要なのは「今の query に最も関係ある断片」であり、物語全体ではない
- **LangBot では多ユーザー境界が本質**
  - 個人アシスタントでは「ユーザー」は通常 1 人
  - LangBot では current speaker / current session / current bot がすべて重要
- **自動注入と能動検索は別の要求**
  - 安定プロフィールは継続的に注入したい
  - 出来事記憶は選択的に検索したい
  - それらを 1 種類のテキスト記憶に押し込むと不自然になる

### 私たちが選んだトレードオフ

したがって、LongTermMemory の設計は本質的に次のトレードオフです。

- **その思想から借りているもの**
  - 記憶は単なるブラックボックスのベクトルストアであるべきではない
  - 安定プロフィール、時間性のある記憶、長期的な振る舞い調整は重要
  - 毎ターンすべてをコンテキストに流し込むべきではない

- **意図的に異なる点**
  - 叙事テキスト日記を唯一の記憶真実源にはしていない
  - 安定プロフィールと出来事記憶を明示的に分離している
  - セッション / 話者 / bot の隔離を優先している
  - L2 記憶を LangBot の KB / 検索系に自然に接続している

要するに:

- OpenClaw は主に「個人アシスタントはどうやって可読・可編集・可反省な長期記憶を持つべきか」を解いている
- LongTermMemory は主に「グループと個人チャットをまたぐ bot が、明示的な隔離ルールのもとで安定プロフィールと検索可能な経験記憶をどう持つべきか」を解いている

どちらが絶対的に優れているという話ではなく、対象プロダクトと重視する失敗モードが違う、という理解が正確です。

## 設計

このプラグインは、LangBot の既存拡張ポイントをなるべくそのまま使う方針です。追加のコア改修を前提にしていません。

- L1 プロフィールはプラグインストレージに JSON として保存
- L2 エピソード記憶はベクターデータベースに保存
- pipeline にこの KnowledgeEngine を紐付けることで明示的に有効化
- 現在は 1 つのプラグインインスタンスにつき 1 つの memory KB を想定し、metadata で隔離

現在の実装は既存の LangBot / SDK API を前提に成り立っています。将来、LangBot に memory 専用 API、session identity API、KB 登録 API などが追加されれば実装はさらに簡潔にできますが、今の設計自体を作り直す必要はありません。

### ベクトルデータベース後方互換性

L2 エピソード記憶は `user_key`、`episode_id`、`tags`、`importance` などの任意 metadata に依存して隔離やフィルタリングを行います。LangBot のすべてのベクトルバックエンドがこの要件を満たすわけではありません。

| バックエンド | 任意 metadata | LongTermMemory の対応状況 |
| --- | --- | --- |
| **Chroma**（デフォルト） | Yes | 完全対応 |
| **Qdrant** | Yes | 完全対応 |
| **SeekDB** | Yes | 完全対応 |
| **Milvus** | No（固定 schema: `text`, `file_id`, `chunk_uuid`） | 非対応 |
| **pgvector** | No（固定 schema: `text`, `file_id`, `chunk_uuid`） | 非対応 |

Milvus と pgvector は認識できない metadata フィールドを黙って破棄します。そのため、`user_key` による隔離や `!memory list`、`!memory forget`、`!memory search` のようなエピソード記憶コマンドは正しく動作しません。フィルタが無視され、スコープ外の結果が返る可能性があります。

LongTermMemory を使う場合は、Chroma、Qdrant、SeekDB のいずれかを使ってください。

## どのように動くか

長期記憶の流れは、大きく 4 段階に分かれます。

### 1. L1 プロフィールの書き込み

- Agent は `update_profile` を使って安定した事実を書き込みます
- データは plugin storage に構造化 JSON として保存されます
- 保存単位は `session` または `speaker` です

### 2. L2 エピソード記憶の書き込み

- Agent は `remember` を使って出来事ベースの記憶を書き込みます
- 各記憶には timestamp、importance、tags、scope などの metadata が付きます
- それらは KnowledgeEngine を通じて embedding され、ベクトル DB に保存されます

### 3. 応答前の自動注入

- `PromptPreProcessing` で EventListener が現在の会話 ID を解決します
- L1 では:
  - session profile を読み込む
  - current speaker profile を読み込む
  - 現在の話者情報と一緒に `default_prompt` へ注入する
- L2 では:
  - 現在のユーザーメッセージを使って一度だけ記憶検索を行う
  - ヒットした記憶を事実ブロックとして prompt に注入する

つまり L1 と L2 はどちらも回答前にコンテキストへ入りますが、L1 は system prompt、L2 は検索結果ブロックとして扱われます。

### 4. 能動検索とデバッグ

- 自動注入だけでは足りない場合、Agent は `recall_memory` を呼び出せます
- 状態確認やデバッグには `!memory`、`!memory profile`、`!memory search`、`!memory list`、`!memory forget` を使えます
- `!memory export` は現在の scope の L1 プロフィールだけを出力します

## AgenticRAG との関係

AgenticRAG と同時に有効にした場合:

- LongTermMemory は自分の memory KB を naive RAG 前処理対象から外します
- L2 の自動 recall は引き続き LongTermMemory 自身が行います
- 同じ memory KB は AgenticRAG の `query_knowledge` ツールから明示的に再検索できます

これにより、記憶の二重注入を避けつつ、必要ならより深い agentic retrieval も可能にしています。

## なぜ Agent に metadata filter を開放していないのか

基盤の runtime は metadata filter を扱えますが、このプラグインでは現時点で Agent フローに任意の raw metadata filter を公開していません。

理由は次の通りです。

- 知識エンジンやベクターバックエンドごとに metadata schema が統一されていない
- filter の項目名、値の形式、使える演算子が異なる可能性がある
- Agent 側に、正しい filter を組み立てるための安定した schema 情報源がまだない

将来、LangBot が知識ベースごとの filterable metadata schema を統一的に提供できるようになれば、より汎用的な Agent 側 metadata filter の導入は可能です。

一方で、この長期記憶プラグイン自身の memory schema は安定しているため、現在でも `recall_memory` という制御されたツール面を通じて、話者や時間範囲などの固定パラメータで記憶を検索できます。モデルに raw filter 構文を直接渡す必要はありません。

## 隔離モデル

2 つの隔離モードをサポートします。

- `session`: グループチャットや個人チャットごとに独立
- `bot`: 同一 bot 配下の全セッションで共有

現在の運用前提では、プラグインインスタンスは通常特定の LangBot ランタイムや bot に紐づくため、このモデルで十分なことが多いです。

## 隔離ルールの詳細

このプラグインには、関連しているが役割の異なるスコープ概念がいくつかあります。

- **session_name**: 現在の query / retrieval 経路で使われる会話識別子。形式は `{launcher_type}_{launcher_id}`
- **session_key**: L1 プロフィール保存に使う内部キー。`bot_uuid` があれば `{bot_uuid}:{launcher_type}_{launcher_id}`、なければ `{launcher_type}_{launcher_id}`
- **scope_key / user_key**: 実際にプロフィール保存や L2 検索隔離に使われるキー

### L1 プロフィールの隔離

L1 は常に現在の会話スコープに紐づいて保存されます。

- `session profile`
  - 現在の会話で共有される安定コンテキスト
- `speaker profile`
  - 現在の話者に紐づく安定コンテキスト

そのため `!memory export` で出力されるのも、現在の `session_key` に属するプロフィールだけです。

### L2 エピソード記憶の隔離

L2 はベクトル DB に metadata 付きで保存され、検索時にその metadata で絞り込みます。

- `session`
  - グループ A の記憶はグループ B に出ない
  - ある個人チャットの記憶は別の個人チャットに出ない
- `bot`
  - 同じ bot 配下の全セッションで記憶を共有する

`sender_id` が使える場合は、まず現在の話者に近い記憶を優先し、その後により広いスコープへ広げることもできます。

### なぜ L1 と L2 の隔離が少し違うのか

これは意図した設計です。

- L1 は安定プロフィールなので、session / speaker 単位の精密な保存が向いています
- L2 は検索可能な経験記憶なので、metadata ベースのフィルタリングが拡張しやすいです
- その結果、L1 は精密さ、L2 は柔軟さを保てます

## 使い方

1. このプラグインをインストールして有効化します。
2. このプラグインの KnowledgeEngine を使って memory knowledge base を 1 つ作成します。
3. 次の項目を設定します。
   - `embedding_model_uuid`
   - `isolation`
   - 任意で `recency_half_life_days`
   - 任意で `auto_recall_top_k`
4. Agent には次を使わせます。
   - `remember`: イベント、予定、状況的な事実の保存
   - `recall_memory`: 自動想起が不十分なときの能動的な記憶検索
   - `update_profile`: 安定した好みやプロフィール情報の保存
   - `forget`: ID 指定でエピソード記憶を削除
5. `!memory`、`!memory profile`、`!memory search <query>`、`!memory list [page]`、`!memory forget <id>`、`!memory export` で状態を確認します。

## 他プラグイン向けのコンテキスト共有

LongTermMemory は各 `PromptPreProcessing` イベントで、構造化したコンテキスト要約を query variable `_ltm_context` に書き込みます。他のプラグインは LongTermMemory のコードを直接参照せずに、この変数を読んでユーザー記憶に基づく処理を行えます。

### 変数キー

`_ltm_context`

### スキーマ

```python
{
    "speaker": {
        "id": "user_123",           # sender_id。空文字のこともある
        "name": "Alice",            # sender_name。空文字のこともある
    },
    "session_profile": {            # 常に存在するが、各フィールドは空のことがある
        "name": "",
        "traits": ["creative", "analytical"],
        "preferences": ["prefers detailed explanations"],
        "notes": "",
        "updated_at": "2025-03-16T12:00:00Z",
    },
    "speaker_profile": {            # sender_id が使えない場合は null
        "name": "Alice",
        "traits": ["extroverted"],
        "preferences": ["likes humor"],
        "notes": "",
        "updated_at": "2025-03-16T12:00:00Z",
    },
    "episodes": [                   # 自動想起された L2 エピソード記憶。空のこともある
        {"content": "User mentioned a trip to Beijing last week"},
    ],
}
```

### 使用例

```python
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.provider.message import Message


class PersonalityCustomizer(EventListener):
    def __init__(self):
        super().__init__()

        @self.handler(events.PromptPreProcessing)
        async def on_prompt(event_ctx: context.EventContext):
            ltm = await event_ctx.get_query_var("_ltm_context")
            if not ltm:
                # LongTermMemory が未導入または無効ならデフォルト動作に戻す
                return

            profile = ltm.get("speaker_profile") or ltm.get("session_profile") or {}
            traits = profile.get("traits", [])

            if "喜欢幽默" in traits:
                style = "Use a humorous and playful tone."
            elif "偏好简洁" in traits:
                style = "Be concise and direct."
            else:
                return

            event_ctx.event.default_prompt.append(
                Message(role="system", content=style)
            )
```

### 設計メモ

- LongTermMemory が未インストールなら `_ltm_context` は存在しません。利用側プラグインは `None` を通常ケースとして扱い、デフォルト挙動に戻るべきです。
- LongTermMemory が有効でもまだプロフィールが無い場合、変数自体は存在しますがフィールドが空です。これにより「未導入」と「導入済みだがデータ未作成」を区別できます。
- 両者は変数キーと schema の約束だけに依存し、相互のコードには依存しません。将来 LongTermMemory を別実装の記憶プラグインに差し替えても、同じキーと schema を書く限り利用側はそのまま動きます。
- Event の実行順では LongTermMemory が利用側プラグインより先に動く必要があります。実際にはプラグインのインストール順に左右されます。

## インポート / エクスポート

- **エクスポート（L1 プロフィール）:** `!memory export` コマンドで、現在の scope に属する session profile / speaker profile を JSON として出力できます。他の session / scope のデータは含まれません。
- **インポート（L2 エピソード記憶）:** LangBot の知識ベース UI から JSON ファイルをアップロードして、エピソード記憶を一括インポートできます。
- **L2 エピソード記憶は一覧可能です:** `!memory list [page]` でページ単位の閲覧ができ、`!memory forget <id>` で個別削除もできます。完全な一括エクスポートはまだ実装していません。

## 重要な技術 Q&A

### Q1. なぜ L1 と L2 を分けるのですか？

アクセスパターンが違うからです。

- L1 は安定事実なので毎回安定して注入したい
- L2 は出来事記憶なので必要時に検索したい

両方をベクトル DB にまとめると、安定プロフィールの再現性が落ち、更新の意味も曖昧になります。

### Q2. なぜ L2 を毎回全部注入しないのですか？

L2 は時間とともに増え続けるからです。全部入れると:

- prompt がすぐ膨らむ
- ノイズが増える
- 本当に関係ある記憶が埋もれる

そのため、まず少数の関連記憶だけを自動 recall し、足りなければ `recall_memory` を使います。

### Q3. L2 には時間減衰がありますか？

あります。

L2 の順位付けはベクトル類似度だけでなく、時間減衰も考慮します。新しい記憶ほど上位に来やすく、古い記憶は徐々に順位上の優位を失います。

現在の実装は half-life 型です。

- 記憶が `half_life_days` に達すると、時間重みはおよそ 50% まで下がります
- 新しい記憶ほど順位上有利です
- 古い記憶も自動削除はされず、単に優先度が下がるだけです

### Q4. 古い記憶は完全に消えますか？

自動では消えません。

時間減衰は順位に効くだけで、ハード削除ではありません。十分に関連していれば、古い記憶も再度ヒットします。

### Q5. `session` と `bot` はどう選べばよいですか？

実運用では次のように考えると分かりやすいです。

- `session`
  - 各会話を独立した記憶空間として扱いたい
  - セッション間の混線リスクを低くしたい
- `bot`
  - bot が複数セッションを横断して経験を共有したい
  - より広い recall を優先したい

迷うなら、まずは `session` から始めるのが無難です。

### Q6. なぜ `!memory export` は現在の scope だけなのですか？

これは安全境界として意図的にそうしています。

もしプラグインインスタンス全体の全 L1 を簡単に出力できると、セッションをまたいだデータ漏えいが起きやすくなります。現在の scope に限定することで露出面を最小化しています。

### Q7. `_knowledge_base_uuids` が query variables に無いと何が起こりますか？

自動記憶注入そのものは動きますが、自分の memory KB を naive RAG 前処理対象から外せなくなります。

すると:

- LongTermMemory 自身が 1 回注入する
- runner 側の一般的な知識ベース処理でもう 1 回同じ内容が引かれる

完全に壊れるわけではありませんが、コンテキストが冗長になりノイズが増えます。

### Q8. なぜ L2 の一括エクスポートはまだ無いのですか？

SDK はすでに `vector_list` API を提供しており、これにより L2 エピソード記憶をページ単位で列挙できるようになりました。LongTermMemory は `!memory list [page]` で閲覧し、`!memory forget <episode_id>` や `forget` ツールで個別削除できます。

ただし、完全な一括エクスポート機能自体はまだ実装していません。

### Q9. AgenticRAG と一緒に使うと二重に recall されませんか？

その重複を避けるのが現在の設計です。

- LongTermMemory は naive RAG 前処理から自分の KB を外します
- 自動 L2 recall は LongTermMemory が担当します
- さらに必要なら AgenticRAG から明示的に query できます

## メモリコンソール

`!memory` コマンドに加えて、本プラグインは視覚的な確認とメンテナンスのための Web 版**メモリコンソール**ページ（プラグインの Page コンポーネントとして登録）を同梱しています。スコープで制限されたページエンドポイント経由でプラグインと通信し、選択中のメモリ空間を越えて操作することはありません。

コンソールは「メモリ空間サイドバー」と複数のタブで構成されます：

- **メモリ空間サイドバー** —— 既存のスコープを選ぶか、`bot_uuid` / `session_name` / `isolation` を入力して **Derive** をクリックすると、対応する `scope_key` と `user_key` を計算します。「Advanced / Raw」領域では内部キーを直接編集できます。
- **プロファイル** —— 選択中スコープのセッションプロファイルと現在の話者プロファイルを表示します。
- **情景記憶** —— 現在の `user_key` の L2 情景記憶をページ単位で一覧・意味検索し、ライフサイクル状態で絞り込み、各レコードをその場でアーカイブ・復元・削除できます。各更新操作は対応する `!memory` コマンドと同様にスコープ付き監査エントリを書き込みます。
- **注入スナップショット** —— そのスコープの**直近のメモリ注入スナップショット**を読み込みます：今回注入したか、ブロック数と文字数、話者、使用したプロファイル、自動召喚された L2 情景記憶。ログを漁らずに「ボットが前回何を覚えていたか」を確認できます。
- **監査** —— スコープ付き監査ログをページ単位で閲覧・エクスポートします。
- **エクスポート** —— 現在のスコープの L1 プロファイルと L2 情景記憶を JSON でエクスポートします。
- **診断** —— **ヘルスチェック実行**で、`!memory health` と同じ metadata 分離プローブ（KB 設定、埋め込みモデル、search / list / delete における `user_key` フィルタ分離）を UI から直接実行し、赤/黄/緑のステータスカードで表示します。注意：コンソールは KB が特定のパイプラインに接続されているかを検証できません。その点はパイプライン内で `!memory health` を実行して確認してください。

コンソールは i18n 対応（`en_US`、`zh_Hans`）で、ホスト LangBot のライト/ダークテーマに追従します。

## コンポーネント

- KnowledgeEngine: [memory_engine.py](../components/knowledge_engine/memory_engine.py)
- EventListener: [memory_injector.py](../components/event_listener/memory_injector.py)
- Tools: [remember.py](../components/tools/remember.py), [recall_memory.py](../components/tools/recall_memory.py), [update_profile.py](../components/tools/update_profile.py), [forget.py](../components/tools/forget.py)
- Command: [memory.py](../components/commands/memory.py)
- Page: [memory_console.py](../components/pages/memory_console/memory_console.py), [index.html](../components/pages/memory_console/index.html)

## 今後の補足候補

README では中核設計、隔離ルール、エクスポート境界、主要コンポーネントをすでにカバーしています。

今後さらに足すなら:

- 多言語 README の同期更新
- JSON インポート例
- `remember` / `recall_memory` / `update_profile` / `forget` のベストプラクティス例
