"""LineEventConverter（WO-LINE-02 message.received 收發閉環事件分发）。

對照 telegram/event_converter.py（分散式 ``target2yiri`` 依事件类型分发）
與 slack event_converter.py（boxed 實測）。

LINE SDK 事件结构為 ⚠️待實測；**唯一直接碰觸 SDK 事件體的地方是
``_sdk_to_payload``（唯一封裝點）**。其下 ``target2yiri`` / ``_convert_message``
均操作歸一化 dict，可獨立測試，且對照 boxed 事件契約
（01-event-system.md §3.2 MessageReceivedEvent）。
"""

from __future__ import annotations

import time
import typing

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events

from .message_converter import LineMessageConverter


class LineEventConverter(abstract_platform_adapter.AbstractEventConverter):
    """LINE 事件轉換器。

    ``target2yiri`` 接收**單條歸一化事件** dict（由 ``_sdk_to_payload`` 产出），
    依 ``type`` 分发至各映射；``_sdk_to_payload`` 是唯一 SDK 存取點。
    """

    @staticmethod
    async def yiri2target(event: platform_events.Event, *args: typing.Any, **kwargs: typing.Any):
        """統一事件 → LINE 原生事件（一般不需要）。"""
        return getattr(event, "source_platform_object", None)

    @staticmethod
    async def target2yiri(
        normalized_event: typing.Any, config_secret: str = ""
    ) -> typing.Optional[platform_events.EBAEvent]:
        """归一化事件 dict → EBA 事件（分發式）。

        ⚠️待實測：事件类别分发依据 SDK 归一化（``_sdk_to_payload``）；
        消息类 → MessageReceivedEvent；follow/leave/postback 等走
        PlatformSpecificEvent（action = ``line.<type>``，EBA 映射待 WO-LINE-05 定稿）。
        """
        if not isinstance(normalized_event, dict):
            return None
        event_type = str(normalized_event.get("type", "")).lower()
        message = normalized_event.get("message")

        if event_type == "message" and message is not None:
            return await LineEventConverter._convert_message(normalized_event)
        if event_type in {"follow", "unfollow"}:
            return LineEventConverter._platform_specific(normalized_event, "follow")
        if event_type in {"leave", "user_left"}:
            return LineEventConverter._platform_specific(normalized_event, "leave")
        if event_type in {"join", "member_joined"}:
            return LineEventConverter._platform_specific(normalized_event, "join")
        if event_type in {"left", "member_left"}:
            return LineEventConverter._platform_specific(normalized_event, "left")
        # default → PlatformSpecificEvent（action 保留原始 LINE 类型，待 WO-LINE-05 细化 EBA 映射）
        return LineEventConverter._platform_specific(normalized_event, event_type or "unknown")

    @staticmethod
    async def _convert_message(normalized_event: dict) -> platform_events.MessageReceivedEvent:
        """LINE 消息事件 → MessageReceivedEvent（WO-LINE-02 核心）。

        LINE 為 1:1 對話，`chat_type=private`、`chat_id=sender_id`；
        群組語義待 SDK 實測（WO-LINE-05）。
        """
        line_message = normalized_event["message"]
        sender = normalized_event.get("sender") or {}
        sender_id = str(sender.get("id", "")).strip()
        sender_name = str(sender.get("name", "")).strip() or sender_id
        message_id = str(normalized_event.get("message_id", line_message.get("id", "")))
        content_provider = normalized_event.get("content_provider")

        message_chain = await LineMessageConverter.target2yiri(
            line_message, config_secret="", content_provider=content_provider
        )
        return platform_events.MessageReceivedEvent(
            type="message.received",
            adapter_name="line-omni",
            message_id=message_id,
            message_chain=message_chain,
            sender=platform_entities.User(id=sender_id, nickname=sender_name),
            chat_type="private",  # ChatType.PRIVATE 字面值（str Enum）
            chat_id=sender_id,
            group=None,
            timestamp=_parse_event_timestamp(normalized_event.get("timestamp")),
            source_platform_object=normalized_event,
        )

    @staticmethod
    def _platform_specific(normalized_event: dict, action: str) -> platform_events.PlatformSpecificEvent:
        """未映射到通用事件者 → PlatformSpecificEvent（action = ``line.<type>``）。

        原始資料留於 ``data``（含 SDK 事件體）；EBA 映射（如 friend.added/removed）
        待 WO-LINE-05 實測後定稿。
        """
        return platform_events.PlatformSpecificEvent(
            type="platform.specific",
            adapter_name="line-omni",
            action=f"line.{action}",
            data=dict(normalized_event.get("data") or normalized_event),
            timestamp=_parse_event_timestamp(normalized_event.get("timestamp")),
            source_platform_object=normalized_event,
        )

    @staticmethod
    def _sdk_to_payload(raw_event: typing.Any) -> typing.Tuple[list[dict], dict]:
        """LINE SDK 事件归一化 —— 唯一直接触碰 SDK 事件體的函式（类层静态方法）。

        已据 SDK 3.26.0 合约（WO-LINE-00-SDK-326-CONTRACT §1.2）收斂：SDK 事件物件
        结构经 ops 在 .84 CubeSandbox 實測（``raw_event.body.events`` /
        ``raw_event.body.destination`` / ``raw_event.body.webhookEventId`` /
        ``raw_event.body.sender``）。接收 raw_event（SDK 事件物件、已解析 dict）；
        归一化為 ``(events, metadata)``：
          events    : list[dict]，每条含 ``type/message_id/reply_token/message/sender/timestamp/data``
          metadata  : ``destination/webhookEventId/sender``
        其余逻辑均操作归一化 dict（可獨立測試，不依赖 SDK）。
        """
        if isinstance(raw_event, dict):
            events = [_normalize_incoming(e) for e in raw_event.get("events", [])]
            metadata = {
                "destination": str(raw_event.get("destination", "")),
                "webhookEventId": str(raw_event.get("webhookEventId", "")),
                "sender": _sender_dict(raw_event.get("sender")),
            }
            return events, metadata
        # SDK 物件分支（NewWebhookEvent：.body(.events/.destination/.webhookEventId/.sender)）
        body = getattr(raw_event, "body", None)
        body_events = getattr(body, "events", []) if body is not None else []
        metadata = {
            "destination": str(getattr(body, "destination", "") if body is not None else ""),
            "webhookEventId": str(getattr(body, "webhookEventId", "") if body is not None else ""),
            "sender": _sender_dict(getattr(body, "sender", None) if body is not None else None),
        }
        events = [_normalize_incoming(e) for e in body_events]
        return events, metadata


