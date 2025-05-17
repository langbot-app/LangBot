from __future__ import annotations

import typing
import mimetypes
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

    def to_json(self) -> dict:
        return {
            'seq_id': self.seq_id,
            'timestamp': self.timestamp,
            'level': self.level.value,
            'text': self.text,
            'images': self.images,
            'message_session_id': self.message_session_id,
        }


class EventLogger:
    """used for logging bot events"""

    ap: app.Application

    seq_id_inc: int

    logs: list[EventLog]

    def __init__(
        self,
        name: str,
        ap: app.Application,
    ):
        self.name = name
        self.ap = ap
        self.logs = []
        self.seq_id_inc = 0

    async def get_logs(
        self, index_id: int, direction: int, max_count: int
    ) -> typing.Tuple[list[EventLog], int, int, int]:
        """
        获取日志

        Args:
            index_id: 索引ID，-1 表示末尾
            direction: 方向，1 表示向前，-1 表示向后
            max_count: 最大数量

        Returns:
            Tuple[list[EventLog], int, int, int]: 日志列表，起始索引，结束索引，总数量
        """

        if index_id < -1:
            index_id = len(self.logs)

        if direction == 1:
            max_id = min(len(self.logs), index_id + max_count)
            return self.logs[index_id:max_id], index_id, max_id, len(self.logs)
        else:
            min_id = max(0, index_id - max_count)
            return self.logs[min_id:index_id], min_id, index_id, len(self.logs)

    async def _add_log(
        self,
        level: EventLogLevel,
        text: str,
        images: typing.Optional[list[platform_message.Image]] = None,
        message_session_id: typing.Optional[str] = None,
        no_throw: bool = True,
    ):
        try:
            image_keys = []

            if images is None:
                images = []

            if message_session_id is None:
                message_session_id = ''

            if not isinstance(message_session_id, str):
                message_session_id = str(message_session_id)

            for img in images:
                img_bytes, mime_type = await img.get_bytes()
                extension = mimetypes.guess_extension(mime_type)
                if extension is None:
                    extension = '.jpg'
                image_key = f'{message_session_id}-{uuid.uuid4()}{extension}'
                await self.ap.storage_mgr.storage_provider.save(image_key, img_bytes)
                image_keys.append(image_key)

            self.logs.append(
                EventLog(
                    seq_id=self.seq_id_inc,
                    timestamp=int(time.time()),
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
