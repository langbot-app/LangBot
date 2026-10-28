from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any


SUPPORTED_SCOPE_MODES = frozenset({"session", "speaker", "bot"})


@dataclass(frozen=True)
class LangBotIdentity:
    bot_uuid: str
    session_name: str
    sender_id: str = ""
    sender_name: str = ""


def session_name_from_session(session: Any) -> str:
    launcher_type = getattr(session, "launcher_type", "")
    launcher_value = getattr(launcher_type, "value", launcher_type)
    launcher_id = getattr(session, "launcher_id", "")
    return f"{launcher_value}_{launcher_id}"


def binding_key(identity: LangBotIdentity, mode: str) -> dict[str, str]:
    normalized_mode = str(mode or "session").strip().lower()
    if normalized_mode not in SUPPORTED_SCOPE_MODES:
        raise ValueError(f"unsupported scope mode: {normalized_mode}")

    if normalized_mode == "speaker":
        if not identity.sender_id:
            raise ValueError("speaker scope requires a current sender ID")
        raw_identity = f"{identity.bot_uuid}\0{identity.sender_id}"
    elif normalized_mode == "bot":
        raw_identity = identity.bot_uuid
    else:
        raw_identity = f"{identity.bot_uuid}\0{identity.session_name}"

    external_id = hashlib.sha256(raw_identity.encode("utf-8")).hexdigest()
    return {
        "integration": "langbot",
        "kind": normalized_mode,
        "external_id": external_id,
    }
