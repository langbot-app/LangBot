"""LineEventConverter（EBA skeleton）。

⚠️ LINE 事件 JSON 结构待官方文檔 + SDK 實測；target2yiri 做分散式分发骨架，
   LINE 事件类型逐一映射为统一 Event（映射表见蓝图的 §3.2）。
"""

from __future__ import annotations

import typing

import langbot_plugin.api.entities.builtin.platform.events as platform_events

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter


class LineEventConverter(abstract_platform_adapter.AbstractEventConverter):
    """LINE 事件转换器骨架。

    对照 telegram event_converter.py 分散式 target2yiri（依 update 类型分发）。
    LINE SDK 事件类型 / JSON 字段待實測；以下为分发骨架 + 占位映射。
    """

    def __init__(self, channel_secret: str = ""):
        self.config_secret = channel_secret

    @staticmethod
    async def yiri2target(event: platform_events.Event, *args, **kwargs):
        """统一事件 → LINE 原生事件（一般不需要）。"""
        return getattr(event, "source_platform_object", None)

    @staticmethod
    async def target2yiri(raw_event: typing.Any, config_secret: str = "") -> typing.Optional[platform_events.EBAEvent]:
        """⚠️待實測：LINE 原生事件 → 统一 EBA 事件。

        分散式分发骨架：LINE 各事件类型（Text/Image/Video/Audio/Sticker/Follow/Leave/Postback...）
        → 映射统一 Event；无法映射者走 PlatformSpecificEvent（action + data）。
        """
        if not raw_event:
            return None
        # ⚠️待實測：line 事件类型分发
        # raw = raw_event.get("event", {})  if 非 dict 则按实际结构处理
        # ev_type = <line event 'type'>
        # match:
        #   "Message" -> _convert_message(raw, config_secret)
        #   "Follow" -> _convert_follow(raw)
        #   "Leave" -> _convert_leave(raw)
        #   "Postback" -> PlatformSpecificEvent(action="postback", data=raw)
        #   default -> PlatformSpecificEvent(action=<line type>, data=raw)
        raise NotImplementedError("LINE target2yiri 待實測定稿（禁捏造）")

    @staticmethod
    async def _convert_message(raw_event, config_secret):
        """⚠️待實測：LINE message 事件 → MessageReceivedEvent。"""
        raise NotImplementedError("LINE message 映射 待實測定稿（禁捏造）")

    @staticmethod
    async def _convert_follow(raw_event):
        """⚠️待實測：LINE Follow 事件映射。"""
        raise NotImplementedError("LINE Follow 映射 待實測定稿（禁捏造）")

    @staticmethod
    async def _convert_leave(raw_event):
        """⚠️待實測：LINE Leave 事件映射。"""
        raise NotImplementedError("LINE Leave 映射 待實測定稿（禁捏造）")


class LegacyEventConverter(abstract_platform_adapter.AbstractEventConverter):
    """兼容层：LINE 原生事件 → 旧 FriendMessage/GroupMessage（对过渡期兼容）。

    对照 telegram LegacyEventConverter（adapter.py 41-62 旧格式）。
    """

    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent, *args, **kwargs):
        return getattr(event, "source_platform_object", None)

    @staticmethod
    async def target2yiri(event: typing.Any, config_secret: str = ""):
        """⚠️待實測：LINE 原生事件 → 旧 FriendMessage/GroupMessage。"""
        raise NotImplementedError("LINE legacy converter 待實測定稿（禁捏造）")
