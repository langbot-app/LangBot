"""Versioned action and observation evidence for regression tooling."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = '1'
ACTION_STATUSES = frozenset({'running', 'succeeded', 'failed', 'timed_out', 'cancelled', 'blocked', 'expired'})


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


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
) -> dict[str, Any]:
    rows, missing = [], []
    for artifact in artifacts:
        if not artifact.exists():
            missing.append(str(artifact))
            continue
        digest = hashlib.sha256()
        with artifact.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        rows.append({'path': str(artifact), 'bytes': artifact.stat().st_size, 'sha256': digest.hexdigest()})
    observed = sorted(set(observed_sources or ()))
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
    path.write_text(_dump(manifest) + '\n', encoding='utf-8')
    return manifest
