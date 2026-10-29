# LongTermMemory

LangBot 的長期記憶插件，採用雙層設計：

- L1 核心設定檔 (Core profile)：注入到系統提示詞中
- L2 片段記憶 (Episodic memory)：透過向量搜尋檢索並注入到上下文

## 功能特性

- 提供 `remember` 工具：用於寫入片段記憶
- 提供 `recall_memory` 工具：用於帶有受控篩選條件的主動片段記憶查詢
- 提供 `update_profile` 工具：用於穩定的設定檔更新
- 提供 `forget` 工具：用於智能體發起的特定片段記憶刪除
- 透過 EventListener 注入設定檔記憶和當前發言者身份
- 使用 EventListener 在模型調用前檢索並注入相關的片段記憶
- 提供 `!memory` 指令：用於檢查和調試
- 提供 `!memory list [page]` 指令：分頁瀏覽片段記憶
- 提供 `!memory forget <episode_id>` 指令：刪除特定片段記憶
- 提供 `!memory search <query>` 指令：搜尋片段記憶（結果包含片段 ID）
- 提供 `!memory export` 指令：將當前會話的 L1 設定檔匯出為 JSON
- 當存儲校正/事實更新/澄清時，自動取代相關的舊片段

## 整體設計

此插件並非試圖將整個對話歷史傾印到上下文中。相反，它將長期記憶分為具有不同存儲和檢索行為的兩層：

- **L1 核心設定檔**：穩定的、低頻率的事實，如姓名、偏好、身份和長期筆記
- **L2 片段記憶**：具時效性和情境性的事實，如最近發生的事件、計劃和經歷

這種劃分是有原因的：

- 穩定的設定檔數據注入到系統提示詞中既便宜又可靠
- 片段記憶隨著時間不斷增長，因此應根據需求檢索，而不是每輪都完整注入
- 智能體更新穩定設定檔事實的方式應與更新事件類記憶的方式不同

## 與 OpenClaw 風格個人助手記憶的區別

最近，許多智能體系統討論了類似 OpenClaw 的設計：長期記憶主要存儲為用戶可讀的文本文件（如 `MEMORY.md`），並結合摘要、反思和輕量級檢索邏輯。

該方法具有明顯的優勢：

- 記憶對用戶完全透明
- 純文本自然易於備份、同步和版本控制
- 非常適合單用戶、單助手、高連續性的個人工作流
- 當記憶量較小時，全文理解確實「夠用了」

但 LangBot 中的 LongTermMemory 解決的是不同的問題。典型的 LangBot 部署更像是：

- 一個機器人服務於多個群聊和私聊
- 一個插件實例處理多個會話和多個發言者
- 記憶包括共享的群組上下文、當前發言者設定檔和會話級片段事實
- 會話、機器人和發言者之間有明確的隔離邊界

因此，我們沒有採用「以單個文本文件作為事實來源」的設計。我們選擇了更符合 LangBot 多會話運行時模型的層次化架構。

### 類似 OpenClaw 的記憶優化目標

抽象地說，該設計優化了：

- **單用戶個人助手**
- **以人類可讀文本作為主要長期記憶形式**
- **透明度、可編輯性和敘事連續性**
- **假設記憶大小保持在可控範圍內，且用戶願意直接維護它**

這非常適合個人 AI 伴侶、研究副手和私人助手工作流。

### 為什麼 LangBot 不簡單複製該模型

LongTermMemory 是圍繞不同的運行限制設計的：多會話、多發言者、明確隔離、受控注入和可檢索的片段回想。

如果我們將長期記憶變成像 `MEMORY.md` 這樣的敘事性文件，很快就會出現幾個問題：

- **隔離變得困難**
  - 群組 A、群組 B 和私聊 C 的記憶如何安全共存？
  - 如何乾淨地將單個發言者的穩定設定檔與共享的敘事日誌分開？
- **注入粒度變得不穩定**
  - 系統提示詞需要穩定的設定檔狀態，而不是完整的年代記日誌
  - 自動回想需要針對當前查詢最相關的記憶切片，而不是整個故事
- **多用戶邊界在 LangBot 中是一等公民**
  - 在個人助手中心，「用戶」通常是一個人
  - 在 LangBot 中，當前發言者、當前會話和當前機器人都很重要