# ============================ ⚠️待實測：SDK 事件归一化边界 ============================
# 下列 accessor 同时兼容 dict（raw LINE JSON）與 SDK 事件物件，
# 线外仅走 dict 分支；SDK 分支由 ops 接入 linebot-sdk v3 后定稿。
# ========================================================================


def _normalize_incoming(event: typing.Any) -> dict:
    """单条 SDK/LINE 事件 → 归一化 dict（dict/物件双兼容）。"""
    return {
        "type": _event_type(event),
        "message_id": _event_message_id(event),
        "reply_token": _event_reply_token(event),
        "message": _event_message(event),
        "timestamp": _event_timestamp(event),
        "sender": _sender_event(event),
        "data": event,
    }


def _sender_event(event: typing.Any) -> dict:
    """SDK/LINE event 的 sender → 归一化 dict（dict/物件双兼容）；dict 取 ``.get("sender")``、物件取 ``getattr``。"""
    if isinstance(event, dict):
        return _sender_dict(event.get("sender"))
    return _sender_dict(getattr(event, "sender", None))


def _event_type(event: typing.Any) -> str:
    if isinstance(event, dict):
        return str(event.get("type", "")).lower()
    return str(getattr(event, "type", "")).lower()


def _event_message(event: typing.Any) -> typing.Any:
    if isinstance(event, dict):
        return event.get("message")
    return getattr(event, "message", None)


def _event_message_id(event: typing.Any) -> str:
    msg = _event_message(event)
    if isinstance(msg, dict):
        return str(msg.get("id", ""))
    if msg is not None:
        return str(getattr(msg, "id", "") or "")
    if isinstance(event, dict):
        return str(event.get("id", ""))
    return str(getattr(event, "id", "") or getattr(event, "message_id", "") or "")


def _event_reply_token(event: typing.Any) -> typing.Optional[str]:
    # 据 SDK 3.26.0 合约 §1.1 实测确认：reply_token 可直接于事件物件 .reply_token /
    # event.message.reply_token 取得（事件级 vs message 级双兼容）；本 accessor 据此实作。
    if isinstance(event, dict):
        return event.get("replyToken") or (event.get("message") or {}).get("replyToken")
    token = getattr(event, "reply_token", None)
    if token:
        return token
    msg = getattr(event, "message", None)
    if msg is not None:
        return getattr(msg, "replyToken", None) or getattr(msg, "reply_token", None)
    return None


def _event_timestamp(event: typing.Any) -> typing.Any:
    if isinstance(event, dict):
        return event.get("timestamp")
    return getattr(event, "timestamp", None)


def _sender_dict(sender: typing.Any) -> dict:
    if isinstance(sender, dict):
        return sender
    if sender is None:
        return {}
    return {"id": getattr(sender, "id", ""), "name": getattr(sender, "name", "")}


def _parse_event_timestamp(ts: typing.Any) -> float:
    try:
        return float(ts) / 1000.0  # LINE 时间戳为毫秒 → 秒
    except (TypeError, ValueError):
        return time.time()
