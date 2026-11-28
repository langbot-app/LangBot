"""Versioned action and observation evidence for regression tooling."""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.regression.service_logs import records as parse_service_log_records

SCHEMA_VERSION = '1'
ACTION_STATUSES = frozenset({'running', 'succeeded', 'failed', 'timed_out', 'cancelled', 'blocked', 'expired'})
TIMING_KINDS = frozenset({'agent_runner_timing', 'box_execute_timing', 'box_selection_timing'})
CORRELATION_LEVELS = frozenset(
    {
        'trace_id',
        'run_id',
        'secondary_query_id',
        'secondary_session_id',
        'secondary_workspace_uuid',
        'uncorrelated',
    }
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def _artifact_ref(artifact: Path, base_dir: Path) -> str:
    return str(artifact.relative_to(base_dir)) if artifact.is_relative_to(base_dir) else str(artifact)


def _normalize_service_logs(
    service_logs: Mapping[str, Path] | Iterable[Path | tuple[Path, str]] | None,
) -> list[tuple[Path, str]]:
    if service_logs is None:
        return []
    if isinstance(service_logs, Mapping):
        return [(Path(log_path), str(service)) for service, log_path in service_logs.items()]
    normalized: list[tuple[Path, str]] = []
    for item in service_logs:
        if isinstance(item, tuple):
            log_path, service = item
            normalized.append((Path(log_path), str(service)))
        else:
            path = Path(item)
            normalized.append((path, path.stem))
    return normalized


def _parse_timing_message(msg: str) -> tuple[str, dict[str, Any]] | None:
    tokens = msg.strip().split()
    if not tokens or tokens[0] not in TIMING_KINDS:
        return None
    kind = tokens[0]
    fields: dict[str, Any] = {}
    for token in tokens[1:]:
        key, sep, raw = token.partition('=')
        if not sep or not key:
            continue
        if raw in ('True', 'False'):
            fields[key] = raw == 'True'
        elif key.endswith('_ms'):
            try:
                value = float(raw)
            except ValueError:
                fields[key] = raw
            else:
                fields[key] = value if math.isfinite(value) else raw
        else:
            fields[key] = raw
    return kind, fields


@dataclass
class ActionResult:
    action_id: str
    action_name: str
    status: str
    started_at: str
    started_monotonic_ns: int
    trace_id: str | None = None
    finished_at: str | None = None
    finished_monotonic_ns: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    phase_ms: dict[str, float] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def finish(self, status: str, *, error: BaseException | None = None) -> dict[str, Any]:
        if status not in ACTION_STATUSES:
            raise ValueError(f'unknown action status: {status}')
        if self.finished_at is not None:
            raise ValueError(f'action already finished: {self.action_id}')
        self.status = status
        self.finished_at = _now()
        self.finished_monotonic_ns = time.monotonic_ns()
        if error is not None:
            self.error_type = type(error).__name__
            self.error_message = str(error)
        return asdict(self)


class ActionWriter:
    """Append action lifecycle records without changing the action itself."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._active: dict[str, ActionResult] = {}
        self.sources: set[str] = set()

    def begin(
        self, action_name: str, *, trace_id: str | None = None, metadata: dict[str, Any] | None = None
    ) -> ActionResult:
        trace_id = trace_id or f'Y-{uuid.uuid4().hex[:16]}'
        result = ActionResult(
            action_id=f'a-{uuid.uuid4().hex}',
            action_name=action_name,
            status='running',
            started_at=_now(),
            started_monotonic_ns=time.monotonic_ns(),
            trace_id=trace_id,
            metadata=dict(metadata or {}),
        )
        self._active[result.action_id] = result
        return result

    def finish(self, result: ActionResult, status: str, *, error: BaseException | None = None) -> dict[str, Any]:
        if self._active.pop(result.action_id, None) is None:
            raise ValueError(f'unknown action: {result.action_id}')
        record = result.finish(status, error=error)
        self.sources.add(result.action_name)
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(_dump(record) + '\n')
        return record

    def close(self) -> None:
        if self._active:
            raise RuntimeError(f'unfinished actions: {len(self._active)}')


@dataclass
class ObservationSample:
    observation_id: str
    source: str
    wall_time: str
    monotonic_ns: int
    sequence: int
    values: dict[str, Any]
    trace_id: str | None = None
    missing_reasons: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


class ObservationWriter:
    """Append versioned samples and preserve explicit missingness."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sequence = 0
        self.sources: set[str] = set()

    def write(
        self,
        source: str,
        values: dict[str, Any],
        *,
        trace_id: str | None = None,
        missing_reasons: list[str] | None = None,
    ) -> dict[str, Any]:
        self.sequence += 1
        self.sources.add(source)
        record = asdict(
            ObservationSample(
                observation_id=f'o-{uuid.uuid4().hex}',
                source=source,
                wall_time=_now(),
                monotonic_ns=time.monotonic_ns(),
                sequence=self.sequence,
                values=values,
                trace_id=trace_id,
                missing_reasons=list(missing_reasons or []),
            )
        )
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(_dump(record) + '\n')
        return record


def write_manifest(
    path: Path,
    *,
    run_id: str,
    expected_sources: list[str],
    observed_sources: set[str] | list[str] | None = None,
    artifacts: list[Path],
    trace_index: Path | None = None,
    service_logs: Mapping[str, Path] | Iterable[Path | tuple[Path, str]] | None = None,
) -> dict[str, Any]:
    rows, missing = [], []
    all_artifacts: list[Path] = []
    seen_artifacts: set[Path] = set()
    for artifact in [*artifacts, *(log_path for log_path, _ in _normalize_service_logs(service_logs))]:
        resolved = Path(artifact)
        if resolved not in seen_artifacts:
            seen_artifacts.add(resolved)
            all_artifacts.append(resolved)
    for artifact in all_artifacts:
        if not artifact.exists():
            missing.append(str(artifact))
            continue
        digest = hashlib.sha256()
        with artifact.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        rows.append({'path': str(artifact), 'bytes': artifact.stat().st_size, 'sha256': digest.hexdigest()})
    index = (
        json.loads(trace_index.read_text(encoding='utf-8')) if trace_index is not None and trace_index.exists() else {}
    )
    observed_set = set(observed_sources or ())
    observed_set.update(index.get('service_log_sources', ()))
    observed = sorted(observed_set)
    missing_sources = sorted(set(expected_sources) - set(observed))
    manifest = {
        'schema_version': SCHEMA_VERSION,
        'run_id': run_id,
        'created_at': _now(),
        'expected_sources': sorted(expected_sources),
        'observed_sources': observed,
        'missing_sources': missing_sources,
        'artifacts': rows,
        'missing_artifacts': missing,
        'completeness': 'complete' if not missing and not missing_sources else 'incomplete',
    }
    if trace_index is not None:
        secondary = index.get('secondary_indexes', {})
        manifest['trace_index'] = {
            'path': str(trace_index),
            'traces': index.get('traces', 0),
            'indexed_records': index.get('indexed_records', 0),
            'unindexed_records': index.get('unindexed_records', 0),
            'missing_artifacts': index.get('missing_artifacts', []),
            'service_logs': len(index.get('service_logs', [])),
            'timing_counts': index.get('timing_counts', {}),
            'secondary_index_counts': {
                'by_query_id': len(secondary.get('by_query_id', {})),
                'by_session_id': len(secondary.get('by_session_id', {})),
                'by_workspace_uuid': len(secondary.get('by_workspace_uuid', {})),
                'by_run_id': len(secondary.get('by_run_id', {})),
                'uncorrelated_timings': len(secondary.get('uncorrelated_timings', [])),
            },
        }
        if manifest['trace_index']['missing_artifacts']:
            manifest['completeness'] = 'incomplete'
    path.write_text(_dump(manifest) + '\n', encoding='utf-8')
    return manifest


def write_trace_index(
    path: Path,
    artifacts: list[Path],
    *,
    run_id: str | None = None,
    service_logs: Mapping[str, Path] | Iterable[Path | tuple[Path, str]] | None = None,
) -> dict[str, Any]:
    """Index trace-bearing JSONL and service-log timing evidence without fabricating links."""

    # shortcut: build the index at run close, upgrade to streaming for very large evidence sets.
    entries: dict[str, dict[str, Any]] = {}
    unindexed_by_artifact: dict[str, int] = {}
    missing_artifacts: list[str] = []
    indexed_records = 0
    for artifact in artifacts:
        if not artifact.exists():
            missing_artifacts.append(str(artifact))
            continue
        with artifact.open(encoding='utf-8') as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f'invalid JSONL in {artifact}:{line_number}: {exc.msg}') from exc
                if not isinstance(record, dict):
                    raise ValueError(f'JSONL record in {artifact}:{line_number} must be an object')
                trace_id = record.get('trace_id')
                if not isinstance(trace_id, str) or not trace_id:
                    key = str(artifact)
                    unindexed_by_artifact[key] = unindexed_by_artifact.get(key, 0) + 1
                    continue
                entry = entries.setdefault(
                    trace_id,
                    {
                        'trace_id': trace_id,
                        'action_ids': [],
                        'observation_ids': [],
                        'run_ids': [],
                        'evidence': [],
                        'timings': [],
                    },
                )
                for field, target in (
                    ('action_id', 'action_ids'),
                    ('observation_id', 'observation_ids'),
                    ('run_id', 'run_ids'),
                ):
                    value = record.get(field)
                    if isinstance(value, str) and value and value not in entry[target]:
                        entry[target].append(value)
                artifact_ref = _artifact_ref(artifact, path.parent)
                entry['evidence'].append(
                    {
                        'artifact': artifact_ref,
                        'line': line_number,
                    }
                )
                indexed_records += 1

    run_id_to_traces: dict[str, list[str]] = {}
    for trace_id, entry in entries.items():
        for linked_run_id in entry['run_ids']:
            run_id_to_traces.setdefault(linked_run_id, []).append(trace_id)

    service_log_summaries: list[dict[str, Any]] = []
    service_log_sources: set[str] = set()
    timing_counts = {kind: 0 for kind in sorted(TIMING_KINDS)}
    secondary_indexes: dict[str, Any] = {
        'by_query_id': {},
        'by_session_id': {},
        'by_workspace_uuid': {},
        'by_run_id': {},
        'uncorrelated_timings': [],
    }
    for log_path, service_name in _normalize_service_logs(service_logs):
        if not log_path.exists():
            missing_artifacts.append(str(log_path))
            continue
        artifact_ref = _artifact_ref(log_path, path.parent)
        file_timing_counts = {kind: 0 for kind in sorted(TIMING_KINDS)}
        record_count = 0
        error_count = 0
        warn_count = 0
        service_log_sources.add(f'service_log:{service_name}')
        with log_path.open(encoding='utf-8', errors='replace') as stream:
            for log_record in parse_service_log_records(stream, service_name):
                record_count += 1
                if log_record.level in ('ERROR', 'FATAL'):
                    error_count += 1
                elif log_record.level == 'WARN':
                    warn_count += 1
                parsed_timing = _parse_timing_message(log_record.msg)
                if parsed_timing is not None:
                    kind, fields = parsed_timing
                    timing_counts[kind] += 1
                    file_timing_counts[kind] += 1
                    service_log_sources.add(kind)
                    timing_item: dict[str, Any] = {
                        'kind': kind,
                        'service': log_record.service,
                        'artifact': artifact_ref,
                        'line': log_record.log_line,
                        'ts': log_record.ts,
                        'fields': fields,
                    }
                    if kind == 'agent_runner_timing':
                        timing_run_id = fields.get('run_id')
                        matched_traces = (
                            run_id_to_traces.get(timing_run_id, [])
                            if isinstance(timing_run_id, str) and timing_run_id
                            else []
                        )
                        if len(matched_traces) == 1:
                            trace_id = matched_traces[0]
                            timing_item['correlation_level'] = 'run_id'
                            timing_item['deterministic_trace_binding'] = True
                            entries[trace_id]['timings'].append(timing_item)
                            entries[trace_id]['evidence'].append(
                                {
                                    'artifact': artifact_ref,
                                    'line': log_record.log_line,
                                    'kind': kind,
                                    'service': log_record.service,
                                    'correlation_level': 'run_id',
                                    'run_id': timing_run_id,
                                }
                            )
                            indexed_records += 1
                        else:
                            timing_item['correlation_level'] = 'uncorrelated'
                            timing_item['deterministic_trace_binding'] = False
                            timing_item['uncorrelated_reason'] = (
                                'ambiguous_run_id' if len(matched_traces) > 1 else 'run_id_not_in_traces'
                            )
                            if isinstance(timing_run_id, str) and timing_run_id:
                                secondary_indexes['by_run_id'].setdefault(timing_run_id, []).append(timing_item)
                            else:
                                secondary_indexes['uncorrelated_timings'].append(timing_item)
                    else:
                        query_id = fields.get('query_id')
                        session_id = fields.get('session_id')
                        workspace_uuid = fields.get('workspace_uuid')
                        linked_secondary = False
                        if isinstance(query_id, str) and query_id:
                            secondary_item = {
                                **timing_item,
                                'correlation_level': 'secondary_query_id',
                                'deterministic_trace_binding': False,
                            }
                            secondary_indexes['by_query_id'].setdefault(query_id, []).append(secondary_item)
                            linked_secondary = True
                        if isinstance(session_id, str) and session_id:
                            secondary_item = {
                                **timing_item,
                                'correlation_level': 'secondary_session_id',
                                'deterministic_trace_binding': False,
                            }
                            secondary_indexes['by_session_id'].setdefault(session_id, []).append(secondary_item)
                            linked_secondary = True
                        if not linked_secondary and isinstance(workspace_uuid, str) and workspace_uuid:
                            secondary_item = {
                                **timing_item,
                                'correlation_level': 'secondary_workspace_uuid',
                                'deterministic_trace_binding': False,
                            }
                            secondary_indexes['by_workspace_uuid'].setdefault(workspace_uuid, []).append(secondary_item)
                            linked_secondary = True
                        if not linked_secondary:
                            secondary_indexes['uncorrelated_timings'].append(
                                {
                                    **timing_item,
                                    'correlation_level': 'uncorrelated',
                                    'deterministic_trace_binding': False,
                                }
                            )
                elif log_record.trace and log_record.trace in entries:
                    entries[log_record.trace]['evidence'].append(
                        {
                            'artifact': artifact_ref,
                            'line': log_record.log_line,
                            'kind': 'service_log',
                            'service': log_record.service,
                            'correlation_level': 'trace_id',
                        }
                    )
                    indexed_records += 1
        service_log_summaries.append(
            {
                'artifact': artifact_ref,
                'service': service_name,
                'records': record_count,
                'error_records': error_count,
                'warn_records': warn_count,
                'timing_counts': file_timing_counts,
            }
        )
    index = {
        'schema_version': SCHEMA_VERSION,
        'run_id': run_id,
        'created_at': _now(),
        'traces': len(entries),
        'indexed_records': indexed_records,
        'unindexed_records': sum(unindexed_by_artifact.values()),
        'unindexed_by_artifact': unindexed_by_artifact,
        'missing_artifacts': missing_artifacts,
        'service_logs': service_log_summaries,
        'service_log_sources': sorted(service_log_sources),
        'timing_counts': timing_counts,
        'secondary_indexes': secondary_indexes,
        'entries': [entries[key] for key in sorted(entries)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump(index) + '\n', encoding='utf-8')
    return index
