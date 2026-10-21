| Native EBA LINE Adapter — 架構說明文檔 |

<!-- 置於 LangBot 工作樹 docs/event-based-agents/
     依任務 WO-LINE-07（b）撰寫 LINE Adapter 專屬架構說明。
     coder 文件交付；程式碼落地見 README.md 落地指引。 -->

## 1. 定位

Native EBA LINE Adapter 是 LangBot 的 **原生 Event-Based Agent 線上平台適配器**，
讓 LINE 成為 LangBot 的一個 native 源（source），直接接入 EBA 的
`MessageChain` 抽象與平台事件分發機制。

核心原則：**框架對平台不可見，平台對框架可插拔** — 一套業務邏輯跨
Telegram / Slack / LINE 移植。

---

## 2. 目錄結構

```
pkg/platform/adapters/line/
├── __init__.py                     # 包初始化
├── manifest.py                     # 插件 manifest（source name / 能力宣告）
├── types.py                        # 事件 / payload 类型契约
├── platform_api.py                 # 平台能力 interface 契约
├── adapter.py                      # LineAdapter（AbstractPlatformAdapter 抽象基底）
│   ├── get_supported_events() / get_supported_apis()   # 能力宣告（未實測不宣告）
│   ├── send_message()              # push_message 主動推播
│   └── （image.received / flex.send 等）
├── api_impl.py                     # SDK 存取抽象（retry 包裝 / 解耦）
├── event_converter.py              # LINE event → EBA payload（_sdk_to_payload staticmethod）
│   └── _platform_specific()        # 事件分派到 platform.<namespace>
├── message_converter.py            # EBA MessageChain ↔ LINE payload 雙向
├── send_api.py                     # LineSendApi（reply/push/flex + RetryPolicy）＋ Flex 卡片族
├── streaming.py                    # LineStreamClient（WebSocket 骨架）＋ LineStreamOutput（打字機）
└── test_*.py                       # 各域 boxed selftest
```

---

## 3. 入站資料流（LINE → EBA）

```
LINE SDK event
  ├─ MessageReceivedEvent ────────────────────────────────────────────────────────────────────────────────────────
  │    _sdk_to_payload() ──▶ PlatformPayload(sender, chat_type, chat_id, source, …)
  │    _platform_specific(type="message.received") ──▶ platform.message.received
  │
  ├─ FollowEvent ──▶ _platform_specific("user.followed")
  │  UnfollowEvent ──▶ _platform_specific("user.unfollowed")
  │  JoinEvent   ──▶ _platform_specific("group.joined")
  │  LeaveEvent  ──▶ _platform_specific("group.left")
  │  PostbackEvent ──▶ _platform_specific("platform.specific.postback")
  │  BeaconEvent ──▶ _platform_specific("platform.specific.beacon")
  │
  ├─ ImageMessage ──▶ _platform_specific("image.received") ──▶ adapter.download_message_content()
  │  Audio/F ──▶ download_message_content()
  │
  └─ Message.edited / ──▶ 未實測，不宣告（architect 紅線）
     Feedback / group.* 
```

---

## 4. 出站資料流（EBA → LINE）

```
EBA MessageChain（Plain/At/Image/… / platform.Component）
  └─ yiri2target() ──▶ LINE payload dict
        ├─ text       → {"type":"text","text":...}
        ├─ image      → {"type":"image","original_content_url":...,"preview_image_url":...}
        ├─ flex 卡片  → {"type":"flex","alternative_text":...,"flex":{…bubble/carousel…}}
        └─ PlatformComponent(line) → flex payload（走 send_flex 承接）
  └─ LineSendApi
        ├─ reply_message()   ← 被動回覆快速通道（ReplyToken；過期 Smoothly 轉 Push）
        └─ push_message()    ← 主動推播
```

**Flex Message 卡片族（`send_api.py` 純量建構，零 SDK 依賴）**：
`FlexText / FlexBox / FlexButton / FlexBubble / FlexCarousel / FlexImage / FlexCard`
＋ `flex_message_object/list/from_bubbles / flex_container / send_flex`。

---

## 5. 能力宣告與實測分界

```python
get_supported_events()  # 未實測事件不宣告（architect 紅線）
get_supported_apis()
```

| 能力 | 狀態 | 分界依据 |
|------|------|----------|
| message.received / send / reply | ✅ 已收發閉環 | WO-LINE-01/02 + ops selftest |
| group.* / user.* 事件映射 | ✅ 映射框架 | WO-LINE-04（event_type 实值据 ops .84 SDK 實測） |
| image.received / download_content | ✅ 框架 | WO-LINE-05 |
| flex.send | ✅ 框架 | WO-LINE-05 |
| get_group_summary / get_user_profile / … | ⚠️待實測 | SDK 實際調用未入箱 |
| streaming（WebSocket / 打字機） | ⚠️待實測 | blueprint §3.1/§407/§418，SDK Streaming 未入箱 |
| message.edited / feedback / beacon | 未宣告 | 未實測，禁宣告 capability |

---

## 6. 設定範例（Illustrative Schema ⚠️以 `.91` SDK 實測定稿為準，禁捏造）

憑據經 SDK 載入（不进版本库、零硬编码，§7 凭证红线）：

```yaml
# .env（示意框架，确切栏位据 SDK 定稿）
LINE_CHANNEL_ACCESS_TOKEN=<...>   # LineBotApi 客户端凭据
LINE_CHANNEL_SECRET=<...>         # webhook 附件/校验 WebhookContentProvider
```

接入形态（据 EBA AbstractPlatformAdapter 契约 + manifest 宣告）：

```python
from pkg.platform.adapters.line.adapter import LineAdapter
# LineAdapter(config=...) 注入 SDK 客户端（channel_access_token / channel_secret）
# 入站: LINE event → event_converter._sdk_to_payload → platform.<namespace>
# 出站: MessageChain → message_converter.yiri2target → LineSendApi push/reply/flex
```

> ⚠️ 确切 config 栏位／注册 API 据 `.91` SDK 实测定稿后由 ops 落箱校准（§9/§23）。

---

## 7. 紀律

- **零硬編碼**：env/secret 一律 `os.getenv`；可變參數不寫死（§7）。
- **SDK 禁捏造**：未實測 SDK 調用一律留痕 ⚠️待實測（§9/§23）。
- **未實測不宣告 capability**（architect 紅線）。
- **boxed 解耦**：selftest 零 SDK 依賴，据 repo 框架就位時測或不測（§9）。
- **CLI/落地歸 ops**：py_compile/selftest/pytest/git commit 由 ops 池執行（§4/§7）。

---

## 8. 落地與 CI（ops）

```
cd <repo>/src/langbot
python -m pkg.platform.adapters.line.test_selftest          # WO-LINE-02（17/17 含 04 殘題）
python -m pkg.platform.adapters.line.test_send_streaming    # WO-LINE-03
python -m pkg.platform.adapters.line.test_group_user_events # WO-LINE-04
python -m pkg.platform.adapters.line.test_multimodal_flex   # WO-LINE-05
```

全量 exit 0 + Ruff/flake8 零 lint + pytest 全綠 → 封 PR（§22 結案報告自動化）。
