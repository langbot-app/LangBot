from __future__ import annotations

from collections import Counter, deque
from datetime import datetime, timezone
from threading import RLock
from typing import Any


_UNKNOWN = "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_text(value: Any, *, default: str = "", limit: int = 240) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    if len(text) > limit:
        return text[: limit - 1] + "..."
    return text


def _safe_filename(value: Any) -> str:
    filename = _safe_text(value, default=_UNKNOWN, limit=180)
    return filename.replace("\\", "/").rsplit("/", 1)[-1] or _UNKNOWN


def _safe_extension(value: Any) -> str:
    return _safe_text(value, default=_UNKNOWN, limit=40).lower()


def _safe_mime_type(value: Any) -> str:
    return _safe_text(value, default=_UNKNOWN, limit=120).split(";", 1)[0].strip().lower() or _UNKNOWN


def _safe_source(value: Any) -> str:
    return _safe_text(value, default=_UNKNOWN, limit=40).lower()


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _top_items(counter: Counter[str], total: int, limit: int = 12) -> list[dict[str, Any]]:
    rows = []
    for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]:
        rows.append({
            "key": key,
            "count": count,
            "percent": round((count / total) * 100, 1) if total else 0.0,
        })
    return rows


class ParserTelemetry:
    """In-memory parser telemetry with bounded event retention.

    The telemetry store intentionally records only operational metadata. It does
    not accept or persist file bytes or extracted text.
    """

    def __init__(self, recent_limit: int = 80) -> None:
        self.recent_limit = max(1, int(recent_limit))
        self._lock = RLock()
        self.clear()

    def clear(self) -> None:
        with self._lock:
            now = _utc_now()
            self._started_at = now
            self._updated_at = now
            self._next_event_id = 0
            self._totals: dict[str, int | float] = {
                "total_parses": 0,
                "successful_parses": 0,
                "failed_parses": 0,
                "parser_failures": 0,
                "parse_errors": 0,
                "total_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "total_text_chars": 0,
                "total_sections": 0,
                "tables_detected": 0,
                "images_detected": 0,
                "total_images_count": 0,
                "vision_used": 0,
                "vision_tasks_count": 0,
                "vision_images_described_count": 0,
                "vision_scanned_pages_count": 0,
                "vision_failed_count": 0,
            }
            self._extensions: Counter[str] = Counter()
            self._mime_types: Counter[str] = Counter()
            self._extension_sources: Counter[str] = Counter()
            self._recent_parses: deque[dict[str, Any]] = deque(maxlen=self.recent_limit)
            self._recent_errors: deque[dict[str, Any]] = deque(maxlen=self.recent_limit)

    def record_parse(
        self,
        *,
        filename: Any,
        mime_type: Any,
        extension: Any,
        extension_source: Any,
        duration_ms: float,
        text_chars: int,
        sections_count: int,
        metadata: dict[str, Any] | None = None,
        failed: bool = False,
        parse_error: Any = None,
    ) -> None:
        metadata = metadata or {}
        metadata_error = metadata.get("parse_error")
        error_text = _safe_text(parse_error if parse_error is not None else metadata_error, limit=500)
        parser_failed = bool(failed or _as_bool(metadata.get("parser_failed")) or error_text)

        extension_key = _safe_extension(extension or metadata.get("extension"))
        mime_type_key = _safe_mime_type(mime_type or metadata.get("mime_type"))
        extension_source_key = _safe_source(extension_source or metadata.get("extension_source"))
        duration = max(0.0, _as_float(duration_ms))
        text_char_count = max(0, _as_int(text_chars))
        section_count = max(0, _as_int(sections_count))
        raw_images = metadata.get("images")
        inferred_images_count = len(raw_images) if isinstance(raw_images, list) else 0
        images_count = max(0, _as_int(metadata.get("images_count"), inferred_images_count))
        has_images = _as_bool(metadata.get("has_images")) or images_count > 0
        has_tables = _as_bool(metadata.get("has_tables"))
        vision_tasks_count = max(0, _as_int(metadata.get("vision_tasks_count")))
        vision_images_described_count = max(0, _as_int(metadata.get("vision_images_described_count")))
        vision_scanned_pages_count = max(0, _as_int(metadata.get("vision_scanned_pages_count")))
        vision_failed_count = max(0, _as_int(metadata.get("vision_failed_count")))
        vision_used = _as_bool(metadata.get("vision_used")) or (
            vision_images_described_count + vision_scanned_pages_count
        ) > 0

        with self._lock:
            self._next_event_id += 1
            event = {
                "id": self._next_event_id,
                "timestamp": _utc_now(),
                "filename": _safe_filename(filename),
                "mime_type": mime_type_key,
                "extension": extension_key,
                "extension_source": extension_source_key,
                "duration_ms": round(duration, 2),
                "text_chars": text_char_count,
                "sections_count": section_count,
                "parser_failed": parser_failed,
                "parse_error": error_text,
                "has_tables": has_tables,
                "has_images": has_images,
                "images_count": images_count,
                "vision_used": vision_used,
                "vision_tasks_count": vision_tasks_count,
                "vision_images_described_count": vision_images_described_count,
                "vision_scanned_pages_count": vision_scanned_pages_count,
                "vision_failed_count": vision_failed_count,
            }

            totals = self._totals
            totals["total_parses"] += 1
            totals["total_duration_ms"] += duration
            totals["max_duration_ms"] = max(float(totals["max_duration_ms"]), duration)
            totals["total_text_chars"] += text_char_count
            totals["total_sections"] += section_count
            totals["successful_parses" if not parser_failed else "failed_parses"] += 1
            if parser_failed:
                totals["parser_failures"] += 1
            if error_text:
                totals["parse_errors"] += 1
            if has_tables:
                totals["tables_detected"] += 1
            if has_images:
                totals["images_detected"] += 1
            totals["total_images_count"] += images_count
            if vision_used:
                totals["vision_used"] += 1
            totals["vision_tasks_count"] += vision_tasks_count
            totals["vision_images_described_count"] += vision_images_described_count
            totals["vision_scanned_pages_count"] += vision_scanned_pages_count
            totals["vision_failed_count"] += vision_failed_count

            self._extensions[extension_key] += 1
            self._mime_types[mime_type_key] += 1
            self._extension_sources[extension_source_key] += 1
            self._recent_parses.append(event)
            if parser_failed or error_text:
                self._recent_errors.append(event)
            self._updated_at = event["timestamp"]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            totals = dict(self._totals)
            total_parses = int(totals["total_parses"])
            failed_parses = int(totals["failed_parses"])
            summary = {
                "started_at": self._started_at,
                "updated_at": self._updated_at,
                "recent_limit": self.recent_limit,
                "total_parses": total_parses,
                "successful_parses": int(totals["successful_parses"]),
                "failed_parses": failed_parses,
                "failure_rate": round((failed_parses / total_parses) * 100, 1) if total_parses else 0.0,
                "avg_duration_ms": round(float(totals["total_duration_ms"]) / total_parses, 2)
                if total_parses
                else 0.0,
                "max_duration_ms": round(float(totals["max_duration_ms"]), 2),
                "avg_text_chars": round(int(totals["total_text_chars"]) / total_parses, 1)
                if total_parses
                else 0.0,
                "avg_sections": round(int(totals["total_sections"]) / total_parses, 1)
                if total_parses
                else 0.0,
                "total_text_chars": int(totals["total_text_chars"]),
                "total_sections": int(totals["total_sections"]),
                "tables_detected": int(totals["tables_detected"]),
                "images_detected": int(totals["images_detected"]),
                "vision_used": int(totals["vision_used"]),
                "vision_tasks_count": int(totals["vision_tasks_count"]),
                "vision_failed_count": int(totals["vision_failed_count"]),
            }
            return {
                "summary": summary,
                "counters": totals,
                "distributions": {
                    "extensions": _top_items(self._extensions, total_parses),
                    "mime_types": _top_items(self._mime_types, total_parses),
                    "extension_sources": _top_items(self._extension_sources, total_parses),
                },
                "recent_parses": list(reversed(self._recent_parses)),
                "recent_errors": list(reversed(self._recent_errors)),
            }


