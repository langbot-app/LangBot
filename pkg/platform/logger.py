from __future__ import annotations

import typing
import time
import enum
import pydantic
import traceback
import uuid

from ..core import app
from .types import message as platform_message


class EventLogLevel(enum.Enum):
    """日志级别"""

    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'


class EventLog(pydantic.BaseModel):
    seq_id: int
    """日志序号"""

    timestamp: int
    """日志时间戳"""

    level: EventLogLevel
    """日志级别"""

    text: str
    """日志文本"""

    images: typing.Optional[list[str]] = None
    """日志图片 URL 列表，需要通过 /api/v1/image/{uuid} 获取图片"""

    message_session_id: typing.Optional[str] = None
    """消息会话ID，仅收发消息事件有值"""


class EventLogger:
    """used for logging bot events"""

    ap: app.Application

    seq_id_inc: int

    def __init__(
        self,
        name: str,
        ap: app.Application,
    ):
        self.name = name
        self.ap = ap
        self.logs = []
        self.seq_id_inc = 0

    async def _add_log(
        self,
        level: EventLogLevel,
        text: str,
        images: typing.Optional[list[platform_message.Image]] = None,
        message_session_id: typing.Optional[str] = None,
        no_throw: bool = True,
    ):
        try:
            img_bytes = []
            for img in images:
                img_bytes.append(await img.get_bytes())

            image_keys = []
            for img_byte in img_bytes:
                image_key = str(uuid.uuid4())
                await self.ap.storage_mgr.storage_provider.save(image_key, img_byte)
                image_keys.append(image_key)

            self.logs.append(
                EventLog(
                    seq_id=self.seq_id_inc,
                    timestamp=time.time(),
                    level=level,
                    text=text,
                    images=image_keys,
                    message_session_id=message_session_id,
                )
            )
            self.seq_id_inc += 1
        except Exception as e:
            if not no_throw:
                raise e
            else:
                traceback.print_exc()

    async def info(
        self,
        text: str,
        images: typing.Optional[list[platform_message.Image]] = None,
        message_session_id: typing.Optional[str] = None,
        no_throw: bool = True,
    ):
        await self._add_log(
            level=EventLogLevel.INFO,
            text=text,
            images=images,
            message_session_id=message_session_id,
            no_throw=no_throw,
        )

    async def debug(
        self,
        text: str,
        images: typing.Optional[list[platform_message.Image]] = None,
        message_session_id: typing.Optional[str] = None,
        no_throw: bool = True,
    ):
        await self._add_log(
            level=EventLogLevel.DEBUG,
            text=text,
            images=images,
            message_session_id=message_session_id,
            no_throw=no_throw,
        )

    async def warning(
        self,
        text: str,
        images: typing.Optional[list[platform_message.Image]] = None,
        message_session_id: typing.Optional[str] = None,
        no_throw: bool = True,
    ):
        await self._add_log(
            level=EventLogLevel.WARNING,
            text=text,
            images=images,
            message_session_id=message_session_id,
            no_throw=no_throw,
        )

    async def error(
        self,
        text: str,
        images: typing.Optional[list[platform_message.Image]] = None,
        message_session_id: typing.Optional[str] = None,
        no_throw: bool = True,
    ):
        await self._add_log(
            level=EventLogLevel.ERROR,
            text=text,
            images=images,
            message_session_id=message_session_id,
            no_throw=no_throw,
        )
