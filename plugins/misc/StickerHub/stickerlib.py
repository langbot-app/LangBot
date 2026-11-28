"""Pure helpers and the plugin-storage backend for StickerHub.

The storage layer is deliberately dependency-free: every Host call goes
through a tiny async protocol (``get_plugin_storage`` / ``set_plugin_storage``
/ ``delete_plugin_storage`` / ``get_plugin_storage_keys``) so the whole store can
be exercised from a stub Host in unit tests without a live LangBot instance.

Stickers are content-addressed: the raw bytes live once, under
``blob:<sha256>``, and every named sticker is a small metadata row that records
the slug, mime type and the filename the asset route serves.  Identical bytes
uploaded under several names share one blob, and deleting the last reference to
a blob removes it again.  This keeps the hot path (one write on first upload,
one delete on the last reference) proportional to the number of new/removed
stickers instead of rewriting an index with every change.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from langbot_plugin.entities.io.errors import ActionCallError

logger = logging.getLogger(__name__)

# plugin_storage key namespace. Keys are scoped by installation inside the
# plugin's own key, exactly like HumanTakeover's ``ht_session_v2_*`` keys: Host
# rows are keyed by [instance, workspace, owner_type, owner, key] with no
# installation dimension.
STORAGE_PREFIX = "sh"
META_KIND = "meta"
BLOB_KIND = "blob"
UPLOAD_KIND = "upload"
STORAGE_SCHEMA_VERSION = 1

# Raw bytes per upload chunk. 256 KiB base64-encodes to ~341 KiB, so the HTTP
# body of one ``/upload/chunk`` call stays flat no matter how large the image
# is (the page-api transport caps a request body at 10 MiB).
UPLOAD_CHUNK_BYTES = 256 * 1024
# An abandoned upload session is dropped once it has been idle this long.
UPLOAD_SESSION_TTL_SECONDS = 15 * 60

# A snapshot of the scope's keys/metadata is reused for this long. The page
# fetches ``/list`` and ``/stats`` back to back on every refresh; without this
# the same 2000 rows would be scanned twice. Every mutation invalidates it.
SNAPSHOT_TTL_SECONDS = 3.0
# Parallel metadata reads keep a cold scan off the serial round-trip path.
SNAPSHOT_READ_CONCURRENCY = 16

# 8 MiB is the performance budget shared with HumanTakeover: it also leaves
# ample room for the SDK's base64 encoding inside the 16 MiB transport frame.
DEFAULT_MAX_STICKER_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_STICKERS = 2000

SUPPORTED_MIMES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/bmp",
    }
)

EXT_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}

MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

_SLUG_RE = re.compile(r"[\W_]+", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_COLLAPSE_RE = re.compile(r"-{2,}")
# The scope itself is colon-separated, so the non-greedy tail matches up to the
# first ``:meta:`` separator. Slugs cannot contain ``:`` (slugify strips it), so
# the match is unambiguous.
_KEY_RE = re.compile(r"^sh:.+?:meta:(?P<slug>.+)$")
_UPLOAD_KEY_RE = re.compile(r"^sh:.+?:upload:(?P<session>[0-9a-zA-Z]+):(?P<index>\d+)$")


def format_bytes(value: int) -> str:
    """Return a short human size: ``6980 B`` / ``6.8 KB`` / ``7.1 MB``.

    The page shows the used total, so a raw kilobyte figure stops being
    readable right around the second sticker.
    """

    try:
        size = float(int(value))
    except (TypeError, ValueError):
        size = 0.0
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


@dataclass
class _Snapshot:
    """One scope's key scan plus the metadata rows resolved from it."""

    metas: list[dict[str, Any]] = field(default_factory=list)
    blob_keys: list[str] = field(default_factory=list)
    meta_keys: list[str] = field(default_factory=list)
    taken_at: float = 0.0