def binding_scope(binding: Any) -> tuple[str, str, str] | None:
    """Return the full installation scope for ``binding``, or ``None``.

    The scope is the triple ``(instance_uuid, workspace_uuid,
    installation_uuid)``. ``runtime_revision`` is deliberately excluded so a
    worker upgrade keeps the same telemetry bucket. The binding object itself is
    never stored; only this derived key is.
    """

    if binding is None:
        return None
    instance = _safe_text(getattr(binding, "instance_uuid", None), default="", limit=200)
    workspace = _safe_text(getattr(binding, "workspace_uuid", None), default="", limit=200)
    installation = _safe_text(getattr(binding, "installation_uuid", None), default="", limit=200)
    if not (instance and workspace and installation):
        return None
    return (instance, workspace, installation)


class TelemetryRegistry:
    """Binding-keyed telemetry stores for one artifact-digest worker.

    One object graph serves every installation, so the process-wide registry
    keeps one ``ParserTelemetry`` per full installation binding and a separate
    "unscoped" store for direct (non-invocation) use. Binding state is released
    by :meth:`release` from ``BasePlugin.on_installation_revoked``.
    """

    def __init__(self, recent_limit: int = 80) -> None:
        self.recent_limit = max(1, int(recent_limit))
        self._lock = RLock()
        self._stores: dict[tuple[str, str, str], ParserTelemetry] = {}
        self._unscoped = ParserTelemetry(recent_limit=self.recent_limit)

    def for_binding(self, binding: Any) -> ParserTelemetry:
        key = binding_scope(binding)
        if key is None:
            return self._unscoped
        with self._lock:
            store = self._stores.get(key)
            if store is None:
                store = ParserTelemetry(recent_limit=self.recent_limit)
                self._stores[key] = store
            return store

    def release(self, binding: Any) -> None:
        key = binding_scope(binding)
        if key is None:
            return
        with self._lock:
            self._stores.pop(key, None)

    def scopes(self) -> list[tuple[str, str, str]]:
        with self._lock:
            return list(self._stores)


_REGISTRY = TelemetryRegistry()


def get_telemetry(binding: Any = None) -> ParserTelemetry:
    """Return the telemetry store for the current installation binding."""

    return _REGISTRY.for_binding(binding)


def release_telemetry(binding: Any) -> None:
    """Drop process-local telemetry held for one revoked installation."""

    _REGISTRY.release(binding)
