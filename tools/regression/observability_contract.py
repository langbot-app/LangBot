"""Versioned action and observation evidence for regression tooling."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import threading
import time
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.regression.service_logs import records as parse_service_log_records

SCHEMA_VERSION = '1'
ACTION_STATUSES = frozenset(
    {'running', 'succeeded', 'failed', 'timed_out', 'cancelled', 'blocked', 'expired', 'interrupted'}
)
OBSERVATION_SCOPES = frozenset({'request', 'global'})
TIMING_KINDS = frozenset({'agent_runner_timing', 'box_execute_timing', 'box_selection_timing'})
REQUIRED_TIMING_MS_KEYS: dict[str, tuple[str, ...]] = {
    'agent_runner_timing': ('duration_ms',),
    'box_execute_timing': ('total_ms', 'runtime_ms'),
    'box_selection_timing': ('total_ms',),
}
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


def inflight_journal_path(actions_path: Path) -> Path:
    return Path(actions_path).with_name(f'{Path(actions_path).stem}.inflight.jsonl')


def _interrupt_reason_for_exception(exc: BaseException | None) -> str:
    if isinstance(exc, TimeoutError):
        return 'timeout'
    if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
        return 'cancelled'
    return 'crashed'


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


def _parse_timing_message(msg: str) -> tuple[str, dict[str, Any], bool] | None:
    tokens = msg.strip().split()
    if not tokens or tokens[0] not in TIMING_KINDS:
        return None
    kind = tokens[0]
    fields: dict[str, Any] = {}
    malformed = False
    for token in tokens[1:]:
        key, sep, raw = token.partition('=')
        if not sep or not key or not raw:
            malformed = True
            continue
        if raw in ('True', 'False'):
            fields[key] = raw == 'True'
        elif key.endswith('_ms'):
            try:
                value = float(raw)
            except ValueError:
                fields[key] = raw
                malformed = True
            else:
                if math.isfinite(value):
                    fields[key] = value
                else:
                    fields[key] = raw
                    malformed = True
        else:
            fields[key] = raw
    required_ms = REQUIRED_TIMING_MS_KEYS[kind]
    if not any(isinstance(fields.get(key), float) for key in required_ms):
        malformed = True
    return kind, fields, malformed


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

    def __init__(self, path: Path, *, inflight_path: Path | None = None):
        self.path = Path(path)
        self.inflight_path = Path(inflight_path) if inflight_path is not None else inflight_journal_path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.inflight_path.parent.mkdir(parents=True, exist_ok=True)
        self._active: dict[str, ActionResult] = {}
        self._lock = threading.Lock()
        self.sources: set[str] = set()

    def __enter__(self) -> ActionWriter:
        return self

    def __exit__(self, exc_type, exc_val, _exc_tb) -> bool:
        if exc_type is None:
            self.close()
            return False
        if self._active:
            self.interrupt_active(reason=_interrupt_reason_for_exception(exc_val), error=exc_val)
        else:
            self.inflight_path.unlink(missing_ok=True)
        return False

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
        started_record = {
            'schema_version': SCHEMA_VERSION,
            'event': 'action_started',
            'action_id': result.action_id,
            'action_name': result.action_name,
            'status': 'running',
            'started_at': result.started_at,
            'started_monotonic_ns': result.started_monotonic_ns,
            'trace_id': result.trace_id,
            'pid': os.getpid(),
            'metadata': dict(result.metadata),
        }
        with self._lock:
            self._active[result.action_id] = result
            with self.inflight_path.open('a', encoding='utf-8') as stream:
                stream.write(_dump(started_record) + '\n')
                stream.flush()
        return result

    def finish(self, result: ActionResult, status: str, *, error: BaseException | None = None) -> dict[str, Any]:
        with self._lock:
            if self._active.pop(result.action_id, None) is None:
                raise ValueError(f'unknown action: {result.action_id}')
            record = result.finish(status, error=error)
            self.sources.add(result.action_name)
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(_dump(record) + '\n')
                stream.flush()
        return record

    def interrupt_active(
        self, *, reason: str = 'interrupted', error: BaseException | None = None
    ) -> list[dict[str, Any]]:
        written: list[dict[str, Any]] = []
        with self._lock:
            active = list(self._active.values())
            self._active.clear()
            if active:
                with self.path.open('a', encoding='utf-8') as stream:
                    for result in active:
                        result.metadata['interrupt_reason'] = reason
                        record = result.finish('interrupted', error=error)
                        if error is None:
                            record['error_type'] = 'ActionInterrupted'
                            record['error_message'] = f'action interrupted: {reason}'
                        self.sources.add(result.action_name)
                        stream.write(_dump(record) + '\n')
                        written.append(record)
                    stream.flush()
            self.inflight_path.unlink(missing_ok=True)
        return written

    def close(self, *, interrupt_reason: str | None = None, error: BaseException | None = None) -> list[dict[str, Any]]:
        if self._active:
            if interrupt_reason is not None:
                return self.interrupt_active(reason=interrupt_reason, error=error)
            raise RuntimeError(f'unfinished actions: {len(self._active)}')
        self.inflight_path.unlink(missing_ok=True)
        return []


def reconcile_inflight_actions(
    actions_path: Path,
    *,
    inflight_path: Path | None = None,
    reason: str = 'sigkill',
    error_message: str | None = None,
) -> list[dict[str, Any]]:
    """Synthesize interrupted terminal ActionResult records for unclosed or truncated inflight entries."""

    actions_path = Path(actions_path)
    journal = Path(inflight_path) if inflight_path is not None else inflight_journal_path(actions_path)
    if not journal.exists():
        return []
    finished_ids: set[str] = set()
    if actions_path.exists():
        with actions_path.open(encoding='utf-8', errors='replace') as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    action_id = record.get('action_id')
                    if isinstance(action_id, str) and action_id and record.get('status') != 'running':
                        finished_ids.add(action_id)
    unclosed: list[dict[str, Any]] = []
    corrupt_journal_entries: list[tuple[int, str]] = []
    seen_started: set[str] = set()
    with journal.open(encoding='utf-8', errors='replace') as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                corrupt_journal_entries.append((line_number, exc.msg))
                continue
            if not isinstance(record, dict):
                corrupt_journal_entries.append((line_number, 'record is not a JSON object'))
                continue
            action_id = record.get('action_id')
            if (
                not isinstance(action_id, str)
                or not action_id
                or action_id in finished_ids
                or action_id in seen_started
            ):
                continue
            seen_started.add(action_id)
            unclosed.append(record)
    recovered: list[dict[str, Any]] = []
    corrupt_to_emit = [
        (line_number, detail)
        for line_number, detail in corrupt_journal_entries
        if f'a-corrupt-{journal.name}-{line_number}' not in finished_ids
    ]
    if unclosed or corrupt_to_emit:
        actions_path.parent.mkdir(parents=True, exist_ok=True)
        needs_leading_newline = False
        if actions_path.exists() and actions_path.stat().st_size > 0:
            with actions_path.open('rb') as check_stream:
                check_stream.seek(-1, os.SEEK_END)
                needs_leading_newline = check_stream.read(1) != b'\n'
        with actions_path.open('a', encoding='utf-8') as stream:
            if needs_leading_newline:
                stream.write('\n')
            for started in unclosed:
                metadata = dict(started.get('metadata') or {})
                metadata['interrupt_reason'] = reason
                metadata['recovered_from_inflight'] = True
                if 'pid' in started:
                    metadata['original_pid'] = started['pid']
                record = asdict(
                    ActionResult(
                        action_id=started['action_id'],
                        action_name=str(started.get('action_name') or 'unknown'),
                        status='interrupted',
                        started_at=str(started.get('started_at') or _now()),
                        started_monotonic_ns=int(started.get('started_monotonic_ns') or 0),
                        trace_id=started.get('trace_id'),
                        finished_at=_now(),
                        finished_monotonic_ns=time.monotonic_ns(),
                        error_type='ProcessInterrupted',
                        error_message=error_message or f'action interrupted before completion ({reason})',
                        metadata=metadata,
                    )
                )
                stream.write(_dump(record) + '\n')
                recovered.append(record)
            for line_number, detail in corrupt_to_emit:
                record = asdict(
                    ActionResult(
                        action_id=f'a-corrupt-{journal.name}-{line_number}',
                        action_name='corrupt_inflight',
                        status='interrupted',
                        started_at=_now(),
                        started_monotonic_ns=time.monotonic_ns(),
                        trace_id=None,
                        finished_at=_now(),
                        finished_monotonic_ns=time.monotonic_ns(),
                        error_type='CorruptInflightRecord',
                        error_message=f'corrupt or truncated JSONL in {journal.name}:{line_number}: {detail}',
                        metadata={
                            'interrupt_reason': reason,
                            'recovered_from_inflight': True,
                            'corrupt_journal': journal.name,
                            'corrupt_line': line_number,
                        },
                    )
                )
                stream.write(_dump(record) + '\n')
                recovered.append(record)
            stream.flush()
    if not corrupt_journal_entries:
        journal.unlink(missing_ok=True)
    return recovered


def inspect_action_artifacts(artifacts: Iterable[Path]) -> dict[str, Any]:
    """Inspect action JSONL files and companion inflight journals for interrupted, unclosed, or corrupt records."""

    total = 0
    interrupted = 0
    interrupt_reasons: dict[str, int] = {}
    finished_ids: set[str] = set()
    unclosed_action_ids: list[str] = []
    seen_unclosed: set[str] = set()
    seen_journals: set[Path] = set()
    corrupt_locations: list[str] = []

    journals_to_inspect: list[Path] = []
    for artifact in artifacts:
        path = Path(artifact)
        if path.suffix != '.jsonl':
            continue
        if path.name.endswith('.inflight.jsonl'):
            if path not in seen_journals and path.exists():
                seen_journals.add(path)
                journals_to_inspect.append(path)
            continue
        if path.exists():
            with path.open(encoding='utf-8', errors='replace') as stream:
                for line_number, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        corrupt_locations.append(f'{path.name}:{line_number}')
                        continue
                    if not isinstance(record, dict):
                        corrupt_locations.append(f'{path.name}:{line_number}')
                        continue
                    if (
                        'arrival_id' in record
                        or not isinstance(record.get('action_id'), str)
                        or record.get('status') not in ACTION_STATUSES
                    ):
                        continue
                    total += 1
                    if record['status'] != 'running':
                        finished_ids.add(record['action_id'])
                    if record['status'] == 'interrupted':
                        interrupted += 1
                        metadata = record.get('metadata')
                        reason = (
                            metadata.get('interrupt_reason')
                            if isinstance(metadata, dict) and isinstance(metadata.get('interrupt_reason'), str)
                            else 'unknown'
                        )
                        interrupt_reasons[reason] = interrupt_reasons.get(reason, 0) + 1
        journal = inflight_journal_path(path)
        if journal not in seen_journals and journal.exists():
            seen_journals.add(journal)
            journals_to_inspect.append(journal)

    for journal in journals_to_inspect:
        with journal.open(encoding='utf-8', errors='replace') as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    corrupt_locations.append(f'{journal.name}:{line_number}')
                    continue
                if not isinstance(record, dict):
                    corrupt_locations.append(f'{journal.name}:{line_number}')
                    continue
                action_id = record.get('action_id')
                if (
                    isinstance(action_id, str)
                    and action_id
                    and action_id not in finished_ids
                    and action_id not in seen_unclosed
                ):
                    seen_unclosed.add(action_id)
                    unclosed_action_ids.append(action_id)
    return {
        'total': total,
        'interrupted': interrupted,
        'unclosed_inflight': len(unclosed_action_ids),
        'interrupt_reasons': interrupt_reasons,
        'unclosed_action_ids': unclosed_action_ids,
        'corrupt_lines': len(corrupt_locations),
        'corrupt_locations': corrupt_locations,
    }


@dataclass
class ObservationSample:
    observation_id: str
    source: str
    wall_time: str
    monotonic_ns: int
    sequence: int
    values: dict[str, Any]
    trace_id: str | None = None
    scope: str = 'request'
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
        scope: str | None = None,
        missing_reasons: list[str] | None = None,
    ) -> dict[str, Any]:
        resolved_scope = 'request' if scope is None else scope
        if resolved_scope not in OBSERVATION_SCOPES:
            raise ValueError(f'unknown observation scope: {resolved_scope}')
        if resolved_scope == 'global' and trace_id is not None:
            raise ValueError('global observations must not set trace_id')
        if trace_id is not None and (not isinstance(trace_id, str) or not trace_id.strip()):
            raise ValueError('trace_id must be a non-empty string when provided')
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
                scope=resolved_scope,
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
    interrupted_reason: str | None = None,
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
        size_bytes = 0
        with artifact.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
                size_bytes += len(chunk)
        rows.append({'path': str(artifact), 'bytes': size_bytes, 'sha256': digest.hexdigest()})
    index = (
        json.loads(trace_index.read_text(encoding='utf-8')) if trace_index is not None and trace_index.exists() else {}
    )
    observed_set = set(observed_sources or ())
    observed_set.update(index.get('service_log_sources', ()))
    observed = sorted(observed_set)
    missing_sources = sorted(set(expected_sources) - set(observed))
    action_summary = inspect_action_artifacts(all_artifacts)
    incomplete_reasons: list[str] = []
    if missing:
        incomplete_reasons.append(f'missing_artifacts:{len(missing)}')
    if missing_sources:
        incomplete_reasons.append(f'missing_sources:{len(missing_sources)}')
    manifest = {
        'schema_version': SCHEMA_VERSION,
        'run_id': run_id,
        'created_at': _now(),
        'expected_sources': sorted(expected_sources),
        'observed_sources': observed,
        'missing_sources': missing_sources,
        'artifacts': rows,
        'missing_artifacts': missing,
        'incomplete_reasons': incomplete_reasons,
        'completeness': 'complete',
    }
    if action_summary['total'] > 0 or action_summary['unclosed_inflight'] > 0 or action_summary['corrupt_lines'] > 0:
        manifest['actions'] = action_summary
    if action_summary['interrupted'] > 0:
        incomplete_reasons.append(f'interrupted_actions:{action_summary["interrupted"]}')
    if action_summary['unclosed_inflight'] > 0:
        incomplete_reasons.append(f'unclosed_inflight_actions:{action_summary["unclosed_inflight"]}')
    if action_summary['corrupt_lines'] > 0:
        incomplete_reasons.append(f'corrupt_action_lines:{action_summary["corrupt_lines"]}')
    if interrupted_reason:
        manifest['interrupted_reason'] = interrupted_reason
        incomplete_reasons.append(f'interrupted:{interrupted_reason}')
    if trace_index is not None:
        secondary = index.get('secondary_indexes', {})
        manifest['trace_index'] = {
            'path': str(trace_index),
            'traces': index.get('traces', 0),
            'indexed_records': index.get('indexed_records', 0),
            'global_observations': index.get('global_observations', 0),
            'unindexed_records': index.get('unindexed_records', 0),
            'missing_trace_observations': index.get('missing_trace_observations', 0),
            'unindexed_legacy_records': index.get('unindexed_legacy_records', 0),
            'corrupt_lines': index.get('corrupt_lines', 0),
            'missing_artifacts': index.get('missing_artifacts', []),
            'service_logs': len(index.get('service_logs', [])),
            'timing_counts': index.get('timing_counts', {}),
            'malformed_timings': len(secondary.get('malformed_timings', [])),
            'secondary_index_counts': {
                'by_query_id': len(secondary.get('by_query_id', {})),
                'by_session_id': len(secondary.get('by_session_id', {})),
                'by_workspace_uuid': len(secondary.get('by_workspace_uuid', {})),
                'by_run_id': len(secondary.get('by_run_id', {})),
                'uncorrelated_timings': len(secondary.get('uncorrelated_timings', [])),
            },
        }
        if manifest['trace_index']['missing_artifacts']:
            incomplete_reasons.append(
                f'trace_index_missing_artifacts:{len(manifest["trace_index"]["missing_artifacts"])}'
            )
        if manifest['trace_index']['missing_trace_observations'] > 0:
            incomplete_reasons.append(
                f'missing_trace_observations:{manifest["trace_index"]["missing_trace_observations"]}'
            )
        if manifest['trace_index']['corrupt_lines'] > 0:
            incomplete_reasons.append(f'trace_index_corrupt_lines:{manifest["trace_index"]["corrupt_lines"]}')
    if (
        action_summary['interrupted'] > 0
        or action_summary['unclosed_inflight'] > 0
        or action_summary['corrupt_lines'] > 0
        or interrupted_reason
    ):
        manifest['completeness'] = 'interrupted'
    elif incomplete_reasons:
        manifest['completeness'] = 'incomplete'
    path.write_text(_dump(manifest) + '\n', encoding='utf-8')
    return manifest


def write_trace_index(
    path: Path,
    artifacts: list[Path],
    *,
    run_id: str | None = None,
    service_logs: Mapping[str, Path] | Iterable[Path | tuple[Path, str]] | None = None,
    allow_corrupt: bool = False,
) -> dict[str, Any]:
    """Index trace-bearing JSONL and service-log timing evidence without fabricating links."""

    # shortcut: build the index at run close, upgrade to streaming for very large evidence sets.
    entries: dict[str, dict[str, Any]] = {}
    global_observations_by_artifact: dict[str, int] = {}
    missing_trace_observations_by_artifact: dict[str, int] = {}
    unindexed_legacy_by_artifact: dict[str, int] = {}
    unindexed_by_artifact: dict[str, int] = {}
    corrupt_by_artifact: dict[str, list[int]] = {}
    missing_artifacts: list[str] = []
    indexed_records = 0
    for artifact in artifacts:
        if not artifact.exists():
            missing_artifacts.append(str(artifact))
            continue
        with artifact.open(encoding='utf-8', errors='replace') as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    if not allow_corrupt:
                        raise ValueError(f'invalid JSONL in {artifact}:{line_number}: {exc.msg}') from exc
                    corrupt_by_artifact.setdefault(str(artifact), []).append(line_number)
                    continue
                if not isinstance(record, dict):
                    if not allow_corrupt:
                        raise ValueError(f'JSONL record in {artifact}:{line_number} must be an object')
                    corrupt_by_artifact.setdefault(str(artifact), []).append(line_number)
                    continue
                trace_id = record.get('trace_id')
                if not isinstance(trace_id, str) or not trace_id.strip():
                    key = str(artifact)
                    has_request_identity = any(
                        record.get(field) not in (None, '') for field in ('action_id', 'arrival_id', 'run_id')
                    )
                    is_valid_global_observation = (
                        record.get('scope') == 'global'
                        and isinstance(record.get('observation_id'), str)
                        and bool(record['observation_id'].strip())
                        and trace_id is None
                        and not has_request_identity
                    )
                    if is_valid_global_observation:
                        global_observations_by_artifact[key] = global_observations_by_artifact.get(key, 0) + 1
                    elif record.get('scope') in OBSERVATION_SCOPES or 'observation_id' in record:
                        missing_trace_observations_by_artifact[key] = (
                            missing_trace_observations_by_artifact.get(key, 0) + 1
                        )
                        unindexed_by_artifact[key] = unindexed_by_artifact.get(key, 0) + 1
                    else:
                        unindexed_legacy_by_artifact[key] = unindexed_legacy_by_artifact.get(key, 0) + 1
                        unindexed_by_artifact[key] = unindexed_by_artifact.get(key, 0) + 1
                    continue
                trace_id = trace_id.strip()
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
        'malformed_timings': [],
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
        with log_path.open(encoding='utf-8', errors='replace', newline='\n') as stream:
            for log_record in parse_service_log_records(stream, service_name):
                record_count += 1
                if log_record.level in ('ERROR', 'FATAL'):
                    error_count += 1
                elif log_record.level == 'WARN':
                    warn_count += 1
                parsed_timing = _parse_timing_message(log_record.msg)
                if parsed_timing is not None:
                    kind, fields, malformed = parsed_timing
                    if malformed:
                        secondary_indexes['malformed_timings'].append(
                            {
                                'kind': kind,
                                'service': log_record.service,
                                'artifact': artifact_ref,
                                'line': log_record.log_line,
                                'ts': log_record.ts,
                                'fields': fields,
                                'correlation_level': 'uncorrelated',
                                'deterministic_trace_binding': False,
                                'malformed': True,
                            }
                        )
                        continue
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
        'global_observations': sum(global_observations_by_artifact.values()),
        'global_observations_by_artifact': global_observations_by_artifact,
        'unindexed_records': sum(unindexed_by_artifact.values()),
        'unindexed_by_artifact': unindexed_by_artifact,
        'missing_trace_observations': sum(missing_trace_observations_by_artifact.values()),
        'missing_trace_observations_by_artifact': missing_trace_observations_by_artifact,
        'unindexed_legacy_records': sum(unindexed_legacy_by_artifact.values()),
        'unindexed_legacy_by_artifact': unindexed_legacy_by_artifact,
        'corrupt_lines': sum(len(lines) for lines in corrupt_by_artifact.values()),
        'corrupt_by_artifact': corrupt_by_artifact,
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
