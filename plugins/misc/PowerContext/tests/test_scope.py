from __future__ import annotations

from types import SimpleNamespace

import pytest

from scope import LangBotIdentity, binding_key, session_name_from_session


def test_binding_keys_are_stable_opaque_and_mode_specific() -> None:
    identity = LangBotIdentity(
        bot_uuid="bot-private-id",
        session_name="group_private-id",
        sender_id="speaker-private-id",
    )

    session_key = binding_key(identity, "session")
    speaker_key = binding_key(identity, "speaker")
    bot_key = binding_key(identity, "bot")

    assert session_key["integration"] == "langbot"
    assert len(session_key["external_id"]) == 64
    assert (
        len(
            {
                session_key["external_id"],
                speaker_key["external_id"],
                bot_key["external_id"],
            }
        )
        == 3
    )
    assert "private" not in str([session_key, speaker_key, bot_key])
    assert binding_key(identity, "session") == session_key


def test_speaker_mode_requires_sender_identity() -> None:
    identity = LangBotIdentity(bot_uuid="bot", session_name="person_1")
    with pytest.raises(ValueError, match="sender ID"):
        binding_key(identity, "speaker")


def test_session_name_supports_enum_like_launcher_type() -> None:
    session = SimpleNamespace(
        launcher_type=SimpleNamespace(value="group"),
        launcher_id="42",
    )
    assert session_name_from_session(session) == "group_42"
