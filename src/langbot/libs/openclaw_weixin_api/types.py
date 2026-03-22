"""Type definitions for the OpenClaw WeChat API, mirroring the upstream protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

SESSION_EXPIRED_ERRCODE = -14


class ApiError(Exception):
    """Structured error raised by the OpenClaw WeChat API."""

    def __init__(
        self,
        message: str,
        *,
        status: int = 0,
        code: int | None = None,
        payload: Any = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.payload = payload

    @property
    def is_session_expired(self) -> bool:
        return self.code == SESSION_EXPIRED_ERRCODE


@dataclass
class CDNMedia:
    encrypt_query_param: Optional[str] = None
    aes_key: Optional[str] = None
    encrypt_type: Optional[int] = None


@dataclass
class TextItem:
    text: Optional[str] = None


@dataclass
class ImageItem:
    media: Optional[CDNMedia] = None
    thumb_media: Optional[CDNMedia] = None
    aeskey: Optional[str] = None
    url: Optional[str] = None
    mid_size: Optional[int] = None
    thumb_size: Optional[int] = None
    thumb_height: Optional[int] = None
    thumb_width: Optional[int] = None
    hd_size: Optional[int] = None


@dataclass
class VoiceItem:
    media: Optional[CDNMedia] = None
    encode_type: Optional[int] = None
    bits_per_sample: Optional[int] = None
    sample_rate: Optional[int] = None
    playtime: Optional[int] = None
    text: Optional[str] = None


@dataclass
class FileItem:
    media: Optional[CDNMedia] = None
    file_name: Optional[str] = None
    md5: Optional[str] = None
    len: Optional[str] = None


@dataclass
class VideoItem:
    media: Optional[CDNMedia] = None
    video_size: Optional[int] = None
    play_length: Optional[int] = None
    video_md5: Optional[str] = None
    thumb_media: Optional[CDNMedia] = None
    thumb_size: Optional[int] = None
    thumb_height: Optional[int] = None
    thumb_width: Optional[int] = None


@dataclass
class RefMessage:
    message_item: Optional[MessageItem] = None
    title: Optional[str] = None


@dataclass
class MessageItem:
    """A single content item inside a WeixinMessage."""

    # Item types
    NONE = 0
    TEXT = 1
    IMAGE = 2
    VOICE = 3
    FILE = 4
    VIDEO = 5

    type: Optional[int] = None
    create_time_ms: Optional[int] = None
    update_time_ms: Optional[int] = None
    is_completed: Optional[bool] = None
    msg_id: Optional[str] = None
    ref_msg: Optional[RefMessage] = None
    text_item: Optional[TextItem] = None
    image_item: Optional[ImageItem] = None
    voice_item: Optional[VoiceItem] = None
    file_item: Optional[FileItem] = None
    video_item: Optional[VideoItem] = None


@dataclass
class WeixinMessage:
    """Unified message from getUpdates or for sendMessage."""

    # Message types
    TYPE_USER = 1
    TYPE_BOT = 2

    # Message states
    STATE_NEW = 0
    STATE_GENERATING = 1
    STATE_FINISH = 2

    seq: Optional[int] = None
    message_id: Optional[int] = None
    from_user_id: Optional[str] = None
    to_user_id: Optional[str] = None
    client_id: Optional[str] = None
    create_time_ms: Optional[int] = None
    update_time_ms: Optional[int] = None
    delete_time_ms: Optional[int] = None
    session_id: Optional[str] = None
    group_id: Optional[str] = None
    message_type: Optional[int] = None
    message_state: Optional[int] = None
    item_list: Optional[list[MessageItem]] = None
    context_token: Optional[str] = None


@dataclass
class GetUpdatesResponse:
    ret: Optional[int] = None
    errcode: Optional[int] = None
    errmsg: Optional[str] = None
    msgs: list[WeixinMessage] = field(default_factory=list)
    get_updates_buf: Optional[str] = None
    longpolling_timeout_ms: Optional[int] = None


@dataclass
class GetConfigResponse:
    ret: Optional[int] = None
    errmsg: Optional[str] = None
    typing_ticket: Optional[str] = None


@dataclass
class GetUploadUrlResponse:
    upload_param: Optional[str] = None
    thumb_upload_param: Optional[str] = None


@dataclass
class QRCodeResponse:
    """Response from get_bot_qrcode endpoint."""

    qrcode: Optional[str] = None
    qrcode_img_content: Optional[str] = None


@dataclass
class QRStatusResponse:
    """Response from get_qrcode_status endpoint."""

    status: Optional[str] = None  # "wait" | "scaned" | "confirmed" | "expired"
    bot_token: Optional[str] = None
    ilink_bot_id: Optional[str] = None
    baseurl: Optional[str] = None
    ilink_user_id: Optional[str] = None


@dataclass
class LoginResult:
    """Result returned by the login flow."""

    token: str
    base_url: str
    account_id: str
    qr_image_base64: Optional[str] = None  # data URI of the last QR code shown
