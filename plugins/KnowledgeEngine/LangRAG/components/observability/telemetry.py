from __future__ import annotations

import copy
import hashlib
import json
import os
import socket
import threading
import time
import uuid
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RECENT_LIMIT = 100
DEFAULT_HISTORY_LIMIT = 5000
WINDOWS_SECONDS = (60, 300, 3600)
FAILED_STATUSES = {"failed", "error"}


def _now_iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or time.time(), timezone.utc).isoformat(
        timespec="seconds"
    )


def _parse_iso(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _duration_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def _instance_id() -> str:
    configured = os.getenv("LANGRAG_INSTANCE_ID")
    if configured:
        return configured
    raw = f"{socket.gethostname()}:{os.getpid()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def hash_text(value: Any) -> str | None:
    """Return a short stable hash for sensitive text-like values."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.encode("utf-8", errors="replace")
    elif not isinstance(value, bytes):
        value = str(value).encode("utf-8", errors="replace")
    return hashlib.sha256(value).hexdigest()[:16]


def _status_value(status: Any) -> str:
    value = getattr(status, "value", status)
    if value is None:
        return "unknown"
    return str(value)


def _safe_len(value: Any) -> int | None:
    try:
        return len(value)
    except Exception:
        return None


def _trim_error(error: Any, limit: int = 300) -> str | None:
    if error is None:
        return None
    text = str(error)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def _safe_copy(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _safe_copy(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_copy(v) for v in value]
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return enum_value
    return str(value)


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)


def _latency_stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0}
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 2),
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "p99": _percentile(values, 0.99),
        "max": round(max(values), 2),
    }


def _compact_settings(settings: dict[str, Any] | None, keys: tuple[str, ...]) -> dict:
    """Keep only non-sensitive operational settings."""
    source = settings or {}
    summary: dict[str, Any] = {}
    for key in keys:
        if key in source:
            summary[key] = _safe_copy(source[key])

    uuid_fields = [key for key in source if key.endswith("_uuid") and source.get(key)]
    if uuid_fields:
        summary["configured_model_fields"] = sorted(uuid_fields)
    return summary


def _collection_summary(collection_id: str | None) -> dict:
    if not collection_id:
        return {}
    return {
        "collection_id": collection_id,
        "collection_id_hash": hash_text(collection_id),
    }


def _sample_hashes(values: list[str] | tuple[str, ...] | None, limit: int = 5) -> list[str]:
    if not values:
        return []
    return [hash_text(str(value)) or "" for value in list(values)[:limit]]


def add_stage_duration(target: dict[str, float], stage: str, duration_ms: float) -> None:
    """Accumulate a stage duration in milliseconds."""
    if not stage:
        return
    current = float(target.get(stage, 0.0) or 0.0)
    target[stage] = round(current + float(duration_ms or 0.0), 2)


class LangRAGTelemetry:
    """Operational telemetry store for the LangRAG plugin.

    The store records compact operational metadata, keeps an in-memory ring
    buffer for the Page UI, and can append privacy-conscious events to JSONL so
    diagnostics survive plugin restarts. It intentionally avoids storing full
    user queries or document text.
    """

    def __init__(
        self,
        max_events: int = DEFAULT_RECENT_LIMIT,
        max_history_events: int = DEFAULT_HISTORY_LIMIT,
        persist_path: str | Path | None = None,
    ) -> None:
        self.max_events = max_events
        self.max_history_events = max_history_events
        self.persist_path = Path(persist_path) if persist_path else None
        self.instance_id = _instance_id()
        self._lock = threading.RLock()
        self._started_at = time.time()
        self._started_at_iso = _now_iso()
        self._counters: Counter[str] = Counter()
        self._events: deque[dict] = deque(maxlen=max_history_events)
        self._recent_ingest: deque[dict] = deque(maxlen=max_events)
        self._recent_retrieval: deque[dict] = deque(maxlen=max_events)
        self._recent_delete: deque[dict] = deque(maxlen=max_events)
        self._recent_embedding: deque[dict] = deque(maxlen=max_events)
        self._recent_errors: deque[dict] = deque(maxlen=max_events)
        self._persistence_error: str | None = None
        self._loaded_event_count = 0
        self._load_persisted_events()

    @staticmethod
    def start_timer() -> float:
        return time.perf_counter()

    @staticmethod
    def elapsed_ms(started_at: float) -> float:
        return _duration_ms(started_at)

    @staticmethod
    def new_trace_id(prefix: str = "rag") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def ingest_settings(settings: dict[str, Any] | None) -> dict:
        return _compact_settings(
            settings,
            (
                "index_type",
                "chunk_size",
                "overlap",
                "parent_chunk_size",
                "child_chunk_size",
                "questions_per_chunk",
            ),
        )

    @staticmethod
    def retrieval_settings(settings: dict[str, Any] | None) -> dict:
        return _compact_settings(
            settings,
            (
                "top_k",
                "search_type",
                "vector_weight",
                "query_rewrite",
                "rerank",
                "context_window",
            ),
        )

    @staticmethod
    def correlation_summary(*sources: Any, trace_id: str | None = None) -> dict:
        summary: dict[str, Any] = {}
        if trace_id:
            summary["trace_id"] = trace_id
        keys = ("request_id", "bot_id", "session_id", "conversation_id", "user_id")
        for source in sources:
            if not isinstance(source, dict):
                continue
            for key in keys:
                value = source.get(key)
                if value and f"{key}_hash" not in summary:
                    summary[f"{key}_hash"] = hash_text(value)
        return summary

    def clear(self) -> None:
        with self._lock:
            self._started_at = time.time()
            self._started_at_iso = _now_iso()
            self._counters = Counter()
            self._events.clear()
            self._recent_ingest.clear()
            self._recent_retrieval.clear()
            self._recent_delete.clear()
            self._recent_embedding.clear()
            self._recent_errors.clear()
            self._loaded_event_count = 0
            self._truncate_persisted_events()

    def record_ingest(
        self,
        *,
        document_id: str | None,
        filename: str | None,
        collection_id: str | None,
        status: Any,
        duration_ms: float,
        index_type: str | None = None,
        chunks_created: int | None = None,
        file_size: int | None = None,
        text_length: int | None = None,
        content_hash: str | None = None,
        sections_count: int | None = None,
        settings: dict[str, Any] | None = None,
        stage_durations_ms: dict[str, float] | None = None,
        parser_source: str | None = None,
        knowledge_base_id: str | None = None,
        trace_id: str | None = None,
        correlation: dict[str, Any] | None = None,
        error: Any = None,
    ) -> None:
        try:
            status_text = _status_value(status)
            event = {
                "recorded_at": _now_iso(),
                "recorded_at_unix": time.time(),
                "operation": "ingest",
                "status": status_text,
                "duration_ms": duration_ms,
                "trace_id": trace_id or self.new_trace_id("ingest"),
                "document_id": document_id,
                "document_id_hash": hash_text(document_id),
                "filename": filename,
                "filename_hash": hash_text(filename),
                "knowledge_base_id_hash": hash_text(knowledge_base_id),
                **_collection_summary(collection_id),
                "index_type": index_type,
                "parser_source": parser_source,
                "chunks_created": chunks_created,
                "file_size": file_size,
                "text_length": text_length,
                "content_hash": content_hash,
                "sections_count": sections_count,
                "settings": self.ingest_settings(settings),
                "stage_durations_ms": _safe_copy(stage_durations_ms or {}),
                "correlation": _safe_copy(correlation or {}),
                "error": _trim_error(error),
            }
            self._record_event(event)
        except Exception:
            return

    def record_retrieval(
        self,
        *,
        query: str | None,
        collection_id: str | None,
        status: Any,
        duration_ms: float,
        index_type: str | None = None,
        search_type: Any = None,
        top_k: int | None = None,
        fetch_k: int | None = None,
        raw_count: int | None = None,
        result_count: int | None = None,
        reference_count: int | None = None,
        heading_count: int | None = None,
        context_expanded_count: int | None = None,
        distance_min: float | None = None,
        distance_avg: float | None = None,
        distance_max: float | None = None,
        filters: Any = None,
        creation_settings: dict[str, Any] | None = None,
        retrieval_settings: dict[str, Any] | None = None,
        stage_durations_ms: dict[str, float] | None = None,
        trace_spans: list[dict[str, Any]] | None = None,
        reranked: bool | None = None,
        knowledge_base_id: str | None = None,
        trace_id: str | None = None,
        correlation: dict[str, Any] | None = None,
        error: Any = None,
    ) -> None:
        try:
            status_text = _status_value(status)
            event = {
                "recorded_at": _now_iso(),
                "recorded_at_unix": time.time(),
                "operation": "retrieval",
                "status": status_text,
                "duration_ms": duration_ms,
                "trace_id": trace_id or self.new_trace_id("retrieval"),
                **_collection_summary(collection_id),
                "knowledge_base_id_hash": hash_text(knowledge_base_id),
                "query_length": _safe_len(query),
                "query_hash": hash_text(query),
                "index_type": index_type,
                "search_type": _status_value(search_type),
                "top_k": top_k,
                "fetch_k": fetch_k,
                "raw_count": raw_count,
                "result_count": result_count,
                "reference_count": reference_count,
                "heading_count": heading_count,
                "context_expanded_count": context_expanded_count,
                "distance_min": distance_min,
                "distance_avg": distance_avg,
                "distance_max": distance_max,
                "filters_summary": self._filters_summary(filters),
                "creation_settings": self.ingest_settings(creation_settings),
                "retrieval_settings": self.retrieval_settings(retrieval_settings),
                "stage_durations_ms": _safe_copy(stage_durations_ms or {}),
                "trace_spans": _safe_copy(trace_spans or []),
                "reranked": reranked,
                "correlation": _safe_copy(correlation or {}),
                "error": _trim_error(error),
            }
            self._record_event(event)
        except Exception:
            return

    def record_delete(
        self,
        *,
        collection_id: str | None,
        document_id: str | None,
        status: Any,
        duration_ms: float,
        deleted: bool | None = None,
        vectors_deleted: int | None = None,
        knowledge_base_id: str | None = None,
        trace_id: str | None = None,
        correlation: dict[str, Any] | None = None,
        error: Any = None,
    ) -> None:
        try:
            status_text = _status_value(status)
            event = {
                "recorded_at": _now_iso(),
                "recorded_at_unix": time.time(),
                "operation": "delete",
                "status": status_text,
                "duration_ms": duration_ms,
                "trace_id": trace_id or self.new_trace_id("delete"),
                "document_id": document_id,
                "document_id_hash": hash_text(document_id),
                "knowledge_base_id_hash": hash_text(knowledge_base_id or collection_id),
                **_collection_summary(collection_id),
                "deleted": deleted,
                "vectors_deleted": vectors_deleted,
                "correlation": _safe_copy(correlation or {}),
                "error": _trim_error(error),
            }
            self._record_event(event)
        except Exception:
            return

    def record_embedding_batch(
        self,
        *,
        collection_id: str | None,
        ids: list[str] | None,
        metas: list[dict] | None,
        texts: list[str] | None,
        status: Any,
        duration_ms: float,
        vectors_stored: int | None = None,
        stage_durations_ms: dict[str, float] | None = None,
        trace_id: str | None = None,
        error: Any = None,
    ) -> None:
        try:
            status_text = _status_value(status)
            text_lengths = [_safe_len(text) for text in (texts or [])]
            document_ids = sorted(
                {
                    str(meta.get("document_id"))
                    for meta in (metas or [])
                    if isinstance(meta, dict) and meta.get("document_id")
                }
            )
            event = {
                "recorded_at": _now_iso(),
                "recorded_at_unix": time.time(),
                "operation": "embedding_batch",
                "status": status_text,
                "duration_ms": duration_ms,
                "trace_id": trace_id or self.new_trace_id("embedding"),
                **_collection_summary(collection_id),
                "vector_count": _safe_len(ids),
                "vectors_stored": vectors_stored,
                "id_hashes": _sample_hashes(ids),
                "document_id_hashes": _sample_hashes(document_ids),
                "total_text_length": sum(x or 0 for x in text_lengths),
                "min_text_length": min(text_lengths) if text_lengths else None,
                "max_text_length": max(text_lengths) if text_lengths else None,
                "stage_durations_ms": _safe_copy(stage_durations_ms or {}),
                "error": _trim_error(error),
            }
            self._record_event(event)
        except Exception:
            return

    def snapshot(self) -> dict:
        with self._lock:
            counters = dict(self._counters)
            events = list(self._events)
            uptime_seconds = max(0, int(time.time() - self._started_at))
            windows = self._windows(events)
            alerts = self._alerts(windows)
            return {
                "generated_at": _now_iso(),
                "started_at": self._started_at_iso,
                "uptime_seconds": uptime_seconds,
                "instance_id": self.instance_id,
                "health": self._health(alerts),
                "alerts": alerts,
                "counters": counters,
                "averages": self._averages(counters),
                "latency": self._latency(events),
                "quality": self._quality(events),
                "windows": windows,
                "recent": {
                    "ingest": list(reversed(copy.deepcopy(self._recent_ingest))),
                    "retrieval": list(reversed(copy.deepcopy(self._recent_retrieval))),
                    "delete": list(reversed(copy.deepcopy(self._recent_delete))),
                    "embedding": list(reversed(copy.deepcopy(self._recent_embedding))),
                    "errors": list(reversed(copy.deepcopy(self._recent_errors))),
                },
                "exporters": {
                    "prometheus_page_api": "/metrics",
                    "json_snapshot_page_api": "/snapshot",
                    "format": "prometheus-text-0.0.4",
                },
                "persistence": {
                    "enabled": self.persist_path is not None,
                    "path": str(self.persist_path) if self.persist_path else None,
                    "loaded_events": self._loaded_event_count,
                    "history_events": len(events),
                    "error": self._persistence_error,
                },
                "limits": {
                    "recent_events": self.max_events,
                    "history_events": self.max_history_events,
                    "windows_seconds": list(WINDOWS_SECONDS),
                },
            }

    def prometheus(self, snapshot: dict | None = None) -> str:
        snapshot = self.snapshot() if snapshot is None else snapshot
        instance = self.instance_id
        lines = [
            "# HELP langrag_info LangRAG observability instance information",
            "# TYPE langrag_info gauge",
            f'langrag_info{{instance="{instance}"}} 1',
            "# HELP langrag_uptime_seconds Seconds since telemetry store start",
            "# TYPE langrag_uptime_seconds gauge",
            f'langrag_uptime_seconds{{instance="{instance}"}} {snapshot["uptime_seconds"]}',
            "# HELP langrag_operation_events_total Operation count by operation",
            "# TYPE langrag_operation_events_total counter",
        ]

        for key, value in sorted(snapshot["counters"].items()):
            parts = key.split(".")
            if len(parts) == 2 and parts[1] == "total":
                lines.append(
                    f'langrag_operation_events_total{{instance="{instance}",'
                    f'operation="{parts[0]}"}} {int(value)}'
                )

        lines.extend(
            [
            "# HELP langrag_operations_total Operation count by operation and status",
            "# TYPE langrag_operations_total counter",
            ]
        )

        for key, value in sorted(snapshot["counters"].items()):
            parts = key.split(".")
            if len(parts) == 2 and parts[1] not in (
                "total",
                "duration_ms_total",
                "chunks_created",
                "results_returned",
                "vectors_deleted",
                "vectors_stored",
                "zero_results",
            ):
                lines.append(
                    f'langrag_operations_total{{instance="{instance}",'
                    f'operation="{parts[0]}",'
                    f'status="{parts[1]}"}} {int(value)}'
                )

        lines.extend(
            [
                "# HELP langrag_operation_duration_ms Operation latency summary",
                "# TYPE langrag_operation_duration_ms gauge",
                "# HELP langrag_stage_duration_ms Operation stage latency summary",
                "# TYPE langrag_stage_duration_ms gauge",
            ]
        )
        for operation, stats in snapshot["latency"].items():
            for metric in ("avg", "p50", "p95", "p99", "max"):
                lines.append(
                    f'langrag_operation_duration_ms{{instance="{instance}",'
                    f'operation="{operation}",'
                    f'quantile="{metric}"}} {stats.get(metric, 0)}'
                )
            for stage, stage_stats in (stats.get("stages_ms") or {}).items():
                for metric in ("avg", "p50", "p95", "p99", "max"):
                    lines.append(
                        f'langrag_stage_duration_ms{{instance="{instance}",'
                        f'operation="{operation}",stage="{stage}",'
                        f'quantile="{metric}"}} {stage_stats.get(metric, 0)}'
                    )

        lines.extend(
            [
                "# HELP langrag_window_error_rate Error rate for recent time windows",
                "# TYPE langrag_window_error_rate gauge",
                "# HELP langrag_window_rate_per_min Operation rate per minute",
                "# TYPE langrag_window_rate_per_min gauge",
            ]
        )
        for window, operations in snapshot["windows"].items():
            for operation, stats in operations.items():
                lines.append(
                    f'langrag_window_error_rate{{instance="{instance}",'
                    f'window="{window}",'
                    f'operation="{operation}"}} {stats.get("error_rate", 0)}'
                )
                lines.append(
                    f'langrag_window_rate_per_min{{instance="{instance}",'
                    f'window="{window}",'
                    f'operation="{operation}"}} {stats.get("rate_per_min", 0)}'
                )

        quality = snapshot["quality"]["retrieval"]
        lines.extend(
            [
                "# HELP langrag_retrieval_zero_result_rate Retrieval zero-result rate",
                "# TYPE langrag_retrieval_zero_result_rate gauge",
                (
                    f'langrag_retrieval_zero_result_rate{{instance="{instance}"}} '
                    f"{quality['zero_result_rate']}"
                ),
                "# HELP langrag_retrieval_topk_fill_rate Average returned/top_k fill rate",
                "# TYPE langrag_retrieval_topk_fill_rate gauge",
                (
                    f'langrag_retrieval_topk_fill_rate{{instance="{instance}"}} '
                    f"{quality['top_k_fill_rate']}"
                ),
                "# HELP langrag_retrieval_reference_coverage_rate Retrieval reference coverage rate",
                "# TYPE langrag_retrieval_reference_coverage_rate gauge",
                (
                    f'langrag_retrieval_reference_coverage_rate{{instance="{instance}"}} '
                    f"{quality['reference_coverage_rate']}"
                ),
                "# HELP langrag_retrieval_rerank_rate Retrieval rerank usage rate",
                "# TYPE langrag_retrieval_rerank_rate gauge",
                (
                    f'langrag_retrieval_rerank_rate{{instance="{instance}"}} '
                    f"{quality['rerank_rate']}"
                ),
                "# HELP langrag_persistence_enabled Whether JSONL persistence is enabled",
                "# TYPE langrag_persistence_enabled gauge",
                (
                    f'langrag_persistence_enabled{{instance="{instance}"}} '
                    f"{1 if snapshot['persistence']['enabled'] else 0}"
                ),
                "# HELP langrag_history_events Number of in-memory history events",
                "# TYPE langrag_history_events gauge",
                (
                    f'langrag_history_events{{instance="{instance}"}} '
                    f"{snapshot['persistence']['history_events']}"
                ),
                "# HELP langrag_alerts_active Active alert count by severity",
                "# TYPE langrag_alerts_active gauge",
            ]
        )
        for severity in ("warning", "critical"):
            count = sum(1 for alert in snapshot["alerts"] if alert["severity"] == severity)
            lines.append(
                f'langrag_alerts_active{{instance="{instance}",'
                f'severity="{severity}"}} {count}'
            )
        return "\n".join(lines) + "\n"

    def _load_persisted_events(self) -> None:
        if not self.persist_path or not self.persist_path.exists():
            return
        try:
            loaded: deque[dict] = deque(maxlen=self.max_history_events)
            with self.persist_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    loaded.append(json.loads(line))
            with self._lock:
                for event in loaded:
                    self._record_event(event, persist=False)
                self._loaded_event_count = len(loaded)
        except Exception as exc:
            self._persistence_error = _trim_error(exc)

    def _truncate_persisted_events(self) -> None:
        if not self.persist_path:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            self.persist_path.write_text("", encoding="utf-8")
            self._persistence_error = None
        except Exception as exc:
            self._persistence_error = _trim_error(exc)

    def _append_persisted_event(self, event: dict) -> None:
        if not self.persist_path:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            with self.persist_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            self._persistence_error = None
        except Exception as exc:
            self._persistence_error = _trim_error(exc)

    def _record_event(self, event: dict, *, persist: bool = True) -> None:
        operation = str(event.get("operation") or "unknown")
        status = str(event.get("status") or "unknown")
        if "recorded_at_unix" not in event:
            event["recorded_at_unix"] = _parse_iso(event.get("recorded_at")) or time.time()
        if "recorded_at" not in event:
            event["recorded_at"] = _now_iso(event["recorded_at_unix"])

        with self._lock:
            self._events.append(event)
            self._counters[f"{operation}.total"] += 1
            self._counters[f"{operation}.{status}"] += 1
            duration = int(round(_safe_float(event.get("duration_ms")) or 0))
            self._counters[f"{operation}.duration_ms_total"] += duration

            if operation == "ingest":
                self._recent_ingest.append(event)
                if event.get("chunks_created"):
                    self._counters["ingest.chunks_created"] += int(
                        event["chunks_created"]
                    )
            elif operation == "retrieval":
                self._recent_retrieval.append(event)
                if event.get("result_count"):
                    self._counters["retrieval.results_returned"] += int(
                        event["result_count"]
                    )
                if event.get("result_count") == 0 and status not in FAILED_STATUSES:
                    self._counters["retrieval.zero_results"] += 1
            elif operation == "delete":
                self._recent_delete.append(event)
                if event.get("deleted"):
                    self._counters["delete.deleted"] += 1
                if event.get("vectors_deleted"):
                    self._counters["delete.vectors_deleted"] += int(
                        event["vectors_deleted"]
                    )
            elif operation == "embedding_batch":
                self._recent_embedding.append(event)
                if event.get("vectors_stored"):
                    self._counters["embedding_batch.vectors_stored"] += int(
                        event["vectors_stored"]
                    )

            for stage, stage_ms in (event.get("stage_durations_ms") or {}).items():
                stage_value = int(round(_safe_float(stage_ms) or 0))
                self._counters[f"{operation}.stage.{stage}.duration_ms_total"] += (
                    stage_value
                )

            if event.get("error") or status in FAILED_STATUSES:
                self._append_error_locked(event)

        if persist:
            self._append_persisted_event(event)

    def _append_error_locked(self, event: dict) -> None:
        self._recent_errors.append(
            {
                "recorded_at": event.get("recorded_at"),
                "operation": event.get("operation"),
                "status": event.get("status"),
                "trace_id": event.get("trace_id"),
                "duration_ms": event.get("duration_ms"),
                "document_id": event.get("document_id"),
                "document_id_hash": event.get("document_id_hash"),
                "collection_id": event.get("collection_id"),
                "collection_id_hash": event.get("collection_id_hash"),
                "query_hash": event.get("query_hash"),
                "error": event.get("error") or "operation failed",
            }
        )

    @staticmethod
    def _filters_summary(filters: Any) -> dict:
        if not filters:
            return {"present": False}
        if isinstance(filters, dict):
            return {
                "present": True,
                "keys": sorted(str(key) for key in filters.keys())[:20],
                "count": len(filters),
            }
        return {"present": True, "type": type(filters).__name__}

    @staticmethod
    def _averages(counters: dict[str, int]) -> dict:
        averages: dict[str, float] = {}
        for operation in ("ingest", "retrieval", "delete", "embedding_batch"):
            total = counters.get(f"{operation}.total", 0)
            duration = counters.get(f"{operation}.duration_ms_total", 0)
            averages[f"{operation}.duration_ms"] = (
                round(duration / total, 2) if total else 0
            )
        return averages

    def _latency(self, events: list[dict]) -> dict:
        by_operation: dict[str, list[float]] = {}
        stage_values: dict[str, dict[str, list[float]]] = {}
        for event in events:
            operation = str(event.get("operation") or "unknown")
            duration = _safe_float(event.get("duration_ms"))
            if duration is not None:
                by_operation.setdefault(operation, []).append(duration)
            for stage, value in (event.get("stage_durations_ms") or {}).items():
                stage_duration = _safe_float(value)
                if stage_duration is not None:
                    stage_values.setdefault(operation, {}).setdefault(stage, []).append(
                        stage_duration
                    )

        latency = {op: _latency_stats(values) for op, values in by_operation.items()}
        for operation, stages in stage_values.items():
            latency.setdefault(operation, _latency_stats([]))
            latency[operation]["stages_ms"] = {
                stage: _latency_stats(values) for stage, values in stages.items()
            }
        return latency

    def _windows(self, events: list[dict]) -> dict[str, dict]:
        now = time.time()
        result: dict[str, dict] = {}
        for seconds in WINDOWS_SECONDS:
            window_events = [
                event
                for event in events
                if now - float(event.get("recorded_at_unix") or 0) <= seconds
            ]
            label = self._window_label(seconds)
            result[label] = {}
            for operation in ("ingest", "retrieval", "delete", "embedding_batch"):
                op_events = [
                    event
                    for event in window_events
                    if event.get("operation") == operation
                ]
                result[label][operation] = self._operation_window_stats(
                    op_events, seconds
                )
            result[label]["all"] = self._operation_window_stats(window_events, seconds)
        return result

    def _operation_window_stats(self, events: list[dict], seconds: int) -> dict:
        total = len(events)
        failed = sum(
            1 for event in events if str(event.get("status")) in FAILED_STATUSES
        )
        durations = [
            duration
            for duration in (_safe_float(event.get("duration_ms")) for event in events)
            if duration is not None
        ]
        zero_results = sum(
            1
            for event in events
            if event.get("operation") == "retrieval"
            and event.get("result_count") == 0
            and str(event.get("status")) not in FAILED_STATUSES
        )
        stage_values: dict[str, list[float]] = {}
        for event in events:
            for stage, value in (event.get("stage_durations_ms") or {}).items():
                stage_duration = _safe_float(value)
                if stage_duration is not None:
                    stage_values.setdefault(stage, []).append(stage_duration)

        return {
            "events": total,
            "failed": failed,
            "error_rate": round(failed / total, 4) if total else 0,
            "zero_results": zero_results,
            "zero_result_rate": round(zero_results / total, 4) if total else 0,
            "rate_per_min": round(total * 60 / seconds, 4),
            "duration_ms": _latency_stats(durations),
            "stages_ms": {
                stage: _latency_stats(values)
                for stage, values in sorted(stage_values.items())
            },
        }

    def _quality(self, events: list[dict]) -> dict:
        retrievals = [event for event in events if event.get("operation") == "retrieval"]
        completed = [
            event
            for event in retrievals
            if str(event.get("status")) not in FAILED_STATUSES
        ]
        if not completed:
            return {
                "retrieval": {
                    "evaluated": 0,
                    "zero_results": 0,
                    "zero_result_rate": 0,
                    "avg_result_count": 0,
                    "avg_raw_count": 0,
                    "top_k_fill_rate": 0,
                    "reference_coverage_rate": 0,
                    "rerank_rate": 0,
                    "filtered_rate": 0,
                }
            }

        zero = sum(1 for event in completed if event.get("result_count") == 0)
        result_counts = [
            _safe_float(event.get("result_count")) or 0.0 for event in completed
        ]
        raw_counts = [_safe_float(event.get("raw_count")) or 0.0 for event in completed]
        fill_values = []
        reference_coverage = []
        for event in completed:
            top_k = _safe_float(event.get("top_k"))
            returned = _safe_float(event.get("result_count")) or 0.0
            if top_k and top_k > 0:
                fill_values.append(min(1.0, returned / top_k))
            references = _safe_float(event.get("reference_count")) or 0.0
            if returned > 0:
                reference_coverage.append(min(1.0, references / returned))

        return {
            "retrieval": {
                "evaluated": len(completed),
                "zero_results": zero,
                "zero_result_rate": round(zero / len(completed), 4),
                "avg_result_count": round(sum(result_counts) / len(completed), 2),
                "avg_raw_count": round(sum(raw_counts) / len(completed), 2),
                "top_k_fill_rate": round(sum(fill_values) / len(fill_values), 4)
                if fill_values
                else 0,
                "reference_coverage_rate": round(
                    sum(reference_coverage) / len(reference_coverage), 4
                )
                if reference_coverage
                else 0,
                "rerank_rate": round(
                    sum(1 for event in completed if event.get("reranked"))
                    / len(completed),
                    4,
                ),
                "filtered_rate": round(
                    sum(
                        1
                        for event in completed
                        if (event.get("filters_summary") or {}).get("present")
                    )
                    / len(completed),
                    4,
                ),
            }
        }

    def _alerts(self, windows: dict[str, dict]) -> list[dict]:
        alerts: list[dict] = []
        five_min = windows.get("5m", {})

        if self.persist_path is None:
            alerts.append(
                {
                    "severity": "warning",
                    "code": "persistence_disabled",
                    "message": "Telemetry persistence is disabled.",
                }
            )
        elif self._persistence_error:
            alerts.append(
                {
                    "severity": "warning",
                    "code": "persistence_error",
                    "message": self._persistence_error,
                }
            )

        all_stats = five_min.get("all", {})
        if all_stats.get("events", 0) >= 5:
            if all_stats.get("error_rate", 0) >= 0.2:
                alerts.append(
                    {
                        "severity": "critical",
                        "code": "high_error_rate",
                        "message": "5m operation error rate is at or above 20%.",
                    }
                )
            elif all_stats.get("error_rate", 0) >= 0.05:
                alerts.append(
                    {
                        "severity": "warning",
                        "code": "elevated_error_rate",
                        "message": "5m operation error rate is at or above 5%.",
                    }
                )

        retrieval = five_min.get("retrieval", {})
        if retrieval.get("events", 0) >= 5:
            if retrieval.get("zero_result_rate", 0) >= 0.5:
                alerts.append(
                    {
                        "severity": "critical",
                        "code": "retrieval_zero_results",
                        "message": "At least half of 5m retrievals returned no results.",
                    }
                )
            elif retrieval.get("zero_result_rate", 0) >= 0.2:
                alerts.append(
                    {
                        "severity": "warning",
                        "code": "retrieval_zero_results_elevated",
                        "message": "5m retrieval zero-result rate is at or above 20%.",
                    }
                )

        thresholds = {
            "ingest": 30000,
            "retrieval": 2000,
            "embedding_batch": 15000,
            "delete": 5000,
        }
        for operation, threshold in thresholds.items():
            stats = five_min.get(operation, {})
            duration = stats.get("duration_ms", {})
            if duration.get("count", 0) >= 3 and duration.get("p95", 0) > threshold:
                alerts.append(
                    {
                        "severity": "warning",
                        "code": f"{operation}_p95_latency",
                        "message": (
                            f"{operation} p95 latency is {duration.get('p95')} ms "
                            f"over {threshold} ms."
                        ),
                    }
                )

        return alerts

    @staticmethod
    def _health(alerts: list[dict]) -> str:
        if any(alert.get("severity") == "critical" for alert in alerts):
            return "critical"
        if alerts:
            return "warning"
        return "ok"

    @staticmethod
    def _window_label(seconds: int) -> str:
        return f"{seconds // 60}m" if seconds < 3600 else f"{seconds // 3600}h"


# Compatibility name for stateless timing helpers; runtime state lives on BasePlugin.
telemetry = LangRAGTelemetry