- **自動注入和主動檢索是不同的需求**
  - 穩定設定檔數據應一致地注入
  - 片段記憶應選擇性地檢索
  - 強行將兩者放入一個純文本記憶形式會變得很尷尬

### 我們所做的權衡

因此，LongTermMemory 的設計本質上是這種權衡：

- **我們借鑒了哪些哲學**
  - 記憶不應僅被視為黑盒向量存儲
  - 穩定設定檔、時間記憶和長期行為調整都很重要
  - 並非所有內容都應在每輪都傾印到上下文中

- **我們刻意區別的地方**
  - 我們不使用敘事文本日記作為唯一的記憶事實來源
  - 我們明確劃分了穩定設定檔和片段記憶
  - 我們優先考慮跨會話、發言者和機器人的隔離
  - 我們讓 L2 記憶自然地接入 LangBot 的知識庫/檢索系統，而不僅僅依賴全文閱讀

簡而言之：

- OpenClaw 主要回答：「個人助手應如何保持可讀、可編輯、具反思性的長期記憶？」
- LongTermMemory 主要回答：「在明確的隔離規則下，跨群組和私聊工作的機器人應如何保持穩定的設定檔狀態和可檢索的經驗記憶？」

這兩種方向都沒有絕對的「優劣」。它們針對不同的產品和不同的失效模式進行了優化。

## 設計

本插件特意貼近 LangBot 現有的擴展點，而不是要求自定義核心補丁。

- L1 設定檔作為 JSON 存儲在插件存儲中
- L2 片段記憶存儲在向量數據庫中
- 通過附加此插件的 KnowledgeEngine 為每個管道啟用記憶檢索
- 插件目前假設每個插件實例使用單個記憶知識庫，並透過元數據隔離記憶

目前的實現是基於現有的 LangBot 和 SDK API。如果 LangBot 以後添加了更多明確的面向記憶的 API、會話身份 API 或知識庫註冊 API，插件可以簡化，但目前的架構仍然有效。

### 向量數據庫後端兼容性

L2 片段記憶依賴於任意元數據欄位（`user_key`、`episode_id`、`tags`、`importance` 等）進行隔離和過濾。並非所有 LangBot 向量數據庫後端都支持任意元數據：

| 後端 | 任意元數據 | LongTermMemory 支持 |
|---------|-------------------|----------------------|
| **Chroma** (預設) | 是 | 完全支持 |
| **Qdrant** | 是 | 完全支持 |
| **SeekDB** | 是 | 完全支持 |
| **Milvus** | 否 (固定 schema: `text`, `file_id`, `chunk_uuid`) | 不支持 |
| **pgvector** | 否 (固定 schema: `text`, `file_id`, `chunk_uuid`) | 不支持 |

Milvus 和 pgvector 使用固定的列 schema，並會靜默捨棄它們不認識的元數據欄位。這意味著基於元數據的隔離（`user_key` 過濾）和片段記憶指令（`!memory list`、`!memory forget`、`!memory search`）在這些後端上將無法正常工作——過濾器將被忽略，查詢可能會返回不受限的結果。

如果您需要使用 LongTermMemory，請使用 Chroma、Qdrant 或 SeekDB 作為您的向量數據庫後端。

## 工作原理

一個端到端的長期記憶流程包含四個主要部分：

### 1. L1 設定檔寫入

- 智能體使用 `update_profile` 寫入穩定事實
- 數據作為結構化 JSON 存儲在插件存儲中
- 設定檔存儲在 `session`（會話）或 `speaker`（發言者）範圍內

### 2. L2 片段寫入

- 智能體使用 `remember` 寫入事件類記憶
- 每條記憶都帶有時間戳、重要性、標籤和範圍等元數據
- 這些記憶透過插件的 KnowledgeEngine 進行向量化並存儲在向量數據庫中

### 3. 回應前的自動注入

- 在 `PromptPreProcessing` 期間，EventListener 解析當前會話身份
- 對於 L1：
  - 加載共享的會話設定檔
  - 加載當前發言者設定檔
  - 將兩者以及當前發言者身份注入到 `default_prompt`
- 對於 L2：
  - 使用當前用戶消息運行一次片段檢索
  - 檢索到的記憶作為事實上下文塊注入

因此，L1 和 L2 都會在答案生成前進入模型上下文，但形式不同：L1 作為系統提示詞記憶，L2 作為檢索到的上下文。

