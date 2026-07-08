from __future__ import annotations

import os
import aiofiles
import shutil

from ...core import app

from .. import provider


LOCAL_STORAGE_PATH = os.path.join('data', 'storage')


def _safe_resolve(base: str, key: str) -> str:
    """Resolve *key* under *base* and ensure the result stays inside *base*.

    Raises ``ValueError`` if the resolved path escapes the storage root
    (e.g. via absolute paths, ``..`` components, or symlinks).
    """
    # os.path.realpath resolves symlinks and normalises the path.
    resolved = os.path.realpath(os.path.join(base, key))
    canonical_base = os.path.realpath(base)
    # The resolved path must be *strictly* inside the base directory (or equal
    # to it only for directory operations).  We append os.sep so that a base of
    # "/data/storage" does not match "/data/storage_evil".
    if not (resolved == canonical_base or resolved.startswith(canonical_base + os.sep)):
        raise ValueError(f'Path traversal detected: key {key!r} resolves outside storage root')
    return resolved


class LocalStorageProvider(provider.StorageProvider):
    def __init__(self, ap: app.Application):
        super().__init__(ap)
        if not os.path.exists(LOCAL_STORAGE_PATH):
            os.makedirs(LOCAL_STORAGE_PATH)

    async def save(
        self,
        key: str,
        value: bytes,
    ):
        resolved = _safe_resolve(LOCAL_STORAGE_PATH, key)
        parent = os.path.dirname(resolved)
        if not os.path.exists(parent):
            os.makedirs(parent)
        async with aiofiles.open(resolved, 'wb') as f:
            await f.write(value)

    async def load(
        self,
        key: str,
    ) -> bytes:
        resolved = _safe_resolve(LOCAL_STORAGE_PATH, key)
        async with aiofiles.open(resolved, 'rb') as f:
            return await f.read()

    async def exists(
        self,
        key: str,
    ) -> bool:
        resolved = _safe_resolve(LOCAL_STORAGE_PATH, key)
        return os.path.exists(resolved)

    async def delete(
        self,
        key: str,
    ):
        resolved = _safe_resolve(LOCAL_STORAGE_PATH, key)
        os.remove(resolved)

    async def size(
        self,
        key: str,
    ) -> int:
        resolved = _safe_resolve(LOCAL_STORAGE_PATH, key)
        return os.path.getsize(resolved)

    async def delete_dir_recursive(
        self,
        dir_path: str,
    ):
        resolved = _safe_resolve(LOCAL_STORAGE_PATH, dir_path)
        # 直接删除整个目录
        if os.path.exists(resolved):
            shutil.rmtree(resolved)
