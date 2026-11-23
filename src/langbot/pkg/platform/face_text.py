"""Model-readable text for SDK Face components."""

from __future__ import annotations

from langbot_plugin.api.entities.builtin.platform import message as platform_message


def face_to_model_text(face: platform_message.Face) -> str:
    """Render a Face for model context without failing the whole message.

    The SDK's ``Face.__str__`` raises for an unknown rps gesture id and
    returns None for an unknown face_type; adapters can produce both.
    """
    try:
        text = str(face)
    except (KeyError, TypeError, ValueError):
        text = None
    return text if isinstance(text, str) else f'[表情]{face.face_name}'
