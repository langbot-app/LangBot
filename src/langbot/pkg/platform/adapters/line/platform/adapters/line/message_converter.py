"""LineMessageConverter — LINE 訊息 payload ↔ EBA MessageChain（WO-LINE-02 / WO-LINE-05）。

WO-LINE-02 收發閉環 ＋ WO-LINE-05 多模態媒體下載／Flex Message：

  - WO-LINE-05 ②a：``_LINE_SDK.download_message_content``（``MessagingApiBlobClient``
    二進位下載），``download_b64`` 已斂為其委派（維持 WO-LINE-02 已實測行為）。
  - WO-LINE-05 ②b：Flex Message 封裝。`send_api.flex_*` 純量構築卡片／氣泡／輪播，
    ``flex_message_object`` 套成 LINE flex 訊息；本檔 ``yiri2target`` 偵測 flex
    ``PlatformComponent`` → 單一 flex 訊息物件回傳（Flex 為獨立訊息，非逐元件）。

LINE SDK 訊息 payload 待實測；⚠️待實測的 SDK 存取與附件下載集中封裝於
``_LINE_SDK``（仅一处），其上方 MessageChain 结构对照 boxed 契约
（02-platform-api.md §6.1 通用元件）。

注意：EBA 无 Video 通用元件（doc 6.1），故 LINE Video / Sticker 走
``PlatformComponent`` 承载（禁捏造 Face 等价，blueprint §3.5 ⚠️）。
"""

from __future__ import annotations

import base64
import datetime
import typing

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from .errors import NotSupportedError

# WO-LINE-05 ②b：Flex 訊息物件由 send_api 纯量生成（不碰 SDK、可 boxed 测试）
from .send_api import flex_message_object


# 線外（boxed 無 LINE SDK）以占位封裝替換；實際 SDK 存取唯一換入點在此。
class _LINE_SDK:
    """⚠️待實測：LINE SDK 附件讀取／上傳封裝（SDK 存取唯一封裝點）。

    對照 slack message_converter 的 media 下載模式。實際值由 ops 接入
    linebot-sdk v3 後於本 class staticmethod 內定稿；本檔不引用任何
    LINE SDK 實際名稱（禁捏造）。base64 編碼以 stdlib 回退，避免直接依賴 SDK。
    """

    @staticmethod
    async def download_message_content(
        message_id: str,
        content_provider: typing.Any,
        mime_hint: str = "application/octet-stream",
    ) -> typing.Tuple[str, str]:
        """下載 LINE 附件 → 返回 ``(base64_data_uri, mime)``（WO-LINE-05 ②a）。

        據 SDK 3.26.0 合约 §2.4：``MessagingApiBlobClient(message_content_id)
        .download_message_content()`` 返回二進位位元組（ops 實測確認）。
        据此封装附件下载（据 content_provider 读取 bytes）；确切 API 参数
        （``MessagingApiBlobClient`` 建構 + ``download_message_content``）
        供 ops 在 worktree 实测确认（§9，未实測）。
        """
        if content_provider is None:
            raise NotSupportedError("line:media_download")
        try:
            data = _read_provider_content(content_provider, message_id)  # ⚠️待實測
            return (f"data:{mime_hint};base64,{_b64encode(data)}", mime_hint)
        except NotSupportedError:
            raise
        except Exception:
            raise NotSupportedError("line:media_download")

    @staticmethod
    async def download_b64(
        message_id: str,
        content_provider: typing.Any,
        mime_hint: str = "application/octet-stream",
    ) -> typing.Tuple[str, str]:
        """（WO-LINE-02）已斂為 ``download_message_content`` 委派，行为不变。

        据 WO-LINE-05 ②a 收斂；旧调用方仍可用，内部改走二進位下載實作。
        """
        return await _LINE_SDK.download_message_content(
            message_id, content_provider, mime_hint
        )

    @staticmethod
    async def upload_media(media_type: str, data: bytes, mime: str) -> str:
        """上傳附件至 LINE 並返回引用 URL（push/reply 外發必需）。

        ⚠️待實測：LINE uploadImage API + SDK 方法未定稿；未定稿時拋 NotSupportedError。
        """
        raise NotSupportedError(f"line:upload_{media_type}")