def slugify(name: str) -> str:
    """Return a stable, filesystem- and storage-safe slug for one sticker name.

    Unicode word characters are preserved (so a Chinese sticker keeps its
    name), everything else collapses to a single ``-``.
    """

    value = _WS_RE.sub("-", str(name or "").strip()).lower()
    value = _SLUG_RE.sub("-", value).strip("-")
    value = _COLLAPSE_RE.sub("-", value)
    if not value:
        value = "sticker"
    return value[:120]


def sniff_mime(data: bytes) -> str | None:
    """Return a supported mime type implied by the leading magic bytes."""

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] == b"BM":
        return "image/bmp"
    return None


def guess_ext(mime_type: str | None, hint: str | None = None) -> str:
    """Return the file extension for a mime type, favouring a hint on mismatch."""

    mime = str(mime_type or "").split(";")[0].strip().lower()
    if mime in EXT_BY_MIME:
        return EXT_BY_MIME[mime]
    if hint:
        suffix = str(hint).lower()
        if suffix.startswith("."):
            suffix = suffix[1:]
        if f".{suffix}" in MIME_BY_EXT:
            return f".{suffix}"
    return ".jpg"


def normalize_mime(data: bytes, provided: str | None, hint_ext: str | None = None) -> str | None:
    """Resolve the mime type of ``data`` from the provided value and the bytes.

    Returns ``None`` when the bytes are neither recognised by magic bytes nor
    explicitly labelled, so the store never silently labels arbitrary bytes as
    an image.
    """

    provided = str(provided or "").split(";")[0].strip().lower()
    sniffed = sniff_mime(data)
    if sniffed:
        return sniffed
    if provided in SUPPORTED_MIMES:
        return provided
    if provided:
        return provided
    if hint_ext:
        suffix = str(hint_ext).lower()
        if not suffix.startswith("."):
            suffix = f".{suffix}"
        guessed = MIME_BY_EXT.get(suffix)
        if guessed:
            return guessed
    return None


def filename_for(slug: str, sha256: str, ext: str) -> str:
    """Return the served filename: a readable ASCII stem plus a content hash."""

    stem = re.sub(r"[^0-9A-Za-z]+", "-", slug).strip("-").lower()
    stem = stem[:48] if stem else "sticker"
    return f"{stem}-{sha256[:12]}{ext}"


def media_path(filename: str) -> str:
    """Return the plugin-relative asset path served by LangBot."""

    return f"assets/stickers/{filename}"


def build_media_url(
    *,
    public_base_url: str,
    author: str,
    plugin_name: str,
    filename: str,
) -> str:
    """Return the stable absolute URL for one served sticker file.

    The LangBot asset route is
    ``GET /api/v1/plugins/<author>/<plugin_name>/assets/<path>``. The route
    normalizes the requested path back to ``assets/<path>``, so the URL carries
    ``assets/stickers/<filename>`` and the plugin process resolves it against
    its own ``assets/stickers`` directory.
    """

    base = str(public_base_url or "").strip().rstrip("/")
    path = (
        f"/api/v1/plugins/{author}/{plugin_name}/assets/stickers/{filename}"
    )
    if not base:
        return path
    return f"{base}{path}"


def parse_data_url(value: str) -> tuple[bytes, str | None]:
    """Parse ``data:<mime>;base64,<payload>`` or raw base64 into (bytes, mime)."""

    import base64 as _base64

    text = str(value or "").strip()
    if not text.startswith("data:") or ";base64," not in text:
        return b"", None
    head, _, payload = text.partition(";base64,")
    mime = head[5:].strip().lower() or None
    try:
        data = _base64.b64decode(payload, validate=False)
    except ValueError:
        return b"", mime
    return data, mime


