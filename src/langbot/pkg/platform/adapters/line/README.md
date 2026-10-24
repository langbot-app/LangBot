# WO-LINE-02 — message.received 收發閉環（LINE EBA Adapter）

**狀態**：〔草案／審閱單〕非執行指令。coder 端 staging 交付件（SOUL §4：仅代码层），待 ops 载入 worktree `feat/line-adapter-skeleton-1018` → py_compile + ruff + 落地 + 取 sha。

## 交付檔（staging `pkg/platform/adapters/line/`）

| 檔 | 狀態 | 變更範圍（相鄰 WO-LINE-01 骨架） |
|----|------|------|
| `adapter.py` | ✅ 填實 | `_handle_native_event`（自我过滤+EBA分发）、`send_message`/`reply_message`、`_sdk_push_message`/`_sdk_reply_message`（据 SDK 3.26.0 合约 §2.2 实作，确切待测）；`run_async`/`kill` 沿用骨架 |
| `event_converter.py` | ✅ 填實 | `target2yiri` 分發式分发；`_convert_message`→`MessageReceivedEvent`；`_sdk_to_payload`（唯一 SDK 歸一化封裝，据 SDK 3.26.0 合约 §1.2 确认 staticmethod 契约一致） |
| `message_converter.py` | ✅ 填實 | `LineMessageConverter.target2yiri`（LINE dict→MessageChain）、`yiri2target`（MessageChain→LINE payload） |
| `errors.py` | ✅ 新建 | `NotSupportedError`（照 slack/officialaccount 模式，try import SDK 回退本地） |
| `api_impl.py` | 沿用 | 不改（`call_platform_api` 透傳） |
| `platform_api.py` | 沿用 | 不改（空映射，未實測不声明） |
| `types.py` | 沿用 | 不改 |
| `manifest.yaml` | 沿用 | 不改（`message.received`/`send_message`/`reply_message` 已在位） |

## 對照 boxed 契約（禁捏造來源）

- 事件：`MessageReceivedEvent`（`01-event-system.md` §3.2）— `type`/`message_id`/`message_chain`/`sender`/`chat_type`/`chat_id`/`group`＋基類 `timestamp`/`adapter_name`/`source_platform_object`。
- 訊息元件：`PlatformMessage` `Source/Plain/At/AtAll/Image/Voice/File/Forward/Quote/Unknown`（`02-platform-api.md` §6.1）。**無 Video 通用元件** → LINE Video/Sticker 走 `PlatformComponent`（doc 6.2）。
- 分发：照 slack `adapter.py` 187-218（native handler → `target2yiri` → `_dispatch_eba_event`）+ telegram 506-512。
- 自我消息过滤（防回圈）＝ acceptance-checklist 紅線。

## 收發閉環流程

```
LINE webhook ──▶ _handle_native_event(raw)
                 ├─ _sdk_to_payload(raw)          ⚠️待實測（唯一 SDK 存取）
                 ├─ 自我消息过滤（sender.id == bot_account_id）  # acceptance 红线
                 ├─ 注入 content_provider
                 └─ LineEventConverter.target2yiri(ev)
                        ├─ _convert_message ─▶ MessageChain（LineMessageConverter.target2yiri）
                        └─ MessageReceivedEvent ─▶ _dispatch_eba_event ─▶ listener ─▶ EventBus
```

出發（bot 发消息）：`send_message`/`reply_message` → `LineMessageConverter.yiri2target` → LINE payload → `_sdk_push_message`/`_sdk_reply_message`（据 SDK 3.26.0 合约 §2.2 实作，确切待测）。

## SDK 3.26.0 合约验收状态（ops .84 CubeSandbox 實測）

据 `WO-LINE-00-SDK-326-CONTRACT.md`（2026-10-20，核心功能驗收通過）：

1. ✅ `_sdk_to_payload` —— staticmethod 契约一致（coder 二轮修正，据 §1.2 确认）。
2. ✅ `replyToken` —— 实测直接於事件物件 `.reply_token` / `.message.reply_token` 取得（§1.1）。
3. ✅ SDK 物件分支存取（`.body.events/.destination/.webhookEventId/.sender`）据 §1.2 确认。
4. ✅ `_sdk_push_message`/`_sdk_reply_message` —— 确认为 SDK `LineBotApi.push_message()` / `reply_message()`（§2.2）；确切调用参数据 v3 API 惯例，供 ops 实测。
5. ✅ 附件下載 `MessagingApiBlobClient.download_b64(message_content_id)` —— 签名实测确认（§2.4）。
6. ⚠️ SDK client / `WebhookContentProvider` 建構（`_build_client`/`_build_content_provider`）—— 据 §2.1 / `WebhookContentProvider` 据合约骨架留（确切待测）。
7. ⚠️ follow/unfollow/leave/join 的 EBA 事件映射（deferred to WO-LINE-05；今走 `platform.specific`）。

## ops 落地指令（待派發）

```
# worktree feat/line-adapter-skeleton-1018 已就位（基線 master edd6cad，commit 10fbed43）
cp -R pkg/platform/adapters/line/* <worktree>/src/langbot/pkg/platform/adapters/line/
# ① py_compile（注意：types.py 遮蔽標準庫 types，cwd 在 line/ 內跑 py_compile 假失敗，屬慣例）
# ② ruff（repo 配置 E4/E7/E9/F）
# ③ import 鏈實測：LineAdapter MRO → LineAPIMixin → AbstractPlatformAdapter（容器 v4.11-hotfixed SDK）
# ④ git add + 取 sha（落地 protocol/ 前须先备份 protocol/ Phase3 skill_proposal.py sha 110279f8）
```

自測：`python -m langbot.pkg.platform.adapters.line.selftest_message_loop`（据 ops 此前纠正，勿直接跑 `python <path>`）；仅测非 SDK 依赖的纯逻辑：`_sdk_to_payload` dict 分支、`target2yiri`、`message_converter` 两向；需在 repo 环境跑，SDK 在位。据 SDK 3.26.0 合约，`_sdk_to_payload` dict 分支 + 归一化 dict 逻辑可独立验证。

*本檔為 staging 产出，非落地。框架契约（✅ boxed 實測）已引用；LINE 端 ⚠️ 待實測项已逐档标注，禁未定案线程直接落地。*
