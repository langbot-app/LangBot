# LINE Adapter（EBA skeleton）— WO-LINE-01-SKELETON-1018

原生 LangBot Native EBA LINE Adapter 骨架（藍圖 §3.3 第一階段）。

## 本階段产出（骨架）

| 檔 | 作用 | 状态 |
|---|---|---|
| `adapter.py` | `LineAdapter(LineAPIMixin, AbstractPlatformAdapter)` — 混血繼承 + Capability + 事件命名空間 + config 載入 | ✅ 骨架 |
| `event_converter.py` | `LineEventConverter`／`LegacyEventConverter` — 事件分發骨架 | ⚠️待實測 |
| `message_converter.py` | `LineMessageConverter` — 消息转换骨架 | ⚠️待實測 |
| `api_impl.py` | `LineAPIMixin` — call_platform_api 透傳骨架 | ✅ 骨架 |
| `platform_api.py` | `PLATFORM_API_MAP`（空） | ⚠️待實測 |
| `types.py` | `LineEventType` 事件类型常量骨架 | ⚠️待實測 |
| `manifest.yaml` | manifest（name/execution/config） | ⚠️待實測 |

## 關鍵設計（對齊 telegram/slack 實測範例）

- **混血繼承**：`LineAdapter(LineAPIMixin, AbstractPlatformAdapter)` — 对照 telegram `TelegramAdapter(TelegramAPIMixin, AbstractPlatformAdapter)` 與 slack `SlackAdapter(SlackAPIMixin, AbstractPlatformAdapter)`。
- **Capability 宣告**：`get_supported_events()`／`get_supported_apis()` — 依藍圖 §3.2，未實測事件/API 不声明（acceptance-checklist 红线）。
- **config 载入**：`channel_access_token`／`channel_secret` 取自 SDK-managed `config` dict（manifest 标 `sensitive:true`）—— **零硬编码、不落檔**（§7 憑證紅線）。
- **run_async**：polling 為預設骨架分支；WebSocket 流式须 architect 裁決（藍圖 ①✜）。
- **handler 注册**：`_register_native_handlers()`／`_handle_native_event()` 为钩子骨架；LINE SDK 事件类型待實測。

## ⚠️ 待實測（LINE 端 — 禁捏造，§9/§23）

- `line-bot-sdk` v3 實際 import 路徑与 client 建構（`_build_client`／`_build_content_provider`）。
- LINE 事件 JSON 字段 → 统一 Event 映射（`target2yiri` 及各 `_convert_*`）。
- LINE Messaging API 端點 → `PLATFORM_API_MAP`（send/reply/get 系列）。
- 流式 vs polling 裁決（architect ①✜）。

## ops 落地步骤（本端不碰 git / 不跑 CLI，§4/§7）

1. ops 在隔离分支 checkout（repo 在 LangBot 正式环境，SDK 在位）。
2. 载入本 staging 骨架至 `pkg/platform/adapters/line/`。
3. 跑 `py_compile` + `ruff`（request ③）—— 本端静态自檢已過（无语法/导入硬错误），但**真实 import 解析须在 SDK 在位环境验证**。
4. 全綠 → 取新 sha → 落地 `protocol/`（Phase 3 既有机制）。
5. ops 回件 → architect 据此推进 02/03。

## 静态自檢记录（coder，非 CLI；§4）

- `adapter.py` / `event_converter.py` / `message_converter.py` / `api_impl.py` / `platform_api.py` / `types.py` / `__init__.py`：语法/导入自檢 OK（runtime 静态检查零报错）。
- 真实 import（`langbot_pkg`／`langbot_plugin`／LINE SDK）须在 SDK 在位 repo 环境 compile 验证（ops）。
