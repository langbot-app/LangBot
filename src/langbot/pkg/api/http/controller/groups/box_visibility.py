from __future__ import annotations


def should_hide_box_runtime_status(edition: str, box_enabled: bool | None) -> bool:
    return edition == 'cloud' and box_enabled is False
