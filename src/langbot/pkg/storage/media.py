from __future__ import annotations

import asyncio
import base64
import copy
import datetime
import mimetypes
import os
import re
import xxhash
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...core import app
    from . import mgr as storage_mgr

DEFAULT_RETENTION_DAYS = 30
DEFAULT_MAX_SIZE_MB = 0
MEDIA_DIR = 'media_cache'
SAFE_MEDIA_FILENAME = re.compile(r'^[a-f0-9]{32,64}(\.[a-zA-Z0-9]{1,10})?$')


class MediaCache:
    """Content-addressable storage cache for images and media attachments.

    Deduplicates media files using xxHash3-128,
    offloads payloads from SQLite to StorageProvider, and implements LRU
    and age-based retention cleanup.
    """

    def __init__(self, ap: app.Application, storage_mgr: storage_mgr.StorageMgr):
        self.ap = ap
        self.storage_mgr = storage_mgr

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        """Compute content-addressable hash for binary data."""
        return xxhash.xxh3_128_hexdigest(data)

    @staticmethod
    def parse_data_url(data_url: str) -> tuple[bytes, str] | None:
        """Parse a data URL or raw base64 string into bytes and mime type."""
        if not data_url or not isinstance(data_url, str):
            return None
        try:
            if data_url.startswith('data:'):
                split_index = data_url.find(';base64,')
                if split_index != -1:
                    mime_type = data_url[5:split_index]
                    b64_data = data_url[split_index + 8 :]
                    return base64.b64decode(b64_data), mime_type
            # Try raw base64 if sufficiently long
            if len(data_url) > 20 and not data_url.startswith(('http://', 'https://', '/')):
                return base64.b64decode(data_url), 'application/octet-stream'
        except Exception:
            return None
        return None

    @staticmethod
    def guess_extension(mime_type: str | None, default: str = '.jpg') -> str:
        """Guess appropriate file extension from MIME type."""
        if not mime_type:
            return default
        mime_lower = mime_type.lower()
        if 'png' in mime_lower:
            return '.png'
        if 'webp' in mime_lower:
            return '.webp'
        if 'gif' in mime_lower:
            return '.gif'
        if 'jpeg' in mime_lower or 'jpg' in mime_lower:
            return '.jpg'
        ext = mimetypes.guess_extension(mime_type)
        if ext == '.jpe':
            return '.jpg'
        return ext or default

    async def save_media(self, data: bytes, mime_type: str | None = None) -> tuple[str, str, int]:
        """Save media bytes into content-addressable storage cache.

        Returns:
            Tuple of (hash_str, storage_key, byte_size)
        """
        hash_str = self.hash_bytes(data)
        ext = self.guess_extension(mime_type)
        storage_key = f'{MEDIA_DIR}/{hash_str}{ext}'
        provider = self.storage_mgr.storage_provider

        if not await provider.exists(storage_key):
            await provider.save(storage_key, data)
        else:
            await self.touch(storage_key)

        return hash_str, storage_key, len(data)

    async def get_media(self, filename_or_key: str) -> tuple[bytes, str] | None:
        """Retrieve media bytes and mime type by key or filename."""
        filename = os.path.basename(filename_or_key)
        if not SAFE_MEDIA_FILENAME.match(filename):
            return None
        storage_key = f'{MEDIA_DIR}/{filename}'
        provider = self.storage_mgr.storage_provider

        if not await provider.exists(storage_key):
            return None

        data = await self.storage_mgr._load_object_bounded(storage_key)
        mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        await self.touch(storage_key)
        return data, mime_type

    async def touch(self, storage_key: str) -> None:
        """Update access/modified time of a media file for LRU tracking."""
        provider = getattr(self.storage_mgr, 'storage_provider', None)
        if provider is not None and provider.__class__.__name__ == 'LocalStorageProvider':
            full_path = os.path.join('data', 'storage', storage_key)
            if os.path.exists(full_path):
                now = datetime.datetime.now().timestamp()
                try:
                    await asyncio.to_thread(os.utime, full_path, (now, now))
                except Exception:
                    # Failures to update mtime are intentionally ignored because LRU touch is opportunistic.
                    pass

    async def cleanup(
        self,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        max_size_mb: int = DEFAULT_MAX_SIZE_MB,
    ) -> dict[str, int]:
        """Perform age-based and LRU size-based cleanup on media cache.

        Args:
            retention_days: Retain media accessed within this many days (default 30).
            max_size_mb: Maximum total size in MB (0 means unlimited).

        Returns:
            Dictionary of cleanup metrics.
        """
        provider = getattr(self.storage_mgr, 'storage_provider', None)
        if provider is None or provider.__class__.__name__ != 'LocalStorageProvider':
            return {'expired_deleted': 0, 'size_deleted': 0, 'bytes_freed': 0}

        target_dir = Path('data/storage') / MEDIA_DIR
        if not target_dir.exists() or not target_dir.is_dir():
            return {'expired_deleted': 0, 'size_deleted': 0, 'bytes_freed': 0}

        now = datetime.datetime.now().timestamp()
        cutoff = (now - retention_days * 86400) if retention_days > 0 else 0

        expired_deleted = 0
        size_deleted = 0
        bytes_freed = 0
        remaining: list[tuple[Path, int, float]] = []

        for entry in target_dir.iterdir():
            if not entry.is_file():
                continue
            try:
                stat = entry.stat()
            except OSError:
                continue

            if cutoff > 0 and stat.st_mtime < cutoff:
                try:
                    entry.unlink(missing_ok=True)
                    expired_deleted += 1
                    bytes_freed += stat.st_size
                except OSError:
                    # Best-effort cleanup; file may already be gone or temporarily inaccessible.
                    pass
            else:
                remaining.append((entry, stat.st_size, stat.st_mtime))

        if max_size_mb > 0:
            max_bytes = max_size_mb * 1024 * 1024
            total_bytes = sum(item[1] for item in remaining)
            if total_bytes > max_bytes:
                remaining.sort(key=lambda item: item[2])
                for path, size, _ in remaining:
                    if total_bytes <= max_bytes:
                        break
                    try:
                        path.unlink(missing_ok=True)
                        size_deleted += 1
                        bytes_freed += size
                        total_bytes -= size
                    except OSError:
                        # Best-effort cleanup; file may already be gone or temporarily inaccessible.
                        continue

        return {
            'expired_deleted': expired_deleted,
            'size_deleted': size_deleted,
            'bytes_freed': bytes_freed,
        }

    async def externalize_chain_dump(self, chain_dump: Any) -> Any:
        """Recursively extract raw base64 media into cache and replace with references."""
        if isinstance(chain_dump, list):
            return [await self.externalize_chain_dump(item) for item in chain_dump]
        if isinstance(chain_dump, dict):
            node = copy.copy(chain_dump)
            node_type = node.get('type')
            if node_type == 'Image':
                b64 = node.get('base64')
                if b64 and isinstance(b64, str):
                    try:
                        parsed = self.parse_data_url(b64)
                        if parsed is not None:
                            raw_bytes, mime_type = parsed
                            hash_str, storage_key, size = await self.save_media(raw_bytes, mime_type)
                            filename = os.path.basename(storage_key)
                            current_url = node.get('url') or ''
                            if current_url and not current_url.startswith('data:'):
                                node['original_url'] = current_url
                            node['url'] = f'/api/v1/files/media/{filename}'
                            node['base64'] = None
                            node['hash'] = hash_str
                            node['storage_key'] = storage_key
                            node['size'] = size
                            node['mime_type'] = mime_type
                    except Exception as e:
                        if hasattr(self.ap, 'logger') and self.ap.logger:
                            self.ap.logger.warning(f'Failed to externalize image to media cache: {e}')
                        node['base64'] = None
            for k, v in list(node.items()):
                if isinstance(v, (list, dict)):
                    node[k] = await self.externalize_chain_dump(v)
            return node
        return chain_dump