# ---- 本地純 Python 輔助（不碰 SDK）----

# 安全取得 MessageComponent 子類（doc 6.1 未列 Video/Sticker，用 getattr 防 AttributeError）
_VIDEO_CLS = getattr(platform_message, "Video", None)
_STICKER_CLS = getattr(platform_message, "Sticker", None)


def _b64encode(data: bytes) -> str:  # stdlib 回退（SDK 未定稿前）
    return base64.b64encode(data).decode("ascii")


def _read_provider_content(content_provider: typing.Any, message_id: str) -> bytes:  # ⚠️待實測
    """⚠️待實測：自 SDK content_provider 讀取附件 bytes（線外以空回退防崩）。"""
    handler = getattr(content_provider, "get", None)
    if callable(handler):
        return handler(message_id)  # 期望返回 bytes
    raise NotSupportedError("line:media_download")


def _source_from_message(line_message: dict) -> platform_message.Source:
    """LINE 訊息物件 → MessageChain.Source（首元件，含 id 與 timestamp）。"""
    return platform_message.Source(
        id=str(line_message.get("id", "")),
        time=_parse_timestamp(line_message.get("timestamp")),
    )


def _parse_timestamp(raw: typing.Any) -> datetime.datetime:
    try:
        return datetime.datetime.fromtimestamp(float(raw) / 1000.0)  # LINE 時間戳為毫秒
    except (TypeError, ValueError):
        return datetime.datetime.now()


def _image_payload(component: typing.Any, media_type: str) -> dict:
    """EBA 媒體元件 → LINE payload（image|audio|video）。

    ⚠️待實測：LINE push/reply 需 originalContentUrl（uploadImage API）；
    僅有 URL 時填入，僅有 base64 時暂無法直接外發（uploadImage 未定稿）。
    """
    return {"type": media_type, "originalContentUrl": getattr(component, "url", "") or ""}


def _file_payload(component: typing.Any) -> dict:
    """EBA File 元件 → LINE payload。"""
    return {"type": "file", "originalContentUrl": getattr(component, "url", "") or ""}


def _platform_component(component_type: str, data: dict) -> platform_message.PlatformComponent:
    """平台專屬元件承載（Video / Sticker —— EBA 無對應通用元件）。"""
    return platform_message.PlatformComponent(
        platform="line",
        component_type=component_type,
        data=data,
    )


class LineMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    """LINE 訊息轉換器（WO-LINE-02 / WO-LINE-05）。

    兩向：
      - ``target2yiri``：LINE 原始訊息（dict）→ EBA MessageChain
      - ``yiri2target``：EBA MessageChain → LINE 訊息陣列（push/reply 共用 ``Message=`` 欄位）

    WO-LINE-05 ②b：MessageChain 若含 flex ``PlatformComponent``，整體視為單一
    flex 訊息回傳（Flex 為独立訊息物件，非逐元件外發）。
    """

    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain, *args: typing.Any, **kwargs: typing.Any
    ) -> list[dict]:
        """EBA MessageChain → LINE 訊息物件陣列（push/reply 共用 ``Message=`` 欄位）。

        ⚠️待實測：媒體外發需 uploadImage URL（``_LINE_SDK.upload_media``）方能成信；
        純文字 / At / AtAll / Quote 對照 boxed 直接生成。

        WO-LINE-05 ②b：Flex 占位 → 單一 flex 訊息物件（非逐元件）。
        """
        # flex 為獨立訊息物件：遇 flex PlatformComponent 即整體視為 flex 訊息
        for component in message_chain:
            if (
                isinstance(component, platform_message.PlatformComponent)
                and getattr(component, "platform", None) == "line"
                and getattr(component, "component_type", None) == "flex"
            ):
                return [flex_message_object(getattr(component, "data", {}) or {})]

        messages: list[dict] = []
        for component in message_chain:
            if isinstance(component, platform_message.Source):
                continue  # Source 僅為元資訊，不隨 MESSAGE 外發
            if isinstance(component, platform_message.Plain):
                messages.append({"type": "text", "text": component.text})
            elif isinstance(component, platform_message.At):
                messages.append({"type": "text", "text": f"<@{component.target}> "})
            elif isinstance(component, platform_message.AtAll):
                messages.append({"type": "text", "text": "<@ALL> "})
            elif isinstance(component, platform_message.Image):
                messages.append(_image_payload(component, "image"))
            elif isinstance(component, platform_message.Voice):
                messages.append(_image_payload(component, "audio"))
            elif isinstance(component, platform_message.File):
                messages.append(_file_payload(component))
            elif _VIDEO_CLS is not None and isinstance(component, _VIDEO_CLS):
                messages.append(_image_payload(component, "video"))
            elif _STICKER_CLS is not None and isinstance(component, _STICKER_CLS):
                messages.append({"type": "sticker", "packageId": "", "stickerId": ""})  # ⚠️待實測
            elif isinstance(component, platform_message.Quote):
                if component.id is not None:
                    messages.append({"type": "text", "text": f"[Quote {component.id}]"})
            elif isinstance(component, platform_message.Forward):
                # ⚠️待實測：LINE forward_message 依藍圖 WO-LINE-03 實測後再定行止
                raise NotSupportedError("line:forward_message")
            elif isinstance(component, platform_message.Unknown):
                messages.append({"type": "text", "text": component.text or str(component)})
            else:
                raise NotSupportedError(f"line:unmappable_component:{type(component).__name__}")
        return messages

    @staticmethod
    async def target2yiri(
        line_message: typing.Any,
        config_secret: str = "",  # 保留參数位；本檔不使用（對齐 adapter 呼叫签名）
        content_provider: typing.Any = None,  # ⚠️待實測：SDK WebhookContentProvider
    ) -> platform_message.MessageChain:
        """LINE 原始訊息 → EBA MessageChain（收端核心）。

        ``line_message`` 為归一化 dict（见 event_converter 的归一化）：
        ``type`` = Text|Image|Video|Audio|Sticker|File；含 ``id``／``text`` 等欄。

        WO-LINE-05 ②a：Image 走 ``download_message_content``（二進位下載）→ Image 元件。
        """
        if not isinstance(line_message, dict):
            raise NotSupportedError(f"line:bad_message_type:{type(line_message).__name__}")
        message_id = str(line_message.get("id", ""))
        message_type = str(line_message.get("type", "")).lower()
        components: list[platform_message.MessageComponent] = [_source_from_message(line_message)]

        if message_type == "text":
            text = str(line_message.get("text", "") or "").strip()
            if text:
                components.append(platform_message.Plain(text=text))
        elif message_type == "image":
            # WO-LINE-05 ②a：ImageMessage → MessageChain 中的 Image 元件（二進位下載）
            data_uri, _mime = await _LINE_SDK.download_message_content(
                message_id, content_provider, "image/jpeg"
            )
            components.append(platform_message.Image(base64=data_uri))
        elif message_type == "video":
            components.append(_platform_component("video", {"message_id": message_id}))
        elif message_type == "audio":
            data_uri, _mime = await _LINE_SDK.download_message_content(
                message_id, content_provider, "audio/3gpp"
            )
            components.append(platform_message.Voice(base64=data_uri))
        elif message_type == "sticker":
            sticker = line_message.get("stickerId") or line_message.get("id", "")
            components.append(_platform_component("sticker", {"sticker_id": sticker}))
        elif message_type == "file":
            data_uri, mime = await _LINE_SDK.download_message_content(
                message_id, content_provider, "application/octet-stream"
            )
            components.append(platform_message.File(
                id=message_id,
                name=str(line_message.get("fileName", "file")),
                size=0,  # ⚠️待實測：size 待附件實際字节
                base64=data_uri,
                mime=mime,
            ))
        else:
            components.append(platform_message.Unknown(text=f"[unsupported LINE message type: {message_type}]"))

        # 若僅剩 Source（無內容），補 Unknown 占位（對照 slack target2yiri 末行）
        if len(components) == 1:
            components.append(platform_message.Unknown(text=f"[empty LINE message: {message_type}]"))
        return platform_message.MessageChain(components)