### 4. 主動查詢和調試

- 如果自動注入不足，智能體可以調用 `recall_memory`
- 對於檢查和調試，可以使用 `!memory`、`!memory profile`、`!memory search`、`!memory list` 和 `!memory forget`
- `!memory export` 僅匯出當前範圍的 L1 設定檔，用於備份或遷移

## 與 AgenticRAG 的關係

當 AgenticRAG 與 LongTermMemory 同時啟用時：

- LongTermMemory 會從常規 RAG 預處理中移除自己的記憶知識庫
- 自動 L2 回想仍由 LongTermMemory 自身處理
- 同一個記憶知識庫仍可透過 AgenticRAG 的 `query_knowledge` 工具進行顯式查詢

這避免了重複回想，同時保留了兩條路徑：

- 自動記憶回想
- 需要時由智能體發起的更深入檢索

## 為什麼沒有智能體端元數據過濾器

底層運行時可以支持元數據過濾，但本插件目前未向智能體流程開放任意原始元數據過濾器。

原因：

- 不同的知識引擎和向量後端不共享統一的元數據 schema
- 過濾器欄位名稱、值格式和支持的運算符可能有所不同
- 智能體目前沒有穩定的 schema 來源來構建可靠的過濾器

如果 LangBot 後來提供了一種統一的方式來描述每個知識庫的可過濾元數據欄位，則可以添加智能體端元數據過濾。

本插件確實為其自身的穩定記憶 schema 提供了一個受控的回想工具接口。該工具支持選定的過濾器（如發言者和時間範圍），而不會向模型暴露特定於後端的自由格式過濾語法。

## 隔離模型

支持兩種隔離模式：

- `session`：每個群聊或私聊擁有獨立的記憶
- `bot`：同一個機器人下的所有會話共享記憶

在當前的部署模型中，這通常已經足夠，因為插件實例通常綁定到特定的 LangBot 運行時/機器人環境。

## 隔離規則詳解

本插件中有兩個相關但略有不同的範圍概念：

- **session_name**：透過當前查詢/檢索路徑傳遞的對話身份，格式為 `{launcher_type}_{launcher_id}`
- **session_key**：插件內部的 L1 存儲鍵。當 `bot_uuid` 可用時，它變為 `{bot_uuid}:{launcher_type}_{launcher_id}`；否則退回到 `{launcher_type}_{launcher_id}`
- **scope_key / user_key**：用於設定檔存儲或 L2 檢索隔離的實際鍵

### L1 設定檔如何隔離

L1 設定檔始終存儲在當前對話範圍內：

- `session profile` (會話設定檔)
  - 當前對話的共享設定檔
  - 對於群組級別或對話級別的穩定上下文很有用
- `speaker profile` (發言者設定檔)
  - 關於當前發言者的穩定事實
  - 對於特定個人的偏好、身份和筆記很有用

因此，`!memory export` 僅匯出屬於當前 `session_key` 的設定檔，而不是插件實例中的每個設定檔。

### L2 片段記憶如何隔離

L2 記憶帶著隔離元數據寫入向量存儲，然後在檢索時進行過濾：

- `session`
  - 群組 A 的記憶不會在群組 B 中被回想
  - 一個私聊的記憶不會在另一個私聊中被回想
- `bot`
  - 同一個機器人下的所有會話共享一個片段記憶空間
  - 當您希望跨會話共享長期經驗時很有用

當 `sender_id` 可用時，插件還可以在擴展到更廣泛範圍之前，優先考慮與發言者相關的記憶。

### 為什麼 L1 和 L2 隔離不完全相同

這是刻意為之：

- L1 的行為類似於穩定的設定檔狀態，因此精確的會話/發言者存儲是有意義的
- L2 的行為類似於可檢索的經驗庫，因此基於元數據的過濾是更具擴展性的模型
- 這使得 L1 保持精確，而 L2 保持靈活

## 如何使用

1. 安裝並啟用插件。
2. 使用此插件的 KnowledgeEngine 創建一個記憶知識庫。
3. 配置：
   - `embedding_model_uuid`
   - `isolation`
   - 選填 `recency_half_life_days`
   - 選填 `auto_recall_top_k`
