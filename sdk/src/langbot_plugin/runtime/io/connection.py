from __future__ import annotations

import abc


MAX_MESSAGE_BYTES = 16 * 1024 * 1024
# A byte limit alone is insufficient: an untrusted peer can fragment one
# message into millions of empty or one-byte frames and exhaust Python object
# memory long before reaching MAX_MESSAGE_BYTES. Legitimate SDK senders use at
# most 1,024 stdio chunks or 256 default WebSocket fragments at the byte cap.
MAX_MESSAGE_FRAGMENTS = 4096


def split_utf8_chunks(message: str, max_bytes: int) -> list[str]:
    """Split text without breaking UTF-8 code points."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    chunks: list[str] = []
    if isinstance(max_bytes, int) and max_bytes >= 4:
        try:
            encoded = message.encode("utf-8")
        except UnicodeEncodeError:
            # Preserve the original per-character error for malformed text.
            pass
        else:
            start = 0
            while start < len(encoded):
                end = min(start + max_bytes, len(encoded))
                # Back up at most three continuation bytes to a code-point boundary.
                while end < len(encoded) and encoded[end] & 0xC0 == 0x80:
                    end -= 1
                chunks.append(encoded[start:end].decode("utf-8"))
                start = end
            return chunks
    current: list[str] = []
    current_size = 0
    for char in message:
        char_size = len(char.encode("utf-8"))
        if char_size > max_bytes:
            raise ValueError("max_bytes is smaller than one UTF-8 code point")
        if current and current_size + char_size > max_bytes:
            chunks.append("".join(current))
            current = []
            current_size = 0
        current.append(char)
        current_size += char_size
    if current:
        chunks.append("".join(current))
    return chunks


class Connection(abc.ABC):
    """The abstract base class for all connections."""

    @abc.abstractmethod
    async def send(self, message: str) -> None:
        pass

    @abc.abstractmethod
    async def receive(self) -> str:
        pass

    @abc.abstractmethod
    async def close(self) -> None:
        pass
