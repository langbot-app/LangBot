"""LineMessageConverter（EBA skeleton）。

对照 telegram message_converter.py（仅 5 行，转发至 sources.telegram 旧格式）。
LINE SDK 消息 payload 待實測；此处做转换骨架 + 占位。
"""

from __future__ import annotations

import typing

import langbot_plugin.api.entities.builtin.platform.events as platform_events


class LineMessageConverter:
    """LINE 消息转换骨架。

    telegram: 消息转换转发到 `langbot_pkg.platform.sources.telegram`。
    LINE: 待實測 LINE SDK 消息体与旧 source 格式的桥接点。
    """

    @staticmethod
    async def yiri2target(event: platform_events.Event, *args, **kwargs):
        if hasattr(event, "source_platform_object"):
            return event.source_platform_object
        return None

    @staticmethod
    async def target2yiri(raw_event: typing.Any, config_secret: str = ""):
        """⚠️待實測：LINE 消息源 → 旧 source 格式（过渡期用）。"""
        raise NotImplementedError("LINE message converter 待實測定稿（禁捏造）")