4. 讓智能體使用：
   - `remember` 用於事件、計劃和片段事實
   - `recall_memory` 用於自動回想不足時的主動記憶查詢
   - `update_profile` 用於穩定的偏好和設定檔數據
   - `forget` 用於透過 ID 刪除特定的片段記憶
5. 使用 `!memory`、`!memory profile`、`!memory search <query>`、`!memory list [page]`、`!memory forget <id>` 和 `!memory export` 來檢查行為。

## 為其他插件共享上下文

LongTermMemory 在每次 `PromptPreProcessing` 事件期間將結構化的上下文摘要寫入查詢變量 `_ltm_context`。其他插件可以讀取此變量，根據用戶記憶做出程序化決策，而無需以任何方式導入或引用 LongTermMemory。

### 變量鍵 (Key)

`_ltm_context`

### Schema

```python
{
    "speaker": {
        "id": "user_123",           # sender_id，可能為空字串
        "name": "Alice",            # sender_name，可能為空字串
    },
    "session_profile": {            # 始終存在，欄位可能為空
        "name": "",
        "traits": ["creative", "analytical"],
        "preferences": ["prefers detailed explanations"],
        "notes": "",
        "updated_at": "2025-03-16T12:00:00Z",
    },
    "speaker_profile": {            # 當 sender_id 不可用時為 null
        "name": "Alice",
        "traits": ["extroverted"],
        "preferences": ["likes humor"],
        "notes": "",
        "updated_at": "2025-03-16T12:00:00Z",
    },
    "episodes": [                   # 自動回想的 L2 片段記憶，可能為空
        {"content": "User mentioned a trip to Beijing last week"},
    ],
}
```

### 使用範例

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
                # LongTermMemory 未安裝或未啟用 — 使用預設值
                return

            profile = ltm.get("speaker_profile") or ltm.get("session_profile") or {}
            traits = profile.get("traits", [])

            if "喜歡幽默" in traits:
                style = "Use a humorous and playful tone."
            elif "偏好簡潔" in traits:
                style = "Be concise and direct."
            else:
                return

            event_ctx.event.default_prompt.append(
                Message(role="system", content=style)
            )
