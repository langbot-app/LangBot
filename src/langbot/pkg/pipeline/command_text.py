from __future__ import annotations

import typing


def command_text_from_chain(message_chain: typing.Any) -> str:
    """Return the text a user typed, ignoring non-text platform components.

    Group callbacks prepend ``Source`` and ``At`` components. Calling
    ``str(message_chain)`` renders those as prefixes such as
    ``@aibtZ-...!stop``, which hides the command behind a non-``!`` start.
    Concatenating only text components keeps command detection and dispatch
    consistent for private and group messages.
    """

    try:
        components = list(message_chain or [])
    except TypeError:
        components = []

    text = ''.join(str(getattr(component, 'text', '') or '') for component in components).strip()
    if text:
        return text
    return str(message_chain or '').strip()


def command_name_from_chain(
    message_chain: typing.Any,
    prefixes: typing.Iterable[str],
) -> str | None:
    """Return the lower-cased command name after a configured prefix."""

    message_text = command_text_from_chain(message_chain)
    for prefix in prefixes:
        if message_text.startswith(prefix):
            command_text = message_text[len(prefix) :].strip()
            return command_text.split(maxsplit=1)[0].lower() if command_text else None
    return None


def strip_command_prefix(message_text: str, prefixes: typing.Iterable[str]) -> str:
    """Remove the first matching command prefix from a text message."""

    for prefix in prefixes:
        if message_text.startswith(prefix):
            return message_text[len(prefix) :].lstrip()
    return message_text[1:].lstrip() if message_text else message_text


__all__ = [
    'command_name_from_chain',
    'command_text_from_chain',
    'strip_command_prefix',
]
