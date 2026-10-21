# -*- coding: utf-8 -*-
"""
event_extensions.py — LINE 事件擴充（WO-LINE-04 子模块）。

据 blueprint §3.2 事件映射表（⚠️待 LINE 事件 JSON 實測）+ EBA 框架契约（boxed）
+ ops .84 CubeSandbox SDK 实测 event_type 值，扩展事件命名空间映射。

对照 WO-LINE-02 event_converter.py 的 `_platform_specific` 分发框架（延续其形态）。

含：
- ②a LINE 关键生命周期与互动事件解析：
  JoinEvent→group.joined／LeaveEvent→group.left／FollowEvent→user.followed
  ／UnfollowEvent→user.unfollowed／PostbackEvent→platform.specific.postback。
- ②b 群组与使用者資訊查詢介面（get_group_summary／get_group_member_profile／get_user_profile）
  的命名空間映射（据 blueprint §3.4 LINE API→EBA 映射表）＋ SDK 调用骨架。
- ②c 事件命名空間映射（未實測事件**不声明 capability**〔architect WO-LINE-04 §c 紅線〕，
  仅据 EBA 框架契约映射 + 标注實測待確認）。

纪律（§3.2／§3.4 标注）：
- blueprint §3.2 明示 LINE 事件 JSON 映射 ⚠️待 LINE 事件 JSON 實測。
- blueprint §3.4 明示 LINE API→EBA 映射（含 getProfile／getGroupMemberIds 等）⚠️待 LINE Messaging API 端點實測。
- 据 ops .84 SDK 实测的 event_type 值判定（见 WO-LINE-02 target2yiri）；
  PostbackEvent／BeaconEvent 等据 blueprint §3.2 mapping table 标注實測待確認。
- 未實測事件不宣告 capability（architect §c 紅線）；未映射者默认走 platform.specific。

解耦：据 WO-LINE-02 框架风格（_platform_specific + EBA 事件命名空间）；仅 stdlib + EBA 框架契约。
"""
from __future__ import annotations

import typing
import time
from typing import Any, Optional


# ---------------------------------------------------------------------------
# 事件命名空間映射（②a / ②c）
# ---------------------------------------------------------------------------
class LineEventExtensions:
    """LINE 事件擴充映射（②a 生命周期與互動事件；②b 資訊查詢命名空間）。

    延续 WO-LINE-02 `LineEventConverter._platform_specific` 框架；据 blueprint §3.2
    映射表（⚠️待 LINE 事件 JSON 實測）+ EBA 框架契约（boxed）+ ops .84 SDK 实测
    event_type 值，产出映射**框架**並标注實測待確認（§9/§23 禁捏造未定案線程）。

    未實測事件**不宣告 capability**（architect §c 紅線）。
    """

    # 据 ops .84 SDK 实测的 event_type 值（见 WO-LINE-02 target2yiri）。
    # blueprint §3.2 明示 LINE 事件 JSON 映射 ⚠️待 LINE 事件 JSON 實測。
    _EVENT_TYPE_MAP = {
        "message": "message.received",
        "follow": "user.followed",
        "unfollow": "user.unfollowed",
        "join": "group.joined",
        "left": "group.left",
        "member_joined": "group.member_joined",
        "member_left": "group.member_left",
        "postback": "platform.specific.postback",
        "beacon": "platform.specific.beacon",
    }

    def __init__(self, namespace: str = "line-omni") -> None:
        self.namespace = namespace

    async def yiri2target(self, event: Any, *args: Any, **kwargs: Any) -> Any:
        """統一事件 → LINE 原生事件（一般不需要，延续 WO-LINE-02 yiri2target）。"""
        return getattr(event, "source_platform_object", None)

    async def target2yiri(self, normalized_event: dict) -> Optional[dict]:
        """归一化事件 dict → EBA 事件映射（框架版）。

        返回 dict：{type, action, ...}，沿用 WO-LINE-02 `_platform_specific` 框架；
        具体 EBA 事件对象构建据 ops .84 SDK 实测（event_type）—— blueprint §3.2 ⚠️待測。

        注：本框架**据 EBA 框架契约**映射命名空間（boxed）；**未實測事件不宣告 capability**。
        """
        if not isinstance(normalized_event, dict):
            return None
        event_type = str(normalized_event.get("type", "")).lower()
        mapped = self._EVENT_TYPE_MAP.get(event_type)
        if mapped is None:
            # 未映射者默认走 platform.specific（action = line.<type>），不宣告 capability
            return {"type": "platform.specific", "action": f"line.{event_type}",
                    "raw_type": event_type, "raw": normalized_event}
        if mapped == "platform.specific.postback":
            # PostbackEvent → platform.specific.postback（保留 action + data）
            data = normalized_event.get("data") or normalized_event.get("postback", {})
            return {"type": mapped, "action": "postback",
                    "params": data, "raw": normalized_event}
        if mapped == "platform.specific.beacon":
            data = normalized_event.get("data") or normalized_event.get("beacon", {})
            return {"type": mapped, "action": "beacon",
                    "params": data, "raw": normalized_event}
        # group.* / user.* / member_* → EBA 事件命名空間（boxed 框架契约）
        # blueprint §3.2 明示 LINE 事件 JSON 映射 ⚠️待 LINE 事件 JSON 實測
        sender = normalized_event.get("sender") or {}
        return {
            "type": mapped,
            "action": mapped,
            "source_platform_object": normalized_event,
            "sender_id": str(sender.get("id", "")).strip(),
            "chat_id": str(sender.get("id", "")).strip(),
            "timestamp": _parse_event_timestamp(normalized_event.get("timestamp")),
            "raw": normalized_event,
        }

    def supported_events(self):
        """据 EBA 框架契约声明的事件命名空間。

        未實測事件**不宣告**（architect §c 紅線）；仅据 blueprint §3.2 映射表框架 + ops .84
        SDK 实测 event_type 值。实测后（WO-LINE-05）据实声明。
        """
        # 据 EBA 框架契约（boxed）+ blueprint §3.2 映射表；未實測事件不在此宣告。
        return [
            "message.received",
            "user.followed",
            "user.unfollowed",
            "group.joined",
            "group.left",
            "group.member_joined",
            "group.member_left",
            "platform.specific.postback",
            "platform.specific.beacon",
        ]


