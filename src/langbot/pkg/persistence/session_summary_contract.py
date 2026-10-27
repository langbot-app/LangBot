"""Payload-free contracts for interactive conversation lists."""

from dataclasses import dataclass
import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SessionListFilter:
    bot_ids: tuple[str, ...] = ()
    pipeline_ids: tuple[str, ...] = ()
    start_time: datetime.datetime | None = None
    end_time: datetime.datetime | None = None
    user_query: str | None = None
    is_active: bool | None = None


class SessionSummaryReader(Protocol):
    """Read stored summaries without consulting or repairing historical ledgers."""

    async def list_page(
        self, workspace: str, filters: SessionListFilter, limit: int, offset: int
    ) -> tuple[list[dict], int]: ...


@dataclass(frozen=True, slots=True)
class SessionSummaryChange:
    workspace: str
    bot_id: str
    session_id: str
    source_key: str
    timestamp: datetime.datetime
    bot_name: str
    pipeline_id: str = ''
    pipeline_name: str = ''
    platform: str | None = None
    user_id: str | None = None
    user_name: str | None = None
    role: str = 'user'
    event_id: str | None = None


def message_source_key(message_id: str) -> str:
    """Distinct message records remain distinct even when they share an event."""
    return f'message:{message_id}'
