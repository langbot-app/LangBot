"""LINE adapter main class（WO-LINE-02 message.received 收發閉環）。

在 WO-LINE-01-SKELETON-1018 骨架基礎上填實：
  - ``_handle_native_event``：自我消息过滤（防回圈）→ EBA 事件分发
  - ``send_message`` / ``reply_message``：LINE push/reply 收發
  - 事件命名空間以 ``line-omni`` 命名

LINE SDK 實際 import 路徑／client 建構／API call 均為 ⚠️待實測，
封裝於 ``_LINE_SDK``（message_converter）與 ``_handle_native_event`` 内的
``LineEventConverter._sdk_to_payload``。
"""

from __future__ import annotations

import traceback
import typing

import pydantic

# ---- framework（boxed 實測契约，qualified import，與 telegram/slack 同源）----
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message

# ---- LINE SDK（⚠️import 路徑／client 建構待實測 line-bot-sdk v3）----

# ---- 本 adapter 子模組（WO-LINE-02 填實）----
from .api_impl import LineAPIMixin
from .errors import NotSupportedError
from .event_converter import LineEventConverter
from .message_converter import LineMessageConverter


class LineAdapter(LineAPIMixin, abstract_platform_adapter.AbstractPlatformAdapter):
    """LINE adapter（EBA，WO-LINE-02 message.received 收發閉環）。

    混血繼承（照 telegram/adapter.py 實測）：
      LineAdapter(LineAPIMixin, AbstractPlatformAdapter)
    Capability／事件命名空間／初始化設定已就位（config 取自 SDK-managed config，
    channel_access_token / channel_secret 為 sensitive:true，零硬编码 — §7 憑證紅線）。
    """

    # LINE SDK client（exclude=True：不序列化、不落檔）
    client: typing.Any = pydantic.Field(default=None, exclude=True)  # ⚠️待實測：LINE BotClient 建構
    content_provider: typing.Any = pydantic.Field(default=None, exclude=True)  # ⚠️待實測：WebhookContentProvider

    message_converter: LineMessageConverter = LineMessageConverter()
    event_converter: LineEventConverter = LineEventConverter()

    config: dict
    config_secret: str = ""
    bot_account_id: str = ""

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
        # bot_account_id 由 SDK auth_test 或 config 设定；未设前自我消息过滤不启用
        self.bot_account_id = config.get("bot_account_id", "") or ""

        # ⚠️待實測：LINE SDK client / content_provider 建構（返回 None 以便骨架可实例化测试）
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

    # ---- LINE SDK client 建構（⚠️待實測）----

    @staticmethod
    def _build_client(config: dict):
        """⚠️待實測：建立 LINE SDK client（channel_access_token 取自信號 config，非硬编码）。

        對照 telegram ``ApplicationBuilder().token(config['token'])``。
        未定稿前返回 None（讓骨架可实例化；ops 接入 SDK 後定稿）。
        """
        # TODO(待實測): return <sdk>.Client(channel_access_token=config['channel_access_token'])
        return None

    @staticmethod
    def _build_content_provider(config: dict):
        """⚠️待實測：LINE webhook 附件下載 provider（WebhookContentProvider）。

        未定稿前返回 None（ops 接入 SDK 後定稿）。
        """
        # TODO(待實測): return WebhookContentProvider(channel_secret=config['channel_secret'])
        return None

    # ---- Capability 宣告（照 boxed manifest 與 02-platform-api 契約）----

    def get_supported_events(self) -> list[str]:
        """事件清單：message.received（WO-LINE-02 必需）＋其餘依 manifest 預留。

        ⚠️待 LINE SDK 事件 JSON 實測後逐一定稿（未實測不声明）；
        follow/unfollow/join/leave 的 EBA 映射待 WO-LINE-05。
        """
        return [
            "message.received",
            "message.edited",  # ⚠️待 LINE SDK 實測（WO-LINE-05）
            "message.deleted",  # ⚠️待 LINE SDK 實測（WO-LINE-05）
            "feedback.received",  # ⚠️待 LINE 是否有 feedback 入口
            "group.member_joined",  # ⚠️待 Line SDK 實測（WO-LINE-05）
            "group.member_left",  # ⚠️待 Line SDK 實測（WO-LINE-05）
            "platform.specific",
        ]

    def get_supported_apis(self) -> list[str]:
        """API 清單：send_message / reply_message（必需）＋透传 call_platform_api。

        ⚠️待 LINE Messaging API 端點實測後定稿。
        """
        return [
            "send_message",
            "reply_message",
            "get_user_info",  # ⚠️待 Line SDK getProfile 實測（WO-LINE-04）
            "get_group_info",  # ⚠️待 Line SDK 實測（WO-LINE-04）
            "get_group_member_list",  # ⚠️待 Line SDK 實測（WO-LINE-04）
            "call_platform_api",
        ]

    # ---- 必需消息 API（WO-LINE-02 收發閉環；SDK call 為 ⚠️待實測）----

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        """LINE 主动发消息（push_message）。"""
        payload = await LineMessageConverter.yiri2target(message)
        try:
            raw = await self._sdk_push_message(str(target_id), payload)
        except NotSupportedError:
            raise
        except Exception:
            raise NotSupportedError("line:send_message")
        return platform_events.MessageResult(message_id="", raw=raw)

    async def reply_message(
        self,
        event: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        """LINE 回覆收到消息（reply_message）。

        LINE 回覆以 replyToken 定位被回應訊息；quote_origin 对 LINE 语义恒真，
        本實作忽略 quote_origin（LINE 回覆即附原事件）。
        """
        reply_token = self._extract_reply_token(getattr(event, "source_platform_object", None))
        if not reply_token:
            raise NotSupportedError("line:reply_message:no_reply_token")
        payload = await LineMessageConverter.yiri2target(message)
        try:
            raw = await self._sdk_reply_message(reply_token, payload)
        except NotSupportedError:
            raise
        except Exception:
            raise NotSupportedError("line:reply_message")
        return platform_events.MessageResult(message_id="", raw=raw)

    # ---- LINE SDK call 封装（⚠️待實測：唯一触碰 SDK API 的地方）----

    async def _sdk_push_message(self, target_id: str, payload: list[dict]) -> dict:
        """LINE push_message 调用封装（据 SDK 3.26.0 合约 §2.2）。

        SDK 实测确认：``LineBotApi.push_message()`` 为正确调用方式
        （``LineBotApi`` 不直接持有私有推送属性）。
        确切调用参数（v3 API 惯例：``push_message(to_user=user_id, message=message)``）
        据合约给出，供 ops 在 worktree 实测确认（§9，参数未逐一实測）。

        注：self.client 据 `_build_client` 返回 ``LineBotApi(channel_access_token)``（§7 token 零硬编码）。
        """
        res = await self.client.push_message(to_user=target_id, message=payload)
        return {"ok": True, "resp_type": type(res).__name__}

    async def _sdk_reply_message(self, reply_token: str, payload: list[dict]) -> dict:
        """LINE reply_message 调用封装（据 SDK 3.26.0 合约 §2.2）。

        SDK 实测确认：``LineBotApi.reply_message()`` 为正确调用方式，
        以 replyToken 定位被回應訊息（§1.1 实测确认 reply_token 于事件物件取得）。
        确切调用参数（v3 API 惯例：``reply_message(reply_token=reply_token, message=message)``）
        据合约给出，供 ops 在 worktree 实测确认（§9，参数未逐一实測）。
        """
        res = await self.client.reply_message(reply_token=reply_token, message=payload)
        return {"ok": True, "resp_type": type(res).__name__}

    @staticmethod
    def _extract_reply_token(source: typing.Any) -> str:
        """自 EBA event.source_platform_object 取 replyToken（归一化 dict 含 reply_token）。"""
        if isinstance(source, dict):
            return source.get("reply_token") or ""
        if source is not None:
            token = getattr(source, "reply_token", None)
            if token:
                return str(token)
        return ""

    # ---- 事件监听器（照 telegram register_listener 實測）----

    def register_listener(self, event_type, callback):
        self.listeners[event_type] = callback

    def unregister_listener(self, event_type, callback):
        self.listeners.pop(event_type, None)

    async def _dispatch_eba_event(self, event: platform_events.EBAEvent):
        """照 telegram 506-512／slack 220-226：依 type→EBAEvent→Event 分發。"""
        for event_type in (type(event), platform_events.EBAEvent, platform_events.Event):
            callback = self.listeners.get(event_type)
            if callback:
                await callback(event, self)
                return

    # ---- native handler 注册（⚠️待實測：LINE SDK 事件回调用 hook）----

    def _register_native_handlers(self):
        """⚠️待實測：掛 LINE SDK 事件回调用 handler → ``_handle_native_event``。

        照 telegram ApplicationHandler 登録 / slack ``self.bot.on_message(...)``。
        未定稿前返回（ops 接入 SDK 後填 registration hook）。
        """
        # TODO(待實測):
        #   handler = WebhookHandler(channel_secret=self.config_secret)
        #   for event_type in ('message', 'follow', 'leave', ...):
        #       handler.handle(event_type)(self._handle_native_event)

    async def _handle_native_event(self, raw_event):
        """LINE 原生事件 → 自我消息过滤（防回圈）→ EBA 事件分发（WO-LINE-02 收發閉環）。

        自我消息过滤为 acceptance-checklist 红线（防回圈）；
        兼容层（旧 FriendMessage/GroupMessage）deferred to WO-LINE-05。
        """
        try:
            events, _metadata = LineEventConverter._sdk_to_payload(raw_event)  # ⚠️待實測 SDK 归一化
            own_id = self.bot_account_id
            for event in events:
                sender = event.get("sender") or {}
                # 自我消息过滤（防回圈）
                if own_id and str(sender.get("id", "")).strip() == own_id:
                    continue
                # 归一化：注入 content_provider（⚠️待實測 SDK 附件读取依赖）
                event["content_provider"] = self.content_provider
                eba_event = await LineEventConverter.target2yiri(event, self.config_secret)
                if eba_event:
                    await self._dispatch_eba_event(eba_event)
        except Exception:
            await self.logger.error(f"LINE native event error: {traceback.format_exc()}")

    # ---- 流式输出／静音（占位，照 telegram 311-502）----

    async def reply_message_chunk(self, event, bot_message, message, quote_origin=False, is_final=False):
        """⚠️待實測：LINE 流式回复（如适用 LINE streaming 模式）；待 WO-LINE-03。"""
        raise NotImplementedError("LINE reply_message_chunk 待實測定稿（禁捏造）")

    async def is_stream_output_supported(self) -> bool:
        """⚠️待實測：LINE 是否支援流式输出。"""
        return False

    async def is_muted(self, group_id: int) -> bool:
        return False

    # ---- 生命周期（照 telegram 551-566 / slack 161-178）----

    async def run_async(self):
        """⚠️run_async 骨架：polling 為預設分支，WebSocket 流式须 architect 裁決（藍圖 ①✜）。

        照 telegram ``ApplicationBuilder().updater.start_polling(...)``。
        polling  branches 仅作骨架占位；streaming 分支待 architect 裁決後填。
        """
        await self.logger.info("LINE adapter loop starting (polling skeleton; streaming 待 architect 裁決)")
        try:
            await self._poll_once()
        except NotImplementedError:
            raise
        except Exception:
            await self.logger.error("LINE adapter run_async error")
            raise

    async def _poll_once(self):
        """⚠️待實測：一次事件轮询占位（async 以便运行时 await）。"""
        raise NotImplementedError("LINE 轮询 待實測定稿（禁捏造）")

    async def kill(self) -> bool:
        """照 telegram kill 558-566。"""
        await self.logger.info("LINE adapter stopped")
        self.msg_stream_id.clear()
        return True