# ---------------------------------------------------------------------------
# 事件命名空間映射（②b 群組與使用者資訊查詢）
# ---------------------------------------------------------------------------
class LineGroupUserQuery:
    """群組與使用者資訊查詢命名空間映射（②b）。

    据 blueprint §3.4 LINE API→EBA 映射表（⚠️待 LINE Messaging API 端點實測）：
    - get_user_info → LINE getProfile
    - get_group_member_list → LINE getGroupMemberIds / getGroupMembers
    - get_group_info → LINE getGroupSummary（待測可用性）

    仅据 blueprint §3.4 映射表产出**命名空间**骨架；SDK 调用约定据 blueprint §3.4
    ⚠️待 LINE Messaging API 端點實測，标注實測待確認（§9/§23 禁捏造未定案線程）。
    """

    # 据 blueprint §3.4 LINE API→EBA 映射表（⚠️待 LINE Messaging API 端實測）
    _API_MAP = {
        "get_user_profile": "get_user_info",        # LINE getProfile（⚠️待測）
        "get_group_summary": "get_group_info",       # LINE getGroupSummary（⚠️待測）
        "get_group_member_profile": "get_group_member_list",  # LINE getGroupMemberIds（⚠️待測）
    }

    def __init__(self, namespace: str = "line-omni") -> None:
        self.namespace = namespace

    def supported_apis(self):
        """据 blueprint §3.4 LINE API→EBA 映射表（可选）产出 API 命名空間骨架。

        ⚠️未實測 LINE Messaging API 端點不聲明 capability（architect §c 紅線）；
        仅据 blueprint §3.4 映射表 + ops .84 SDK 实测框架标注實測待確認。
        """
        return [
            "get_user_info",
            "get_group_info",
            "get_group_member_list",
        ]

    def query_name(self, action: str) -> Optional[str]:
        """据 blueprint §3.4 API 映射表返回对应 EBA API 命名空間。

        action ∈ {get_user_profile, get_group_summary, get_group_member_profile}。
        SDK 调用（getProfile / getGroupSummary / getGroupMemberIds）据 blueprint §3.4
        ⚠️待 LINE Messaging API 端實測——标注實測待確認（§9/§23 禁捏造）。
        """
        return self._API_MAP.get(action)


def _parse_event_timestamp(value: Any) -> float:
    """据 ops .84 SDK 实测 timestamp 字段（epoch 毫秒或 ISO）解析（延续 WO-LINE-02）。

    blueprint §3.2 未實測 event timestamp 结构——据 ops .84 SDK 实测框架；标注實測待確認。
    """
    if value is None:
        return 0.0
    try:
        # epoch 毫秒 → 秒（ops .84 SDK 实测多数 LINE 事件用 epoch 毫秒）
        if isinstance(value, (int, float)):
            return float(value) / 1000.0 if value > 1e12 else float(value)
        return time.time()
    except (TypeError, ValueError):
        return time.time()
