from __future__ import annotations

import enum
import typing

import pydantic


class EventLogLevel(enum.Enum):
    """Event log level"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EventLog(pydantic.BaseModel):
    seq_id: int
    """Event log sequence ID"""

    timestamp: int
    """Event log timestamp"""

    level: EventLogLevel
    """Event log level"""

    text: str
    """Event log text"""

    images: typing.Optional[list[str]] = None
    """Event log image URL list, need to get image through /api/v1/files/image/{uuid}"""

    message_session_id: typing.Optional[str] = None
    """Message session ID, only has value for message events"""

    def to_json(self) -> dict:
        return {
            "seq_id": self.seq_id,
            "timestamp": self.timestamp,
            "level": self.level.value,
            "text": self.text,
            "images": self.images,
            "message_session_id": self.message_session_id,
        }
