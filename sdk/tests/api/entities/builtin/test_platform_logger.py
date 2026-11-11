from __future__ import annotations

from langbot_plugin.api.entities.builtin.platform.logger import EventLog, EventLogLevel


def test_event_log_to_json_serializes_level_value_and_optional_fields():
    log = EventLog(
        seq_id=1,
        timestamp=123456,
        level=EventLogLevel.WARNING,
        text="careful",
        images=["img"],
        message_session_id="session",
    )

    assert log.to_json() == {
        "seq_id": 1,
        "timestamp": 123456,
        "level": "warning",
        "text": "careful",
        "images": ["img"],
        "message_session_id": "session",
    }