```

### 設計筆記

- 如果未安裝 LongTermMemory，則 `_ltm_context` 不存在。調用插件應將 `None` 視為正常情況並退回到預設行為。
- 如果 LongTermMemory 已啟用但尚未存儲設定檔數據，則該變量存在但欄位為空。這讓調用插件能夠區分「無記憶插件」和「記憶插件已啟用但尚無數據」。
- 雙方僅依賴於變量鍵和 schema 約定，而不依賴於彼此的代碼。如果 LongTermMemory 被另一個寫入相同鍵和相同 schema 的記憶插件取代，調用插件仍可繼續工作。
- 在事件分發順序中，LongTermMemory 必須在調用插件之前運行。實際上這取決於插件的安裝順序。

## 匯入 / 匯出

- **匯出 (L1 設定檔)：** 使用 `!memory export` 將當前範圍的會話和發言者設定檔匯出為 JSON。它不會匯出其他會話或範圍的數據。
- **匯入 (L2 片段記憶)：** 透過 LangBot 知識庫 UI 上傳 JSON 文件，以批量匯入片段記憶。
- **L2 片段記憶可以瀏覽**：透過 `!memory list [page]` 瀏覽，並透過 `!memory forget <id>` 刪除單個片段。目前尚未實現完整的批量匯出。

## 關鍵技術問答

### Q1. 為什麼將記憶分為 L1 和 L2，而不是將所有內容都存儲在向量數據庫中？

因為訪問模式不同：

- L1 包含穩定事實，應一致地注入
- L2 包含事件類記憶，應按需檢索

將兩者都放入向量存儲會使穩定設定檔的回想變得不太可靠，並使記憶更新在語義上變得混亂。

### Q2. 為什麼 L2 是檢索式的，而不是每輪都完整注入？

因為 L2 會隨著時間增長。完整注入很快會導致：

- 提示詞膨脹
- 太多無關的雜訊
- 舊記憶擠占了實際相關的上下文

目前的策略是自動檢索一個小的相關子集，如果智能體需要更多，則讓其使用 `recall_memory`。

### Q3. L2 記憶會隨時間衰減嗎？

會。

L2 排名不僅取決於向量相似度。它還應用了時間衰減，因此較新的記憶往往比舊記憶排名更高。

目前的實現採用半衰期式方法：

- 當記憶達到 `half_life_days` 時，其時間權重衰減至約 50%
- 較新的記憶在排名中更受青睞
- 舊記憶不會被自動刪除；它只是失去了排名優勢

這旨在優先考慮最近的上下文，而不是硬性刪除過去。

### Q4. 舊記憶最終會完全消失嗎？

不會自動消失。

時間衰減影響的是排名，而不是硬性刪除。如果舊記憶保持足夠的相關性，仍然可以被回想起來。

### Q5. 我應該如何在 `session` 和 `bot` 隔離之間做出選擇？

實踐中：

- 選擇 `session`
  - 當每個群聊/私聊應保持獨立記憶時
  - 當您希望降低跨會話洩漏風險時
- 選擇 `bot`
  - 當機器人應跨會話共享長期經驗時
  - 當廣泛的回想比嚴格的隔離更重要時

如果您不確定，請從 `session` 開始。

### Q6. 為什麼 `!memory export` 僅匯出當前範圍？

這是一個刻意的安全邊界。

允許匯出插件實例中的每個 L1 設定檔會使跨會話數據洩漏變得更容易。將匯出限制在當前範圍遵循最小暴露原則。

### Q7. 如果運行時未在查詢變量中公開 `_knowledge_base_uuids` 會發生什麼？

自動記憶注入仍然有效，但插件無法從常規 RAG 預處理中移除自己的記憶知識庫。

這可能導致重複的記憶回想：

- 一份由 LongTermMemory 自身注入
- 另一份由運行時的通用知識庫流程再次回想

因此這不是完全的失敗，但會浪費上下文並使提示詞變得更嘈雜。

### Q8. 為什麼目前不支持 L2 匯出？

SDK 現在提供了一個 `vector_list` API 用於向量存儲內容的分頁枚舉。片段記憶可以透過 `!memory list [page]` 瀏覽，並透過 `!memory forget <episode_id>` 或 `forget` 工具單個刪除。

完整的批量匯出尚未實現，但構建塊已經到位。

### Q9. 同時啟用 LongTermMemory 和 AgenticRAG 時會重複檢索嗎？

不會，目前的設計正是為了避免這種重複：

- LongTermMemory 移除自己的常規 RAG 預處理
- 自動 L2 回想由 LongTermMemory 處理
- 更深入的即時檢索仍可透過 AgenticRAG 進行

## 組件

- KnowledgeEngine：[memory_engine.py](components/knowledge_engine/memory_engine.py)
- EventListener：[memory_injector.py](components/event_listener/memory_injector.py)
- 工具：[remember.py](components/tools/remember.py), [recall_memory.py](components/tools/recall_memory.py), [update_profile.py](components/tools/update_profile.py), [forget.py](components/tools/forget.py)
- 指令：[memory.py](components/commands/memory.py)

## 目前差距

README 現在涵蓋了核心設計、隔離規則、匯出邊界和主要組件。

以後仍值得添加：

- 同步更新本地化文檔
- 具體的 JSON 匯入範例
- `remember`、`recall_memory` 和 `update_profile` 的最佳實踐範例

## 日誌

插件現在在關鍵的記憶生命週期點發出日誌，以便您可以觀察運行時如何使用長期記憶。

您將看到以下內容的日誌：

- 插件初始化和解析的記憶上下文
- `remember`、`recall_memory` 和 `update_profile` 工具調用
- 模型調用前的設定檔注入
- KnowledgeEngine 中的自動 L2 記憶檢索
- 片段記憶向量寫入、搜尋、批量匯入和刪除

典型的日誌訊息如下：

```text
[LongTermMemory] remember called: query_id=123 params_keys=['content', 'importance', 'tags']
[LongTermMemory] memory injection ready: query_id=123 kb_id=kb-1 scope_key=bot:xxx:group_123 sender_id=u1 block_count=2 prompt_chars=280
[LongTermMemory] engine retrieve called: collection_id=kb-1 top_k=5 session_name=group_123 sender_id=u1 bot_uuid=bot-1 query='user asked about travel plan'
[LongTermMemory] search_episodes completed: collection_id=kb-1 result_count=3 filters={'user_key': 'bot:bot-1:group_123'}
```
