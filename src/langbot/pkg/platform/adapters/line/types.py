"""LINE adapter 事件类型常量骨架（待實測 LINE SDK 事件 JSON 定稿）。

对照 telegram 各 Update 类型常量。此处为占位命名空间；实际 line 事件类型
待官方文档 + SDK 实測后逐一定义（禁捏造）。
"""

from __future__ import annotations

from enum import Enum


class LineEventType(str, Enum):
    """⚠️ 待實測：LINE SDK 事件类别。

    未實測的 LINE 事件类型一律不在此声明，遵守「未實測不声明」。
    """

    # 消息类
    text = "text"
    image = "image"
    video = "video"
    audio = "audio"
    sticker = "sticker"
    file = "file"
    # 交互
    interactive_message = "interactive"  # ⚠️待实测
    postback = "postback"  # ⚠️待实测
    # 群/用户事件
    group_joined = "group_joined"  # ⚠️待实测
    group_left = "group_left"  # ⚠️待实测
    user_joined = "user_joined"  # ⚠️待实测
    user_left = "user_left"  # ⚠️待实测
    # 关注
    follow = "follow"  # ⚠️待实测
    unfollow = "unfollow"  # ⚠️待实测
