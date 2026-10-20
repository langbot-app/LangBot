"""LINE adapter main class (EBA skeleton).

骨架（WO-LINE-01-SKELETON-1018 階段）— 依 telegram/slack 實測範例（boxed）
建立「混血繼承 + Capability 宣告 + 事件命名空間 + 初始化設定」骨架。

⚠️ LINE SDK 實際 import 路徑／client 建構／API call 全做 stub，
   待 LINE Developers 官方文檔 + line-bot-sdk 實測後方可定稿（§9/§23 實測優先，禁捏造）。
"""

from __future__ import annotations

import typing

import pydantic

# ---- framework（boxed 實測契约，qualified import，與 telegram/slack 同源）----
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message

# ---- LINE SDK（⚠️ import 路徑待實測 line-bot-sdk v3，禁當成品引用）----
# TODO(待實測): 確認 linebot v3 實際可 import 的名稱與路徑。
# 參考：from linebot import WebhookContentProvider, GetWebhookContentRequest
#       from linebot.v3.webhook import MessageEvent as LineMessageEvent, SourceType
# from linebot.v3 import ...  # ⚠️待實測

# ---- 本 adapter 子模組（骨架，內容待 02/03 填實）----
from langbot.pkg.platform.adapters.line.event_converter import LineEventConverter, LegacyEventConverter
from langbot.pkg.platform.adapters.line.message_converter import LineMessageConverter
from langbot.pkg.platform.adapters.line.api_impl import LineAPIMixin

