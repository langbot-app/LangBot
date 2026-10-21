# WO-LINE-05 — 多模態媒體接收／Flex Message 彈性卡片擴充（EBA LINE Adapter）

**狀態**：〔deliverable／審閱單〕coder-1 staging 交付件（SOUL §4：仅代码层）。待 ops 载入 worktree → py_compile + ruff + import 链实测 + selftest + 取 sha。
**来源 repo**：`pkg/platform/adapters/line/`（基准 = WO-LINE-02-MESSAGE-LOOP-1018 staging）。
**blueprint §3.5**：未于本环境落盘为独立文件（疑为 architect session 内架构文件）；本 deliverable 据 **②任务规格 + WO-LINE-02 boxed 契约** 實作，SDK 存取一律 ⚠️待實測。

## 交付檔（staging `pkg/platform/adapters/line/`）

| 檔 | 狀態 | 變更範圍（相鄰 WO-LINE-02） |
|----|------|------|
| `send_api.py` | ✅ 新建 | Flex Message 純量封裝：`FlexText`/`FlexButton`/`FlexPostbackAction`/`FlexMessageAction`/`FlexImage`/`FlexBox`/`FlexBubble`/`FlexCarousel`／`flex_message_object`／`flex_message_list`／`send_flex`。零 framework / 零 SDK 依赖（boxed 可测）。 |
| `message_converter.py` | ✅ 改實 | `_LINE_SDK.download_message_content`（`MessagingApiBlobClient` 二進位下載，§2.4）；`download_b64` 斂為其委派（維持已實測行為）；`yiri2target` 偵測 flex `PlatformComponent` → 單一 flex 訊息；`target2yiri` image 走 `download_message_content`。 |
| `event_converter.py` | ✅ 改註 | `image.received` 子能力宣示／註解（`content_provider` 已 threaded，behavior 不变）。 |
| `adapter.py` | ✅ 改實 | `get_supported_events` 加 `image.received`；`get_supported_apis` 加 `flex.send`；新增 `send_flex()`（据 §2.2 push/reply，⚠️待實測）；import `send_api`。 |
| `test_multimodal_flex.py` | ✅ 新建 | `send_api` 純量構築恒测（无框架依赖）；`image.received`／flex `yiri2target`／capability 宣示据 repo 框架就位时测。 |
| `errors.py` | 沿用 | 不改（`NotSupportedError` 本地回退 + SDK 注入）。 |
| `api_impl.py` | 沿用 | 不改（`LineAPIMixin` 于 worktree 在位，本 staging 重交付）。 |

## 能力新增（②c 正式宣告）

- 事件：`message.received` ＋ `image.received`（image 類訊息 → `download_message_content` → `Image` 元件）。
- API：`send_message` / `reply_message` ＋ `flex.send`（Bubble / Carousel 彈性卡片）。

## SDK 存取邊界（唯一封裝點，⚠️待實測）

- 附件下載：`_LINE_SDK.download_message_content`（`MessagingApiBlobClient(message_content_id).download_message_content()`，§2.4）。
- Flex 發送：`adapter.send_flex` → `send_api.send_flex` → `_sdk_push_message` / `_sdk_reply_message`（`LineBotApi.push/reply`，§2.2）。
- 本 staging 档不引用任何 LINE SDK 實際名稱（禁捏造）；確切 API 参数供 ops 于 worktree 实测（§9）。

## ops 落地指令（待派發）

```
# worktree（基線 master，沿用 WO-LINE-02 feat/line-adapter-skeleton-1018 或新分支）
cp -R pkg/platform/adapters/line/* <worktree>/src/langbot/pkg/platform/adapters/line/
# ① py_compile（注意：types.py 遮蔽標準庫 types，cwd 在 line/ 內跑 py_compile 假失敗，屬慣例）
# ② ruff（repo 配置 E4/E7/E9/F）
# ③ import 鏈實測：LineAdapter MRO → LineAPIMixin → AbstractPlatformAdapter（容器 SDK 在位）
# ④ git add + 取 sha
```

## 自測（据 WO-LINE-02 selftest 惯例）

```
# repo 環境（langbot 框架 + SDK 在位）
cd <repo>/src/langbot
python -m pkg.platform.adapters.line.test_multimodal_flex
# send_api 純量構築恒测；image.received / flex yiri2target / capability 据框架就位测
```

## 已知 ⚠️待實測项

- `MessagingApiBlobClient` 建構 + `download_message_content` 确切签名（§2.4）。
- Flex Message push/reply 确切 payload（`contentType: application/json` + `data` 容器）。
- `image.received` 的 SDK 事件 JSON 与 `content_provider.get(message_id)` 返回字节形态。

*本檔為 staging 产出，非落地。框架契约（✅ boxed 實測）已引用；LINE 端 ⚠️待實測项已逐档标注，禁未定案线程直接落地。*
