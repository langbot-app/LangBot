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

from ..utils.image import DEFAULT_BASE64_MEDIA_LIMIT

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
                    return MediaCache._decode_base64(b64_data), mime_type
            if not data_url.startswith(('http://', 'https://', '/')):
                return MediaCache._decode_base64(data_url), 'application/octet-stream'
        except Exception:
            return None
        return None

    @staticmethod
    def _decode_base64(value: str) -> bytes:
        """Bound decoding before allocating a binary payload for persistence."""
        if len(value) > 4 * ((DEFAULT_BASE64_MEDIA_LIMIT + 2) // 3):
            raise ValueError('Inline image exceeds the media size limit')
        decoded = base64.b64decode(value, validate=True)
        if len(decoded) > DEFAULT_BASE64_MEDIA_LIMIT:
            raise ValueError('Inline image exceeds the media size limit')
        return decoded

    @staticmethod
    def _inline_image_payload(node: dict) -> str | None:
        """Recognize platform and provider image payloads without fetching URLs."""
        node_type = node.get('type')
        if node_type == 'Image':
            payload = node.get('base64')
            url = node.get('url')
        elif node_type in ('image', 'image_url', 'image_base64'):
            payload = node.get('image_base64')
            url = node.get('image_url')
            if isinstance(url, dict):
                url = url.get('url')
        else:
            return None
        if isinstance(payload, str) and payload:
            return payload
        if isinstance(url, str) and url.startswith('data:image/'):
            return url
        return None

    @classmethod
    def has_inline_images(cls, value: Any) -> bool:
        if isinstance(value, list):
            return any(cls.has_inline_images(item) for item in value)
        if isinstance(value, dict):
            return cls._inline_image_payload(value) is not None or any(
                cls.has_inline_images(item) for item in value.values() if isinstance(item, (list, dict))
            )
        return False

    @staticmethod
    def _clear_inline_image(node: dict) -> None:
        field = 'base64' if node.get('type') == 'Image' else 'image_base64'
        if node.get(field):
            node[field] = None
        url_field = 'url' if node.get('type') == 'Image' else 'image_url'
        url = node.get(url_field)
        if isinstance(url, str) and url.startswith('data:image/'):
            node[url_field] = None
        elif isinstance(url, dict) and str(url.get('url', '')).startswith('data:image/'):
            node[url_field] = {**url, 'url': None}

    @classmethod
    def redact_inline_images(cls, value: Any) -> Any:
        """Keep metadata-only records binary-free, including short raw base64."""
        if isinstance(value, list):
            return [cls.redact_inline_images(item) for item in value]
        if isinstance(value, dict):
            node = dict(value)
            if cls._inline_image_payload(node) is not None:
                cls._clear_inline_image(node)
            return {
                key: cls.redact_inline_images(item) if isinstance(item, (list, dict)) else item
                for key, item in node.items()
            }
        return value

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
            payload = self._inline_image_payload(node)
            if payload is not None:
                try:
                    parsed = await asyncio.to_thread(self.parse_data_url, payload)
                    if parsed is None:
                        raise ValueError('Invalid inline image payload')
                    raw_bytes, mime_type = parsed
                    hash_str, storage_key, size = await self.save_media(raw_bytes, mime_type)
                    url = f'/api/v1/files/media/{os.path.basename(storage_key)}'
                    if node.get('type') == 'Image':
                        current_url = node.get('url') or ''
                        if current_url and not current_url.startswith('data:'):
                            node['original_url'] = current_url
                        node['url'] = url
                    else:
                        current_url = node.get('image_url')
                        if isinstance(current_url, dict):
                            current_url = current_url.get('url')
                        if current_url and not current_url.startswith('data:'):
                            node['original_url'] = current_url
                        image_url = node.get('image_url')
                        node['image_url'] = {**image_url, 'url': url} if isinstance(image_url, dict) else {'url': url}
                    node.update(hash=hash_str, storage_key=storage_key, size=size, mime_type=mime_type)
                except Exception as e:
                    if hasattr(self.ap, 'logger') and self.ap.logger:
                        self.ap.logger.warning(f'Failed to externalize image to media cache: {e}')
                self._clear_inline_image(node)
            for k, v in list(node.items()):
                if isinstance(v, (list, dict)):
                    node[k] = await self.externalize_chain_dump(v)
            return node
        return chain_dump
