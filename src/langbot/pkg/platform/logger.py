from __future__ import annotations

import typing
import mimetypes
import time
import enum
import pydantic
import traceback
import uuid

from ..core import app
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_event_logger


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


MAX_LOG_COUNT = 200
DELETE_COUNT_PER_TIME = 50


class EventLogger(abstract_platform_event_logger.AbstractEventLogger):
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

    async def get_logs(self, from_seq_id: int, max_count: int) -> typing.Tuple[list[EventLog], int]:
        """
        获取日志，从 from_seq_id 开始获取 max_count 条历史日志

        Args:
            from_seq_id: 起始序号，-1 表示末尾
            max_count: 最大数量

        Returns:
            Tuple[list[EventLog], int]: 日志列表，日志总数
        """
        if len(self.logs) == 0:
            return [], 0

        if from_seq_id <= -1:
            from_seq_id = self.logs[-1].seq_id

        min_seq_id_in_logs = self.logs[0].seq_id
        max_seq_id_in_logs = self.logs[-1].seq_id

        if from_seq_id < min_seq_id_in_logs:  # 需要的整个范围都已经被删除
            return [], len(self.logs)

        if (
            from_seq_id > max_seq_id_in_logs and from_seq_id - max_count > max_seq_id_in_logs
        ):  # 需要的整个范围都还没生成
            return [], len(self.logs)

        end_index = 1

        for i, log in enumerate(self.logs):
            if log.seq_id >= from_seq_id:
                end_index = i + 1
                break

        start_index = max(0, end_index - max_count)

        if max_count > 0:
            return self.logs[start_index:end_index], len(self.logs)
        else:
            return [], len(self.logs)

    async def _truncate_logs(self):
        if len(self.logs) > MAX_LOG_COUNT:
            for i in range(DELETE_COUNT_PER_TIME):
                for image_key in self.logs[i].images:  # type: ignore
                    await self.ap.storage_mgr.storage_provider.delete(image_key)
            self.logs = self.logs[DELETE_COUNT_PER_TIME:]

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
                image_key = f'bot_log_images/{message_session_id}-{uuid.uuid4()}{extension}'
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

            await self._truncate_logs()

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
