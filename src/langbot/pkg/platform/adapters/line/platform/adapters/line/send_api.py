"""send_api — LINE Flex Message 純量封裝（WO-LINE-05 ②b，boxed 可测，无 SDK 依赖）。

本檔仅产出纯 Python dict（Flex 卡片／氣泡／輪播／按钮／动作），不碰任何 LINE SDK。
真正对外发送由 adapter.py 的 ``send_flex`` 承接（据 SDK 3.26.0 合约 §2.2
push_message / reply_message，⚠️待實測）。

Flex 訊息物件格式（LINE Messaging API）：
    {"type": "flex", "contentType": "application/json", "data": <container>}
其中 <container> 為 ``bubble`` 或 ``carousel`` 容器。

所有字段皆可选填，缺省即回 LINE 端默认值（未實測，供 ops 在 worktree 确认）。
"""

from __future__ import annotations

import typing

__all__ = [
    "FlexText",
    "FlexButton",
    "FlexPostbackAction",
    "FlexMessageAction",
    "FlexImage",
    "FlexBox",
    "FlexBubble",
    "FlexCarousel",
    "flex_message_object",
    "flex_message_list",
    "send_flex",
]


# ---- 容器内元件（component）----

def FlexText(
    text: str,
    *,
    size: str = "md",
    weight: str = "",
    color: str = "",
    align: str = "",
    margin: str = "",
) -> dict:
    """Flex 文字元件。缺省 ``size=md``；weight/color/align/margin 留空即不回传。"""
    c: dict = {"type": "text", "text": text, "size": size}
    if weight:
        c["weight"] = weight
    if color:
        c["color"] = color
    if align:
        c["align"] = align
    if margin:
        c["margin"] = margin
    return c


def FlexImage(url: str, *, aspect_ratio: str = "") -> dict:
    """Flex 图片元件。``aspect_ratio`` 留空即不回传。"""
    c: dict = {"type": "image", "url": url}
    if aspect_ratio:
        c["aspectRatio"] = aspect_ratio
    return c


def FlexBox(
    layout: str,
    contents: typing.Sequence[dict],
    *,
    spacing: str = "",
    padding_start: str = "",
    padding_end: str = "",
    background_color: str = "",
) -> dict:
    """Flex box（``layout`` ∈ {horizontal, vertical, baseline}）。

    缺省 ``spacing=md``；其余 padding/background 留空即不回传。
    """
    c: dict = {"type": "box", "layout": layout, "contents": list(contents), "spacing": spacing or "md"}
    if padding_start:
        c["paddingStart"] = padding_start
    if padding_end:
        c["paddingEnd"] = padding_end
    if background_color:
        c["backgroundColor"] = background_color
    return c


def FlexPostbackAction(label: str, data: str, *, display_text: str = "") -> dict:
    """Flex 按钮动作：postback（点击回传 ``data``，可选回显 ``displayText``）。"""
    a: dict = {"type": "postback", "label": label, "data": data}
    if display_text:
        a["displayText"] = display_text
    return a


def FlexMessageAction(label: str, text: str) -> dict:
    """Flex 按钮动作：message（点击把 ``text`` 送入输入框）。"""
    return {"type": "message", "label": label, "text": text}


def FlexButton(
    action: dict,
    *,
    style: str = "",
    color: str = "",
) -> dict:
    """Flex 按钮元件。``action`` 由 ``FlexPostbackAction`` / ``FlexMessageAction`` 生成。"""
    b: dict = {"type": "button", "action": action}
    if style:
        b["style"] = style
    if color:
        b["color"] = color
    return b


# ---- 容器（container）----

def FlexBubble(
    body: dict,
    *,
    header: dict = None,
    footer: dict = None,
) -> dict:
    """Flex bubble。``body`` 必需（含 ``layout``/``contents``）；header/footer 可选。

    依 LINE 规格，header/footer 若填亦为含 ``layout``/``contents`` 的 box。
    """
    bubble: dict = {"type": "bubble", "body": body}
    if header:
        bubble["header"] = header
    if footer:
        bubble["footer"] = footer
    return bubble


def FlexCarousel(bubbles: typing.Sequence[dict]) -> dict:
    """Flex carousel（多气泡横滑）：``contents`` 为 bubble 列表。"""
    return {"type": "carousel", "contents": list(bubbles)}


# ---- flex 訊息物件 ----

def flex_message_object(container: dict) -> dict:
    """把 flex 容器套成 LINE flex 訊息物件（push/reply message 阵列之一元素）。"""
    return {"type": "flex", "contentType": "application/json", "data": container or {}}


def flex_message_list(container: dict) -> list[dict]:
    """flex 容器 → 符合 push/reply ``message`` 栏位的单元素阵列。"""
    return [flex_message_object(container)]


# ---- 发送承接（据 SDK 合约，⚠️待實測）----

async def send_flex(
    adapter: typing.Any,
    target_id: str,
    container: dict,
    reply_token: str | None = None,
) -> dict:
    """Flex 发送承接（linearity 最小封装：据 push/reply 合约）。

    - ``reply_token`` 有值 → 走 ``reply_message``（回被回應訊息）；
    - 否则走 ``push_message(to=target_id)``（主动发送）。

    ``adapter._sdk_push_message`` / ``_sdk_reply_message`` 为唯一 SDK 存取點
    （据 SDK 3.26.0 合约 §2.2，⚠️待實測）；本函式仅回传其原始结果。
    adapter.py ``send_flex`` 会再包成 ``MessageResult``。
    """
    payload = flex_message_list(container)
    if reply_token:
        return await adapter._sdk_reply_message(reply_token, payload)
    return await adapter._sdk_push_message(str(target_id), payload)