class StickerStore:
    """Installation-scoped content-addressed sticker store.

    The object is stateless apart from the plugin binding and a single
    ``asyncio.Lock``, so it is safe to recreate per scope and to keep on the
    process-wide object graph across installations (each installation gets its
    own store, and the revoked one is dropped by ``on_installation_revoked``).
    """

    def __init__(
        self,
        plugin: Any,
        scope: str,
        *,
        max_bytes: int = DEFAULT_MAX_STICKER_BYTES,
        max_stickers: int = DEFAULT_MAX_STICKERS,
        lock: asyncio.Lock | None = None,
    ) -> None:
        self._plugin = plugin
        self._scope = scope
        self._max_bytes = max(1, int(max_bytes))
        self._max_stickers = max(1, int(max_stickers))
        self._lock = lock or asyncio.Lock()
        self._snapshot: _Snapshot | None = None

    # ==================== key layout ====================

    @property
    def scope(self) -> str:
        return self._scope

    def _meta_key(self, slug: str) -> str:
        return f"{STORAGE_PREFIX}:{self._scope}:{META_KIND}:{slug}"

    def _blob_key(self, sha256: str) -> str:
        return f"{STORAGE_PREFIX}:{self._scope}:{BLOB_KIND}:{sha256}"

    def _upload_key(self, session: str, index: int) -> str:
        return f"{STORAGE_PREFIX}:{self._scope}:{UPLOAD_KIND}:{session}:{index:06d}"

    def _matches_scope(self, key: str) -> bool:
        return key.startswith(f"{STORAGE_PREFIX}:{self._scope}:")

    @staticmethod
    def _slug_from_key(key: str) -> str | None:
        match = _KEY_RE.match(key)
        if not match:
            return None
        return match.group("slug")

    @staticmethod
    def _meta_to_dict(raw: bytes) -> dict[str, Any] | None:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        payload.setdefault("slug", "")
        payload.setdefault("name", payload["slug"])
        return payload

    def _to_public(self, meta: dict[str, Any], *, base_url: str | None) -> dict[str, Any]:
        out = dict(meta)
        filename = meta.get("filename") or filename_for(
            meta.get("slug", ""), meta.get("sha256", ""), meta.get("ext", ".png")
        )
        out["filename"] = filename
        out["path"] = media_path(filename)
        if base_url is None:
            out.pop("url", None)
        else:
            out["url"] = build_media_url(
                public_base_url=base_url,
                author=self._plugin.metadata_author,
                plugin_name=self._plugin.metadata_name,
                filename=filename,
            )
        out.pop("_dirty", None)
        return out

    # ==================== low level storage ====================

    async def _read_raw(self, key: str) -> bytes | None:
        # A missing plugin-storage key comes back from the Host as a failed
        # action, not as a ``KeyError``: catch both the SDK error and the
        # conventional key error so the store degrades to "absent".
        try:
            return await self._plugin.get_plugin_storage(key)
        except (KeyError, ActionCallError):
            return None

    async def _write_raw(self, key: str, value: bytes) -> None:
        await self._plugin.set_plugin_storage(key, value)

    async def _delete_raw(self, key: str) -> None:
        await self._plugin.delete_plugin_storage(key)

    async def _keys(self) -> list[str]:
        keys = list(await self._plugin.get_plugin_storage_keys())
        return [key for key in keys if isinstance(key, str) and self._matches_scope(key)]

    def _invalidate(self) -> None:
        self._snapshot = None

    async def _scan(self, *, force: bool = False) -> _Snapshot:
        """Return the scope's metadata in one pass, from cache when fresh.

        ``list``/``stats``/``total``/eviction all need every row that
        ``_keys`` found; reading them one by one made one page refresh cost
        ``2 * max_stickers`` Host round trips. Scan once, resolve the metadata
        concurrently, and reuse the result for the follow-up call.
        """

        cached = self._snapshot
        if (
            cached is not None
            and not force
            and time.monotonic() - cached.taken_at < SNAPSHOT_TTL_SECONDS
        ):
            return cached

        keys = await self._keys()
        meta_keys = [key for key in keys if self._slug_from_key(key) is not None]
        blob_keys = [key for key in keys if f":{BLOB_KIND}:" in key]
        meta_keys.sort()

        gate = asyncio.Semaphore(SNAPSHOT_READ_CONCURRENCY)

        async def read(key: str) -> tuple[str, bytes | None]:
            async with gate:
                return key, await self._read_raw(key)

        snapshot = _Snapshot(blob_keys=blob_keys, meta_keys=meta_keys)
        for key, raw in await asyncio.gather(*(read(key) for key in meta_keys)):
            if raw is None:
                continue
            meta = self._meta_to_dict(raw)
            slug = self._slug_from_key(key)
            if meta is None or slug is None:
                continue
            meta.setdefault("slug", slug)
            snapshot.metas.append(meta)
        snapshot.taken_at = time.monotonic()
        self._snapshot = snapshot
        return snapshot

    async def _read_meta(self, slug: str) -> dict[str, Any] | None:
        raw = await self._read_raw(self._meta_key(slug))
        if raw is None:
            return None
        meta = self._meta_to_dict(raw)
        if meta is not None:
            meta.setdefault("slug", slug)
        return meta

    # ==================== public API ====================

    async def add(
        self,
        name: str,
        data: bytes,
        mime: str | None = None,
        *,
        source: str = "human",
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Store ``data`` under ``name`` and return its public metadata."""

        name = str(name or "").strip()
        if not name:
            raise ValueError("sticker name is required")
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("sticker data must be bytes")
        data = bytes(data)
        if not data:
            raise ValueError("sticker image is empty")
        if len(data) > self._max_bytes:
            raise ValueError(
                f"sticker image is {len(data)} bytes; the maximum is {self._max_bytes} bytes"
            )

        mime = normalize_mime(data, mime)
        if mime not in SUPPORTED_MIMES:
            raise ValueError(
                f"unsupported image type {mime!r}; supported: {', '.join(sorted(SUPPORTED_MIMES))}"
            )
        ext = guess_ext(mime, hint=str(name).rsplit('.', 1)[-1] if '.' in str(name) else None)
        sha = hashlib.sha256(data).hexdigest()
        slug = slugify(name)
        filename = filename_for(slug, sha, ext)

        async with self._lock:
            try:
                blob_key = self._blob_key(sha)
                meta_key = self._meta_key(slug)
                try:
                    existing_blob = await self._read_raw(blob_key)
                except Exception:  # noqa: BLE001 - treat an ambiguous read as absent
                    existing_blob = None
                if existing_blob is None:
                    await self._write_raw(blob_key, data)

                now = time.time()
                previous = await self._read_meta(slug)
                created_at = previous.get("created_at", now) if previous else now
                meta = {
                    "schema": STORAGE_SCHEMA_VERSION,
                    "slug": slug,
                    "name": previous.get("name", name) if previous else name,
                    "mime": mime,
                    "ext": ext,
                    "size": len(data),
                    "sha256": sha,
                    "filename": filename,
                    "created_at": created_at,
                    "updated_at": now,
                    "source": str(source or "human"),
                }
                await self._write_raw(
                    meta_key, json.dumps(meta, ensure_ascii=False).encode("utf-8")
                )
                removed = await self._evict_over_limit()
            finally:
                self._invalidate()
        return self._to_public(meta, base_url=base_url) | {"evicted": removed}

    # ==================== chunked upload ====================

    async def begin_upload(self) -> str:
        """Open an upload session and return its token.

        The page then posts 256 KiB slices to :meth:`put_upload_chunk` and
        finally calls :meth:`finish_upload`, so no single HTTP request carries
        the whole (up to 8 MiB) image.
        """

        session = secrets.token_hex(8)
        async with self._lock:
            try:
                # Opening a session is a good moment to reap abandoned ones:
                # the 8 MiB blobs they hold would otherwise linger forever.
                try:
                    await self._expire_uploads()
                except Exception:  # noqa: BLE001 - reaping is best effort
                    logger.warning("StickerHub could not reap stale uploads", exc_info=True)
                await self._write_raw(
                    self._upload_key(session, 0),
                    json.dumps({"created_at": time.time()}).encode("utf-8"),
                )
            finally:
                self._invalidate()
        return session

    async def put_upload_chunk(self, session: str, index: int, payload: bytes) -> int:
        """Store one decoded chunk; returns the bytes accumulated so far."""

        session = str(session or "").strip()
        if not re.fullmatch(r"[0-9a-zA-Z]{1,64}", session):
            raise ValueError("invalid upload session")
        index = int(index)
        if index < 0:
            raise ValueError("chunk index must not be negative")
        if not payload:
            raise ValueError("upload chunk is empty")
        if index * UPLOAD_CHUNK_BYTES + len(payload) > self._max_bytes:
            raise ValueError(
                f"sticker image exceeds the {self._max_bytes}-byte limit"
            )

        async with self._lock:
            try:
                await self._write_raw(self._upload_key(session, index + 1), payload)
                received = await self._upload_size(session)
            finally:
                self._invalidate()
        return received

    async def finish_upload(
        self,
        name: str,
        session: str,
        *,
        mime: str | None = None,
        source: str = "human",
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Assemble the session's chunks, store the sticker and drop the session."""

        session = str(session or "").strip()
        if not re.fullmatch(r"[0-9a-zA-Z]{1,64}", session):
            raise ValueError("invalid upload session")
        chunks = await self._upload_chunks(session)
        if not chunks:
            raise ValueError("upload session has no data")
        data = b"".join(chunks)
        try:
            return await self.add(name, data, mime, source=source, base_url=base_url)
        finally:
            await self._drop_upload(session)

    async def abort_upload(self, session: str) -> None:
        await self._drop_upload(str(session or "").strip())

    async def _upload_chunks(self, session: str, *, contiguous: bool = True) -> list[bytes]:
        snapshot_keys = await self._keys()
        indices = sorted(
            int(match.group("index"))
            for key in snapshot_keys
            if (match := _UPLOAD_KEY_RE.match(key)) and match.group("session") == session
        )
        # Index 0 is the session marker itself, not a payload chunk.
        payload_indices = [index for index in indices if index > 0]
        if not payload_indices:
            return []
        if contiguous and payload_indices != list(range(1, len(payload_indices) + 1)):
            raise ValueError("upload session has a gap in its chunks")
        chunks = []
        for index in payload_indices:
            raw = await self._read_raw(self._upload_key(session, index))
            if raw is not None:
                chunks.append(raw)
        return chunks

    async def _upload_size(self, session: str) -> int:
        # A partially uploaded session is legitimately gappy; only finishing
        # has to insist on a contiguous run of chunks.
        return sum(len(chunk) for chunk in await self._upload_chunks(session, contiguous=False))

    async def _drop_upload(self, session: str) -> None:
        if not session:
            return
        for key in await self._keys():
            match = _UPLOAD_KEY_RE.match(key)
            if match and match.group("session") == session:
                await self._delete_raw(key)
        self._invalidate()

    async def _expire_uploads(self) -> int:
        """Drop upload sessions idle for longer than the TTL."""

        keys = await self._keys()
        sessions: dict[str, list[str]] = {}
        for key in keys:
            match = _UPLOAD_KEY_RE.match(key)
            if match:
                sessions.setdefault(match.group("session"), []).append(key)
        cutoff = time.time() - UPLOAD_SESSION_TTL_SECONDS
        expired = 0
        for session, session_keys in sessions.items():
            marker = await self._read_raw(self._upload_key(session, 0))
            created = 0.0
            if marker:
                try:
                    created = float(json.loads(marker.decode("utf-8")).get("created_at", 0))
                except (ValueError, UnicodeDecodeError):
                    created = 0.0
            if created and created < cutoff:
                for key in session_keys:
                    await self._delete_raw(key)
                expired += 1
        if expired:
            self._invalidate()
        return expired

    async def get(self, name: str, *, base_url: str | None = None) -> dict[str, Any] | None:
        slug = slugify(name)
        async with self._lock:
            meta = await self._read_meta(slug)
        if meta is None:
            return None
        return self._to_public(meta, base_url=base_url)

    async def get_bytes(self, name: str) -> tuple[bytes, dict[str, Any]] | None:
        slug = slugify(name)
        async with self._lock:
            meta = await self._read_meta(slug)
            if meta is None:
                return None
            data = await self._read_raw(self._blob_key(meta.get("sha256", "")))
        if data is None:
            return None
        return data, meta

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Return a page of sticker metadata: ``{"items", "total", "count"}``."""

        async with self._lock:
            snapshot = await self._scan()
        items = sorted(
            snapshot.metas,
            key=lambda item: (item.get("created_at", 0), item.get("slug", "")),
            reverse=True,
        )
        start = max(0, int(offset))
        window = len(items) if not limit else max(0, int(limit))
        page = items[start : start + window]
        return {
            "items": [self._to_public(meta, base_url=base_url) for meta in page],
            "total": len(items),
            "count": len(page),
        }

    async def total(self) -> int:
        async with self._lock:
            snapshot = await self._scan()
        return len(snapshot.metas)

    async def stats(self) -> dict[str, Any]:
        """Return count/bytes/mime breakdown for one scope.

        Reuses the snapshot ``list`` just built, so one page refresh scans the
        key space once instead of once per endpoint.
        """

        async with self._lock:
            snapshot = await self._scan()
        total_bytes = 0
        mime_counts: dict[str, int] = {}
        for meta in snapshot.metas:
            total_bytes += int(meta.get("size", 0))
            mime = str(meta.get("mime") or "unknown")
            mime_counts[mime] = mime_counts.get(mime, 0) + 1
        return {
            "count": len(snapshot.metas),
            "bytes": total_bytes,
            "display_bytes": format_bytes(total_bytes),
            "mime_counts": mime_counts,
            "max_sticker_bytes": self._max_bytes,
            "max_stickers": self._max_stickers,
            "scope": self._scope,
        }

    async def delete(self, name: str) -> bool:
        slug = slugify(name)
        async with self._lock:
            try:
                meta = await self._read_meta(slug)
                if meta is None:
                    return False
                await self._delete_raw(self._meta_key(slug))
                if not await self._refs_for_sha(meta.get("sha256", "")):
                    await self._drop_blob(meta.get("sha256", ""))
            finally:
                self._invalidate()
        return True

    async def clear(self) -> int:
        """Delete every sticker and blob in this scope, returning sticker count."""

        async with self._lock:
            try:
                keys = await self._keys()
                stickers = len(
                    [key for key in keys if self._slug_from_key(key) is not None]
                )
                for key in keys:
                    await self._delete_raw(key)
            finally:
                self._invalidate()
        return stickers

    async def _drop_blob(self, sha256: str) -> None:
        if not sha256:
            return
        blob_key = self._blob_key(sha256)
        if await self._read_raw(blob_key) is not None:
            await self._delete_raw(blob_key)

    async def _evict_over_limit(self) -> int:
        """Drop the oldest stickers once the count exceeds ``max_stickers``."""

        snapshot = await self._scan(force=True)
        if len(snapshot.metas) <= self._max_stickers:
            return 0
        ordered = sorted(
            snapshot.metas,
            key=lambda item: (item.get("created_at", 0), item.get("slug", "")),
        )
        excess = len(ordered) - self._max_stickers
        for meta in ordered[: max(0, excess)]:
            await self._delete_raw(self._meta_key(meta.get("slug", "")))
            # The snapshot still lists the rows being evicted, so count the
            # references that survive in it instead of re-scanning per sticker.
            if not self._refs_in(snapshot, meta.get("sha256", "")):
                await self._drop_blob(meta.get("sha256", ""))
        self._invalidate()
        return excess

    @staticmethod
    def _refs_in(snapshot: _Snapshot, sha256: str) -> list[str]:
        if not sha256:
            return []
        return [
            meta.get("slug", "")
            for meta in snapshot.metas
            if meta.get("sha256") == sha256
        ]

    async def _refs_for_sha(self, sha256: str) -> list[str]:
        if not sha256:
            return []
        snapshot = await self._scan(force=True)
        return self._refs_in(snapshot, sha256)
