from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class WecomCSCursorCheckpoint:
    bot_uuid: str
    open_kfid: str
    cursor: str
    bootstrapped: bool


@dataclass
class WecomCSMessageState:
    bot_uuid: str
    open_kfid: str
    msgid: str
    external_userid: str
    msgtype: str
    send_time: int | None
    process_status: str
    reply_status: str
    retry_count: int
    last_error_stage: str
    last_error: str
    first_seen_at: int
    queued_at: int | None
    processing_at: int | None
    done_at: int | None
    reply_at: int | None
    failed_at: int | None
    updated_at: int
    content_preview: str

    def to_dict(self) -> dict:
        return asdict(self)
