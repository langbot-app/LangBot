from __future__ import annotations

import abc

from ..core import app


HARD_MAX_STORAGE_OBJECT_BYTES = 64 * 1024 * 1024


def normalize_read_limit(max_bytes: int) -> int:
    """Validate a provider read limit without allowing callers to bypass the hard cap."""

    try:
        normalized = int(max_bytes)
    except (TypeError, ValueError):
        normalized = HARD_MAX_STORAGE_OBJECT_BYTES
    return min(max(normalized, 1), HARD_MAX_STORAGE_OBJECT_BYTES)


class StorageProvider(abc.ABC):
    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    async def shutdown(self) -> None:
        """Release provider-owned clients or pools."""

        return None

    @abc.abstractmethod
    async def save(
        self,
        key: str,
        value: bytes,
    ):
        pass

    @abc.abstractmethod
    async def load(
        self,
        key: str,
    ) -> bytes:
        pass

    async def load_bounded(self, key: str, *, max_bytes: int) -> bytes:
        """Fallback for third-party providers that have not implemented streaming bounds.

        Built-in providers override this method so the byte limit is enforced by
        the actual read. The size check still protects compatible providers from
        downloading a known oversized object.
        """

        max_bytes = normalize_read_limit(max_bytes)
        object_size = await self.size(key)
        if object_size > max_bytes:
            raise ValueError(f'Storage object exceeds the {max_bytes}-byte read limit')
        value = await self.load(key)
        if len(value) > max_bytes:
            raise ValueError(f'Storage object exceeds the {max_bytes}-byte read limit')
        return value

    @abc.abstractmethod
    async def exists(
        self,
        key: str,
    ) -> bool:
        pass

    @abc.abstractmethod
    async def delete(
        self,
        key: str,
    ):
        pass

    @abc.abstractmethod
    async def size(
        self,
        key: str,
    ) -> int:
        pass

    @abc.abstractmethod
    async def delete_dir_recursive(
        self,
        dir_path: str,
    ):
        pass