class LineAdapter(LineAPIMixin, abstract_platform_adapter.AbstractPlatformAdapter):
    """LINE adapter（EBA skeleton）。

    混血繼承（对照 telegram/adapter.py 實測模式）：
      LineAdapter(LineAPIMixin, AbstractPlatformAdapter)
    Capability／事件命名空間／初始化設定已就位（config 取自 SDK-managed config，
    channel_access_token / channel_secret 為 sensitive:true，零硬编码 — §7 憑證紅線）。
    """

    # LINE SDK client（exclude=True：不序列化、不落檔；實測前為占位）
    client: typing.Any = pydantic.Field(default=None, exclude=True)  # ⚠️待實測：LINE BotClient 建構
    content_provider: typing.Any = pydantic.Field(default=None, exclude=True)  # ⚠️待實測：WebhookContentProvider

    message_converter: LineMessageConverter = LineMessageConverter()
    event_converter: LineEventConverter = LineEventConverter()
    legacy_event_converter: LegacyEventConverter = LegacyEventConverter()

    config: dict

    msg_stream_id: dict = {}
    seq: int = 1

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        # ---- §7 憑證紅線：config 由 SDK 依 manifest 載入（sensitive:true → env/secret store）----
        #    本端零硬编码 token/secret；讀 dict，不碰 os.getenv、不落檔。
        self.config = config
        if not config.get("channel_access_token"):
            raise ValueError("LINE adapter config missing channel_access_token")
        if not config.get("channel_secret"):
            raise ValueError("LINE adapter config missing channel_secret")
        self.config_secret = config["channel_secret"]  # 僅供 webhook 簽名校驗；不落檔

        # ⚠️待實測：LINE SDK client 建構（channel_access_token 取自信號 config，非硬编码）
        self.client = LineAdapter._build_client(config)
        self.content_provider = LineAdapter._build_content_provider(config)

        super().__init__(
            config=config,
            logger=logger,
            client=self.client,
            content_provider=self.content_provider,
            msg_stream_id={},
            seq=1,
            listeners={},
        )
        self._register_native_handlers()

    # ---- LINE SDK client 建構（⚠️待實測占位；實際值由 ops 接入時定稿）----

    @staticmethod
    def _build_client(config: dict):
        """⚠️待實測：建立 LINE SDK client。

        對照 telegram `ApplicationBuilder().token(config['token'])`。
        此處不實作實際调用；待 line-bot-sdk v3 實測後填 `...Client(channel_access_token=...)`。
        """
        # TODO(待實測): return <sdk>.Client(channel_access_token=config['channel_access_token'])
        raise NotImplementedError("LINE SDK client 待實測定稿（禁捏造）")

    @staticmethod
    def _build_content_provider(config: dict):
        """⚠️待實測：LINE webhook 附件下載 provider。"""
        # TODO(待實測): return WebhookContentProvider(channel_secret=config['channel_secret'])
        raise NotImplementedError("LINE SDK WebhookContentProvider 待實測定稿（禁捏造）")

    # ---- Capability 宣告（对照 telegram 169-202 實測）----

    def get_supported_events(self) -> list[str]:
        """⚠️ 事件清單待 LINE SDK 事件 JSON 實測後定稿。

        先依框架命名空間 + LINE 常見事件之預留（未實測前可先声明 message.received，
        其余待逐一實測再加，遵守 acceptance-checklist「未實測不声明」）。
        """
        return [
            "message.received",
            "message.edited",  # ⚠️待 LINE SDK 實測
            "message.deleted",  # ⚠️待 Line SDK 實測
            "feedback.received",  # ⚠️待 LINE 是否有 feedback 入口
            "group.member_joined",  # ⚠️待 Line SDK 實測
            "group.member_left",  # ⚠️待 Line SDK 實測
            "platform.specific",
        ]

    def get_supported_apis(self) -> list[str]:
        """⚠️ API 清單待 LINE Messaging API 端點實測後定稿。"""
        return [
            "send_message",
            "reply_message",
            "get_user_info",  # ⚠️待 Line SDK getProfile 實測
            "get_group_info",  # ⚠️待 Line SDK 實測
            "get_group_member_list",  # ⚠️待 Line SDK 實測
            "call_platform_api",
        ]

    # ---- 必需消息 API（⚠️ body 待 Line SDK 實測；签名依 02-platform-api 契约）----

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        """⚠️待實測：LINE push_message / 主动发消息。"""
        # TODO(待實測): 依 LineMessageConverter.yiri2target 转 LINE payload → client.push/sendMessage
        raise NotImplementedError("LINE send_message 待實測定稿（禁捏造）")

    async def reply_message(
        self,
        event: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        """⚠️待實測：LINE reply_message / 回覆收到消息。"""
        # TODO(待實測): 取 event.source_platform_object 的 replyToken → client.reply_message
        raise NotImplementedError("LINE reply_message 待實測定稿（禁捏造）")

    # ---- 事件监听器（对照 telegram register_listener 實測）----

    def register_listener(self, event_type, callback):
        self.listeners[event_type] = callback

    def unregister_listener(self, event_type, callback):
        self.listeners.pop(event_type, None)

    async def _dispatch_eba_event(self, event: platform_events.EBAEvent):
        """对照 telegram 506-512／slack 220-226：依 type→EBAEvent→Event 分發。"""
        for event_type in (type(event), platform_events.EBAEvent, platform_events.Event):
            callback = self.listeners.get(event_type)
            if callback:
                await callback(event, self)
                return

    # ---- native handler 注册（⚠️ 注册钩子；LINE SDK 事件类型待實測）----

    def _register_native_handlers(self):
        """⚠️待實測：掛 LINE SDK 事件回调用 handler → _handle_native_event。

        对照 telegram ApplicationHandler 登録 / slack `self.bot.on_message(...)`。
        """
        # TODO(待實測):
        #   application.on_message(self._handle_native_event) 等
        #   自我消息过滤（bot echo）亦须在此实现，遵守 acceptance-checklist「防回圈」
        pass

    async def _handle_native_event(self, raw_event):
        """⚠️待實測：LINE 原生事件 → 自我消息过滤 → 兼容层转发旧 FriendMessage/GroupMessage（若注册）→ _dispatch_eba_event。

        对照 telegram _dispatch 104-114 / slack _handle_native_event 187-218。
        """
        try:
            # 1. 自我消息过滤（bot echo loop 防護）— ⚠️待 Line SDK 事件結構實測
            # 2. 兼容层：若注册旧 FriendMessage/GroupMessage listener，先转 legacy
            # legacy_event = await self.legacy_event_converter.target2yiri(raw_event, self.config_secret)
            # 3. 歸一化 EBA 事件
            # eba_event = await self.event_converter.target2yiri(raw_event, self.config_secret)
            # 4. 分發
            # if eba_event: await self._dispatch_eba_event(eba_event)
            raise NotImplementedError("LINE native handler 待實測定稿（禁捏造）")
        except Exception:
            import traceback

            await self.logger.error(f"LINE native event error: {traceback.format_exc()}")

    # ---- 流式输出／静音（占位，对照 telegram 311-502）----

    async def reply_message_chunk(self, event, bot_message, message, quote_origin=False, is_final=False):
        """⚠️待實測：LINE 流式回复（如适用 LINE streaming 模式）。"""
        raise NotImplementedError("LINE reply_message_chunk 待實測定稿（禁捏造）")

    async def is_stream_output_supported(self) -> bool:
        """⚠️待實測：LINE 是否支援流式输出。"""
        return False

    async def is_muted(self, group_id: int) -> bool:
        return False

    # ---- 生命周期（对照 telegram 551-566 / slack 161-178）----

    async def run_async(self):
        """⚠️⚠️ run_async 骨架：polling 為預設分支，WebSocket 流式须 architect 裁決（藍圖 ①✜）。

        对照 telegram `ApplicationBuilder().updater.start_polling(...)`。
        polling 分支仅作骨架占位；streaming 分支待 architect 裁決後填。
        """
        # ⚠️待 architect 裁決：WebSocket 流式 vs polling（藍圖 ①✜）。
        # 預設走 polling（architect ② config 未含 bot_push_token，與 polling 一致）。
        # ⚠️待實測：以下为骨架占位；实际轮询/事件循环结构待 Line SDK 實測。
        await self.logger.info("LINE adapter loop starting (polling skeleton; streaming 待 architect 裁決)")
        try:
            await self._poll_once()
        except NotImplementedError:
            raise
        except Exception:
            await self.logger.error("LINE adapter run_async error")
            raise

    async def _poll_once(self):
        """⚠️待實測：一次事件轮询占位。"""
        raise NotImplementedError("LINE 轮询 待實測定稿（禁捏造）")

    async def kill(self) -> bool:
        """对照 telegram kill 558-566。"""
        await self.logger.info("LINE adapter stopped")
        self.msg_stream_id.clear()
        return True
