#!/usr/bin/env python3
"""Run the final LangBot Cloud resource-stability acceptance gate.

The short synthetic probes in this repository prove that selected registries
plateau.  This tool is for the production-candidate topology: it samples Core,
Plugin Runtime and Box health endpoints together with their Linux process trees
and cgroup v2 accounting, streams raw evidence to JSONL, and fails when the
post-load tail shows a material leak or sustained CPU pressure.

Examples:

    uv run python scripts/cloud_runtime_soak.py \
      --duration 24h --startup-grace 5m --cooldown 30m \
      --endpoint core=http://langbot:5300/healthz \
      --endpoint plugin=http://langbot-plugin-runtime:5400/healthz \
      --endpoint box=http://langbot-box:5410/readyz \
      --cgroup core=/sys/fs/cgroup/langbot \
      --cgroup plugin=/sys/fs/cgroup/langbot-plugin-runtime \
      --cgroup box=/sys/fs/cgroup/langbot-box \
      --samples-file artifacts/cloud-soak-samples.jsonl \
      --report-file artifacts/cloud-soak-report.json \
      --workload uv run python tests/load/cloud_candidate_workload.py

Run this from a node/sidecar that can read the target cgroups.  A process target
(``--pid name=PID``) is useful when cgroup paths are not directly mounted, but
cgroup evidence is still required for the production gate because only cgroups
report OOM, PID-limit and CPU-throttling events.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import dataclasses
import datetime as dt
import json
import math
import os
import re
import signal
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO


BYTES_PER_MIB = 1024 * 1024
MAX_HTTP_BODY_BYTES = BYTES_PER_MIB
MAX_FLATTENED_HTTP_METRICS = 256
MAX_PROCESS_TREE_SIZE = 4096
MAX_TARGETS = 32
MAX_SAMPLER_THREADS = 8
_DIRECT_HTTP_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TARGET_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')
COUNTER_SUFFIXES = (
    '.memory.events.high',
    '.memory.events.max',
    '.memory.events.oom',
    '.memory.events.oom_kill',
    '.memory.events.oom_group_kill',
    '.pids.events.max',
)
REJECTION_SUFFIXES = (
    '.blocking_executor.global_rejected_total',
    '.blocking_executor.scope_rejected_total',
)
RUNTIME_FAILURE_COUNTER_SUFFIXES = ('.restart_coordinator.circuit_open_total',)
DRAIN_GAUGE_SUFFIXES = (
    '.blocking_executor.pending',
    '.restart_coordinator.active_launches',
    '.restart_coordinator.gate_waiters',
    '.restart_coordinator.half_open_probe_inflight',
    '.restart_coordinator.open_remaining_seconds',
    '.resources.runtimes.mcp_projection_retirements',
    '.resources.runtimes.mcp_projection_reconcile_active',
    '.resources.runtimes.message_aggregation_buffers',
    '.resources.runtimes.message_aggregation_scopes',
)
TRANSIENT_GAUGE_SUFFIXES = (
    '.resources.telemetry_tasks',
    '.resources.query_pool.queued',
    '.resources.runtimes.mcp_host_tasks',
    '.resources.runtimes.mcp_dispatch_tasks',
    '.resources.creating_session_tasks',
    '.resources.closing_session_tasks',
    '.resources.background_tasks',
)
CAPACITY_GAUGE_PAIRS = (
    (
        '.resources.directory.active_workspaces',
        '.resources.directory.max_active_workspaces',
    ),
    (
        '.resources.directory.last_batch_workspaces',
        '.resources.directory.max_snapshot_workspaces',
    ),
    (
        '.resources.directory.last_batch_memberships',
        '.resources.directory.max_snapshot_memberships',
    ),
    (
        '.resources.database_pool.checked_out',
        '.resources.database_pool.configured_capacity',
    ),
)
REQUIRED_CORE_CAPACITY_GAUGES = frozenset(suffix for pair in CAPACITY_GAUGE_PAIRS for suffix in pair)


@dataclasses.dataclass(frozen=True, slots=True)
class Target:
    name: str
    kind: str
    location: str


@dataclasses.dataclass(frozen=True, slots=True)
class MetricSample:
    monotonic_seconds: float
    wall_time: str
    metrics: dict[str, float]


@dataclasses.dataclass(slots=True)
class TargetState:
    target: Target
    samples: deque[MetricSample]
    baseline_metrics: dict[str, float] | None = None
    last_metrics: dict[str, float] | None = None
    observed_max_metrics: dict[str, float] = dataclasses.field(default_factory=dict)
    attempted_samples: int = 0
    successful_samples: int = 0
    failed_samples: int = 0
    consecutive_failures: int = 0
    max_consecutive_failures: int = 0
    first_error: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class Thresholds:
    max_memory_growth_bytes: int
    max_memory_slope_bytes_per_hour: float
    max_tail_cpu_cores: float
    max_throttled_period_ratio: float
    allow_rejections: bool
    max_transient_gauge_growth: float
    require_hard_limits: bool
    max_event_loop_lag_ms: float
    max_event_loop_p95_lag_ms: float
    require_event_loop_metrics: bool


@dataclasses.dataclass(frozen=True, slots=True)
class WorkloadResult:
    executable: str | None
    argument_count: int
    started_at_seconds: float | None
    completed_at_seconds: float | None
    return_code: int | None
    timed_out: bool


@dataclasses.dataclass(frozen=True, slots=True)
class GateResult:
    failures: tuple[str, ...]
    warnings: tuple[str, ...]
    targets: dict[str, dict[str, Any]]

    @property
    def passed(self) -> bool:
        return not self.failures


def parse_duration(value: str) -> float:
    """Parse a positive duration such as 30s, 5m, 2h or 1d."""

    match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*([smhd]?)\s*', value, re.IGNORECASE)
    if match is None:
        raise argparse.ArgumentTypeError(f'invalid duration: {value!r}')
    amount = float(match.group(1))
    if amount <= 0:
        raise argparse.ArgumentTypeError('duration must be greater than zero')
    multiplier = {
        '': 1.0,
        's': 1.0,
        'm': 60.0,
        'h': 3600.0,
        'd': 86400.0,
    }[match.group(2).lower()]
    return amount * multiplier


def _parse_named_values(values: Iterable[str], *, option: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        name, separator, location = value.partition('=')
        name = name.strip()
        location = location.strip()
        if not separator or not TARGET_NAME_RE.fullmatch(name) or not location:
            raise ValueError(f'{option} must use NAME=VALUE with a safe, non-empty name: {value!r}')
        if name in parsed:
            raise ValueError(f'duplicate target name {name!r} in {option}')
        parsed[name] = location
    return parsed


def _safe_endpoint_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise ValueError(f'health endpoint must be an http(s) URL: {value!r}')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('health endpoint URLs must not contain credentials, query parameters or fragments')
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path or '/', '', ''))


def build_targets(
    *,
    endpoints: Iterable[str],
    cgroups: Iterable[str],
    pids: Iterable[str],
) -> list[Target]:
    targets: list[Target] = []
    seen_names: set[str] = set()
    for kind, option, values in (
        ('endpoint', '--endpoint', endpoints),
        ('cgroup', '--cgroup', cgroups),
        ('process', '--pid', pids),
    ):
        for name, location in _parse_named_values(values, option=option).items():
            qualified_name = f'{kind}:{name}'
            if qualified_name in seen_names:
                raise ValueError(f'duplicate target {qualified_name!r}')
            seen_names.add(qualified_name)
            if kind == 'endpoint':
                location = _safe_endpoint_url(location)
            elif kind == 'cgroup':
                location = str(Path(location).resolve())
            else:
                try:
                    pid = int(location)
                except ValueError as exc:
                    raise ValueError(f'{option} PID must be an integer: {location!r}') from exc
                if pid <= 0:
                    raise ValueError(f'{option} PID must be greater than zero')
                location = str(pid)
            targets.append(Target(name=name, kind=kind, location=location))
    return targets


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding='utf-8').strip()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return None


def _read_integer(path: Path) -> int | None:
    value = _read_text(path)
    if value is None or value == 'max':
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _read_key_value_file(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    text = _read_text(path)
    if text is None:
        return values
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            values[fields[0]] = int(fields[1])
        except ValueError:
            continue
    return values


def read_cgroup_snapshot(path: Path) -> dict[str, float]:
    """Read bounded cgroup v2 resource accounting from *path*."""

    if not path.is_dir():
        raise RuntimeError(f'cgroup directory is unavailable: {path}')
    metrics: dict[str, float] = {}
    scalar_files = {
        'memory.current': 'memory.current_bytes',
        'memory.peak': 'memory.peak_bytes',
        'memory.swap.current': 'memory.swap.current_bytes',
        'memory.max': 'memory.max_bytes',
        'memory.swap.max': 'memory.swap.max_bytes',
        'pids.current': 'pids.current',
        'pids.max': 'pids.max',
    }
    for filename, metric_name in scalar_files.items():
        value = _read_integer(path / filename)
        if value is not None:
            metrics[metric_name] = float(value)

    for filename, prefix in (
        ('cpu.stat', 'cpu'),
        ('memory.events', 'memory.events'),
        ('pids.events', 'pids.events'),
    ):
        for key, value in _read_key_value_file(path / filename).items():
            metrics[f'{prefix}.{key}'] = float(value)

    cpu_max = _read_text(path / 'cpu.max')
    if cpu_max:
        fields = cpu_max.split()
        if len(fields) == 2:
            if fields[0] != 'max':
                with contextlib.suppress(ValueError):
                    metrics['cpu.quota_usec'] = float(int(fields[0]))
            with contextlib.suppress(ValueError):
                metrics['cpu.period_usec'] = float(int(fields[1]))
    required_metrics = {
        'memory.current_bytes',
        'memory.events.oom',
        'cpu.usage_usec',
        'pids.current',
        'pids.events.max',
    }
    missing_metrics = sorted(required_metrics - metrics.keys())
    if missing_metrics:
        raise RuntimeError(f'cgroup v2 metrics missing from {path}: {", ".join(missing_metrics)}')
    return metrics


def _read_process_ids(proc_root: Path, root_pid: int) -> list[int]:
    pending = [root_pid]
    discovered: list[int] = []
    seen: set[int] = set()
    while pending and len(discovered) < MAX_PROCESS_TREE_SIZE:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        if not (proc_root / str(pid)).is_dir():
            continue
        discovered.append(pid)
        task_root = proc_root / str(pid) / 'task'
        try:
            task_ids = tuple(task_root.iterdir())
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            task_ids = ()
        for task_path in task_ids:
            children = _read_text(task_path / 'children')
            if not children:
                continue
            for child in children.split():
                with contextlib.suppress(ValueError):
                    child_pid = int(child)
                    if child_pid not in seen:
                        pending.append(child_pid)
    if pending:
        raise RuntimeError(f'process tree exceeded {MAX_PROCESS_TREE_SIZE} processes')
    return discovered


def _read_process_status(path: Path) -> tuple[int, int]:
    rss_bytes = 0
    threads = 0
    text = _read_text(path)
    if text is None:
        return rss_bytes, threads
    for line in text.splitlines():
        key, separator, raw_value = line.partition(':')
        if not separator:
            continue
        fields = raw_value.split()
        if not fields:
            continue
        if key == 'VmRSS':
            with contextlib.suppress(ValueError):
                rss_bytes = int(fields[0]) * 1024
        elif key == 'Threads':
            with contextlib.suppress(ValueError):
                threads = int(fields[0])
    return rss_bytes, threads


def _read_process_cpu_seconds(path: Path, clock_ticks: int) -> float:
    text = _read_text(path)
    if text is None:
        return 0.0
    _, separator, remainder = text.rpartition(')')
    if not separator:
        return 0.0
    fields = remainder.split()
    if len(fields) <= 12:
        return 0.0
    try:
        return (int(fields[11]) + int(fields[12])) / clock_ticks
    except ValueError:
        return 0.0


def _count_open_fds(path: Path) -> int:
    try:
        with os.scandir(path) as entries:
            return sum(1 for _ in entries)
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return 0


def read_process_snapshot(
    pid: int,
    *,
    proc_root: Path = Path('/proc'),
    clock_ticks: int | None = None,
) -> dict[str, float]:
    """Aggregate RSS, CPU, threads and file descriptors for a process tree."""

    process_ids = _read_process_ids(proc_root, pid)
    if not process_ids:
        raise RuntimeError(f'process {pid} is unavailable')
    ticks = clock_ticks or int(os.sysconf('SC_CLK_TCK'))
    rss_bytes = 0
    threads = 0
    open_fds = 0
    cpu_seconds = 0.0
    for process_id in process_ids:
        process_root = proc_root / str(process_id)
        process_rss, process_threads = _read_process_status(process_root / 'status')
        rss_bytes += process_rss
        threads += process_threads
        open_fds += _count_open_fds(process_root / 'fd')
        cpu_seconds += _read_process_cpu_seconds(process_root / 'stat', ticks)
    return {
        'rss_bytes': float(rss_bytes),
        'cpu_seconds': cpu_seconds,
        'threads': float(threads),
        'open_fds': float(open_fds),
        'processes': float(len(process_ids)),
    }


def _flatten_numeric_json(
    value: Any,
    *,
    prefix: str = 'body',
    output: dict[str, float] | None = None,
    depth: int = 0,
) -> dict[str, float]:
    if output is None:
        output = {}
    if depth > 8 or len(output) >= MAX_FLATTENED_HTTP_METRICS:
        return output
    if isinstance(value, bool):
        output[prefix] = float(value)
    elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        output[prefix] = float(value)
    elif isinstance(value, Mapping):
        for key, nested_value in value.items():
            if len(output) >= MAX_FLATTENED_HTTP_METRICS:
                break
            safe_key = str(key).replace('.', '_')[:128]
            _flatten_numeric_json(
                nested_value,
                prefix=f'{prefix}.{safe_key}',
                output=output,
                depth=depth + 1,
            )
    return output


def read_endpoint_snapshot(
    url: str,
    *,
    timeout_seconds: float,
    opener: Callable[..., Any] | None = None,
) -> dict[str, float]:
    """Fetch a bounded health response and flatten numeric resource gauges."""

    request = urllib.request.Request(
        url,
        headers={
            'Accept': 'application/json, text/plain',
            'User-Agent': 'langbot-cloud-runtime-soak/1',
        },
        method='GET',
    )
    started_at = time.monotonic()
    direct_opener = opener or _DIRECT_HTTP_OPENER.open
    try:
        response_context = direct_opener(request, timeout=timeout_seconds)
        with response_context as response:
            status = int(getattr(response, 'status', response.getcode()))
            content_type = str(response.headers.get('Content-Type', ''))
            body = response.read(MAX_HTTP_BODY_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'health endpoint returned HTTP {exc.code}') from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f'health endpoint request failed: {type(exc).__name__}') from exc
    if len(body) > MAX_HTTP_BODY_BYTES:
        raise RuntimeError(f'health endpoint response exceeded {MAX_HTTP_BODY_BYTES} bytes')
    if not 200 <= status < 300:
        raise RuntimeError(f'health endpoint returned HTTP {status}')

    metrics = {
        'http.status': float(status),
        'http.latency_ms': (time.monotonic() - started_at) * 1000,
        'http.ok': 1.0,
    }
    if 'json' in content_type.lower() or body.lstrip().startswith((b'{', b'[')):
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError('health endpoint returned invalid JSON') from exc
        if isinstance(payload, Mapping):
            if 'code' in payload and payload['code'] != 0:
                raise RuntimeError(f'health endpoint reported code={payload["code"]!r}')
            if payload.get('live') is False or payload.get('ready') is False:
                raise RuntimeError('health endpoint reported not ready')
        metrics.update(_flatten_numeric_json(payload))
    return metrics


def _sample_target(target: Target, *, http_timeout_seconds: float) -> dict[str, float]:
    if target.kind == 'endpoint':
        return read_endpoint_snapshot(target.location, timeout_seconds=http_timeout_seconds)
    if target.kind == 'cgroup':
        return read_cgroup_snapshot(Path(target.location))
    if target.kind == 'process':
        return read_process_snapshot(int(target.location))
    raise AssertionError(f'unsupported target kind: {target.kind}')


def _tail_metric_points(
    samples: Sequence[MetricSample],
    *,
    analysis_start_seconds: float,
    metric: str,
) -> list[tuple[float, float]]:
    return [
        (sample.monotonic_seconds, sample.metrics[metric])
        for sample in samples
        if sample.monotonic_seconds >= analysis_start_seconds and metric in sample.metrics
    ]


def _robust_growth(points: Sequence[tuple[float, float]]) -> float:
    width = max(1, min(len(points) // 5, 12))
    initial = statistics.median(value for _, value in points[:width])
    final = statistics.median(value for _, value in points[-width:])
    return final - initial


def _slope_per_hour(points: Sequence[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    origin = points[0][0]
    xs = [timestamp - origin for timestamp, _ in points]
    ys = [value for _, value in points]
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    denominator = sum((value - x_mean) ** 2 for value in xs)
    if denominator <= 0:
        return 0.0
    slope_per_second = (
        sum((x_value - x_mean) * (y_value - y_mean) for x_value, y_value in zip(xs, ys, strict=True)) / denominator
    )
    return slope_per_second * 3600


def _counter_delta(
    first: MetricSample | Mapping[str, float],
    last: MetricSample | Mapping[str, float],
    metric: str,
) -> float | None:
    first_metrics = first.metrics if isinstance(first, MetricSample) else first
    last_metrics = last.metrics if isinstance(last, MetricSample) else last
    if metric not in first_metrics or metric not in last_metrics:
        return None
    return last_metrics[metric] - first_metrics[metric]


def evaluate_gate(
    states: Sequence[TargetState],
    *,
    analysis_start_seconds: float,
    thresholds: Thresholds,
) -> GateResult:
    failures: list[str] = []
    warnings: list[str] = []
    summaries: dict[str, dict[str, Any]] = {}

    for state in states:
        target_id = f'{state.target.kind}:{state.target.name}'
        target_summary: dict[str, Any] = {
            'attempted_samples': state.attempted_samples,
            'successful_samples': state.successful_samples,
            'failed_samples': state.failed_samples,
            'max_consecutive_failures': state.max_consecutive_failures,
            'first_error': state.first_error,
        }
        summaries[target_id] = target_summary
        if state.failed_samples:
            failures.append(
                f'{target_id} had {state.failed_samples} failed samples '
                f'(max consecutive {state.max_consecutive_failures}): {state.first_error}'
            )
        samples = list(state.samples)
        tail_samples = [sample for sample in samples if sample.monotonic_seconds >= analysis_start_seconds]
        target_summary['tail_samples'] = len(tail_samples)
        if len(tail_samples) < 2:
            failures.append(f'{target_id} has fewer than two successful tail samples')
            continue

        first = tail_samples[0]
        last = tail_samples[-1]
        tail_elapsed = last.monotonic_seconds - first.monotonic_seconds
        target_summary['tail_elapsed_seconds'] = tail_elapsed
        if tail_elapsed <= 0:
            failures.append(f'{target_id} has no measurable tail interval')
            continue

        if state.target.kind == 'cgroup':
            baseline_metrics = state.baseline_metrics or first.metrics
            resource_limits = {
                'cpu_quota_usec': baseline_metrics.get('cpu.quota_usec'),
                'cpu_period_usec': baseline_metrics.get('cpu.period_usec'),
                'memory_max_bytes': baseline_metrics.get('memory.max_bytes'),
                'memory_swap_max_bytes': baseline_metrics.get('memory.swap.max_bytes'),
                'pids_max': baseline_metrics.get('pids.max'),
            }
            hard_limits = {
                'cpu': resource_limits['cpu_quota_usec'] is not None,
                'memory': resource_limits['memory_max_bytes'] is not None,
                'swap': resource_limits['memory_swap_max_bytes'] is not None,
                'pids': resource_limits['pids_max'] is not None,
            }
            target_summary['resource_limits'] = resource_limits
            target_summary['hard_limits'] = hard_limits
            if state.last_metrics is not None:
                target_summary['memory.peak_bytes'] = state.last_metrics.get('memory.peak_bytes')
            if thresholds.require_hard_limits:
                missing_limits = sorted(name for name, enabled in hard_limits.items() if not enabled)
                if missing_limits:
                    failures.append(f'{target_id} is missing hard cgroup limits: {", ".join(missing_limits)}')
            for suffix in COUNTER_SUFFIXES:
                metric = suffix.lstrip('.')
                delta = _counter_delta(
                    state.baseline_metrics or first,
                    state.last_metrics or last,
                    metric,
                )
                if delta is not None:
                    target_summary[f'delta.{metric}'] = delta
                    if delta < 0:
                        failures.append(f'{target_id} monotonic counter {metric} reset; the cgroup may have restarted')
                    elif delta > 0:
                        failures.append(f'{target_id} increased {metric} by {delta:g}')

            period_delta = _counter_delta(
                state.baseline_metrics or first,
                state.last_metrics or last,
                'cpu.nr_periods',
            )
            throttled_delta = _counter_delta(
                state.baseline_metrics or first,
                state.last_metrics or last,
                'cpu.nr_throttled',
            )
            if period_delta is not None and throttled_delta is not None and period_delta > 0:
                throttled_ratio = max(throttled_delta, 0) / period_delta
                target_summary['cpu.throttled_period_ratio'] = throttled_ratio
                if throttled_ratio > thresholds.max_throttled_period_ratio:
                    failures.append(
                        f'{target_id} CPU throttled-period ratio {throttled_ratio:.3f} '
                        f'exceeded {thresholds.max_throttled_period_ratio:.3f}'
                    )
            elif period_delta is not None and period_delta < 0:
                failures.append(f'{target_id} monotonic CPU counters reset; the cgroup may have restarted')

        memory_metric = {
            'cgroup': 'memory.current_bytes',
            'process': 'rss_bytes',
        }.get(state.target.kind)
        if memory_metric is not None:
            memory_points = _tail_metric_points(
                tail_samples,
                analysis_start_seconds=analysis_start_seconds,
                metric=memory_metric,
            )
            if len(memory_points) >= 2:
                growth = _robust_growth(memory_points)
                slope = _slope_per_hour(memory_points)
                target_summary['memory.metric'] = memory_metric
                target_summary['memory.robust_growth_bytes'] = growth
                target_summary['memory.slope_bytes_per_hour'] = slope
                if growth > thresholds.max_memory_growth_bytes and slope > thresholds.max_memory_slope_bytes_per_hour:
                    failures.append(
                        f'{target_id} {memory_metric} grew {growth / BYTES_PER_MIB:.2f} MiB '
                        f'at {slope / BYTES_PER_MIB:.2f} MiB/hour'
                    )
            else:
                warnings.append(f'{target_id} did not expose {memory_metric} throughout the tail')

        cpu_metric = {
            'cgroup': 'cpu.usage_usec',
            'process': 'cpu_seconds',
        }.get(state.target.kind)
        if cpu_metric is not None:
            cpu_delta = _counter_delta(first, last, cpu_metric)
            if cpu_delta is not None:
                cpu_seconds = cpu_delta / 1_000_000 if cpu_metric.endswith('_usec') else cpu_delta
                average_cores = max(cpu_seconds, 0) / tail_elapsed
                target_summary['cpu.average_cores'] = average_cores
                if average_cores > thresholds.max_tail_cpu_cores:
                    failures.append(
                        f'{target_id} tail CPU averaged {average_cores:.3f} cores, '
                        f'above {thresholds.max_tail_cpu_cores:.3f}'
                    )

        if state.target.kind == 'endpoint':
            metric_keys = (
                set(first.metrics)
                | set(last.metrics)
                | set(state.baseline_metrics or ())
                | set(state.last_metrics or ())
            )
            if state.target.name == 'core':
                for suffix in sorted(REQUIRED_CORE_CAPACITY_GAUGES):
                    matching_metrics = sorted(key for key in metric_keys if key.endswith(suffix))
                    if not matching_metrics:
                        failures.append(f'{target_id} did not expose required capacity gauge {suffix}')
                        continue
                    for metric in matching_metrics:
                        if any(metric not in sample.metrics for sample in tail_samples):
                            failures.append(
                                f'{target_id} did not expose required capacity gauge {metric} throughout the tail'
                            )
            for suffix in REJECTION_SUFFIXES:
                if thresholds.allow_rejections:
                    break
                for metric in sorted(key for key in metric_keys if key.endswith(suffix)):
                    delta = _counter_delta(
                        state.baseline_metrics or first,
                        state.last_metrics or last,
                        metric,
                    )
                    if delta is not None and delta > 0:
                        failures.append(f'{target_id} increased {metric} by {delta:g}')
                    elif delta is not None and delta < 0:
                        failures.append(f'{target_id} monotonic counter {metric} reset; the runtime may have restarted')
            for suffix in RUNTIME_FAILURE_COUNTER_SUFFIXES:
                for metric in sorted(key for key in metric_keys if key.endswith(suffix)):
                    delta = _counter_delta(
                        state.baseline_metrics or first,
                        state.last_metrics or last,
                        metric,
                    )
                    if delta is not None and delta > 0:
                        failures.append(f'{target_id} increased {metric} by {delta:g}')
                    elif delta is not None and delta < 0:
                        failures.append(f'{target_id} monotonic counter {metric} reset; the runtime may have restarted')
            for suffix in DRAIN_GAUGE_SUFFIXES:
                for metric in sorted(key for key in metric_keys if key.endswith(suffix)):
                    values = [sample.metrics[metric] for sample in tail_samples if metric in sample.metrics]
                    if values and min(values) > 0:
                        failures.append(f'{target_id} kept {metric} above zero for the entire tail')
            for suffix in TRANSIENT_GAUGE_SUFFIXES:
                for metric in sorted(key for key in metric_keys if key.endswith(suffix)):
                    growth = _counter_delta(first, last, metric)
                    if growth is not None and growth > thresholds.max_transient_gauge_growth:
                        failures.append(f'{target_id} transient gauge {metric} grew by {growth:g} during the idle tail')
            for current_suffix, capacity_suffix in CAPACITY_GAUGE_PAIRS:
                for current_metric in sorted(key for key in metric_keys if key.endswith(current_suffix)):
                    capacity_metric = current_metric[: -len(current_suffix)] + capacity_suffix
                    observed = [
                        (sample.metrics[current_metric], sample.metrics.get(capacity_metric))
                        for sample in tail_samples
                        if current_metric in sample.metrics
                    ]
                    if any(capacity is None for _current, capacity in observed):
                        failures.append(f'{target_id} exposed {current_metric} without matching {capacity_metric}')
                        continue
                    if any(
                        current < 0 or capacity is None or capacity <= 0 or current > capacity
                        for current, capacity in observed
                    ):
                        failures.append(
                            f'{target_id} exceeded or invalidated capacity pair {current_metric} <= {capacity_metric}'
                        )

            loop_running_metrics = sorted(key for key in metric_keys if key.endswith('.event_loop.running'))
            if not loop_running_metrics:
                if thresholds.require_event_loop_metrics:
                    failures.append(f'{target_id} did not expose event-loop health metrics')
            else:
                for metric in loop_running_metrics:
                    running_values = [sample.metrics[metric] for sample in tail_samples if metric in sample.metrics]
                    if not running_values or min(running_values) < 1:
                        failures.append(f'{target_id} event-loop monitor was not running throughout the tail')

            recent_max_metrics = sorted(
                key for key in state.observed_max_metrics if key.endswith('.event_loop.recent_max_lag_ms')
            )
            for metric in recent_max_metrics:
                observed_max = state.observed_max_metrics[metric]
                target_summary['event_loop.max_observed_recent_lag_ms'] = observed_max
                if observed_max > thresholds.max_event_loop_lag_ms:
                    failures.append(
                        f'{target_id} event-loop lag reached '
                        f'{observed_max:.2f} ms, above '
                        f'{thresholds.max_event_loop_lag_ms:.2f} ms'
                    )

            recent_p95_metrics = sorted(key for key in metric_keys if key.endswith('.event_loop.recent_p95_lag_ms'))
            for metric in recent_p95_metrics:
                p95_values = [sample.metrics[metric] for sample in tail_samples if metric in sample.metrics]
                if not p95_values:
                    continue
                maximum_p95 = max(p95_values)
                target_summary['event_loop.max_tail_recent_p95_lag_ms'] = maximum_p95
                if maximum_p95 > thresholds.max_event_loop_p95_lag_ms:
                    failures.append(
                        f'{target_id} event-loop recent p95 reached '
                        f'{maximum_p95:.2f} ms, above '
                        f'{thresholds.max_event_loop_p95_lag_ms:.2f} ms'
                    )

            sample_total_metrics = sorted(key for key in metric_keys if key.endswith('.event_loop.samples_total'))
            for metric in sample_total_metrics:
                delta = _counter_delta(
                    state.baseline_metrics or first,
                    state.last_metrics or last,
                    metric,
                )
                if delta is not None and delta < 0:
                    failures.append(f'{target_id} event-loop sample counter reset; the runtime may have restarted')

    return GateResult(
        failures=tuple(dict.fromkeys(failures)),
        warnings=tuple(dict.fromkeys(warnings)),
        targets=summaries,
    )


def _utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _open_output(path: Path | None) -> TextIO | None:
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open('w', encoding='utf-8')


def _write_json_line(stream: TextIO | None, payload: Mapping[str, Any]) -> None:
    if stream is None:
        return
    stream.write(json.dumps(payload, sort_keys=True, separators=(',', ':')) + '\n')
    stream.flush()


def _terminate_workload(process: subprocess.Popen[Any], *, grace_seconds: float = 10.0) -> None:
    if process.poll() is not None:
        return
    if os.name == 'posix':
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
    else:
        process.terminate()
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        if os.name == 'posix':
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=grace_seconds)


def run_soak(
    *,
    targets: Sequence[Target],
    duration_seconds: float,
    sample_interval_seconds: float,
    startup_grace_seconds: float,
    cooldown_seconds: float,
    analysis_window_seconds: float,
    http_timeout_seconds: float,
    thresholds: Thresholds,
    workload_command: Sequence[str] | None,
    samples_stream: TextIO | None,
) -> tuple[dict[str, Any], int]:
    started_at_wall = _utc_now()
    started_at = time.monotonic()
    deadline = started_at + duration_seconds
    max_tail_seconds = max(analysis_window_seconds, cooldown_seconds, sample_interval_seconds)
    retained_samples = min(
        max(4, math.ceil(max_tail_seconds / sample_interval_seconds) + 4),
        100_000,
    )
    states = [TargetState(target=target, samples=deque(maxlen=retained_samples)) for target in targets]
    workload: subprocess.Popen[Any] | None = None
    workload_started_at: float | None = None
    workload_completed_at: float | None = None
    workload_return_code: int | None = None
    workload_timed_out = False
    workload_start_error: str | None = None
    interrupted = False
    next_sample_at = started_at
    previous_sigterm_handler: Any = None

    def interrupt_on_sigterm(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    with contextlib.suppress(ValueError):
        previous_sigterm_handler = signal.signal(signal.SIGTERM, interrupt_on_sigterm)
    sampler_pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, min(len(states), MAX_SAMPLER_THREADS)),
        thread_name_prefix='langbot-soak-sampler',
    )

    try:
        while True:
            now = time.monotonic()
            if workload is None and workload_command and now - started_at >= startup_grace_seconds:
                workload_started_at = now
                try:
                    workload = subprocess.Popen(
                        list(workload_command),
                        stdin=subprocess.DEVNULL,
                        stdout=sys.stderr,
                        stderr=sys.stderr,
                        start_new_session=True,
                    )
                except OSError as exc:
                    workload_start_error = f'{type(exc).__name__}: {exc}'
                    break

            if workload is not None and workload_return_code is None:
                polled = workload.poll()
                if polled is not None:
                    workload_return_code = polled
                    workload_completed_at = now

            if now >= next_sample_at:
                sample_wall_time = _utc_now()
                sample_record: dict[str, Any] = {
                    'schema_version': 1,
                    'wall_time': sample_wall_time,
                    'elapsed_seconds': now - started_at,
                    'targets': {},
                }
                in_gate_window = now - started_at >= startup_grace_seconds
                sample_futures = [
                    (
                        state,
                        sampler_pool.submit(
                            _sample_target,
                            state.target,
                            http_timeout_seconds=http_timeout_seconds,
                        ),
                    )
                    for state in states
                ]
                for state, sample_future in sample_futures:
                    state.attempted_samples += 1
                    target_id = f'{state.target.kind}:{state.target.name}'
                    try:
                        metrics = sample_future.result()
                    except Exception as exc:
                        error = f'{type(exc).__name__}: {exc}'
                        sample_record['targets'][target_id] = {'error': error}
                        if in_gate_window:
                            state.failed_samples += 1
                            state.consecutive_failures += 1
                            state.max_consecutive_failures = max(
                                state.max_consecutive_failures,
                                state.consecutive_failures,
                            )
                            if state.first_error is None:
                                state.first_error = error
                    else:
                        sample = MetricSample(
                            monotonic_seconds=now,
                            wall_time=sample_wall_time,
                            metrics=metrics,
                        )
                        state.samples.append(sample)
                        state.successful_samples += 1
                        state.consecutive_failures = 0
                        state.last_metrics = metrics
                        if in_gate_window and state.baseline_metrics is None:
                            state.baseline_metrics = dict(metrics)
                        if in_gate_window:
                            for metric, value in metrics.items():
                                previous_max = state.observed_max_metrics.get(metric)
                                if previous_max is None or value > previous_max:
                                    state.observed_max_metrics[metric] = value
                        sample_record['targets'][target_id] = {'metrics': metrics}
                _write_json_line(samples_stream, sample_record)
                next_sample_at = max(
                    next_sample_at + sample_interval_seconds,
                    time.monotonic(),
                )

            now = time.monotonic()
            if workload_command and workload_completed_at is not None:
                if now >= min(deadline, workload_completed_at + cooldown_seconds):
                    break
            elif now >= deadline:
                if workload is not None and workload.poll() is None:
                    workload_timed_out = True
                    _terminate_workload(workload)
                    workload_return_code = workload.returncode
                    workload_completed_at = time.monotonic()
                break

            sleep_seconds = min(max(next_sample_at - now, 0.01), 0.25)
            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        interrupted = True
    finally:
        if workload is not None and workload.poll() is None:
            _terminate_workload(workload)
            workload_return_code = workload.returncode
            workload_completed_at = time.monotonic()
        if previous_sigterm_handler is not None:
            signal.signal(signal.SIGTERM, previous_sigterm_handler)
        sampler_pool.shutdown(wait=True, cancel_futures=True)

    completed_at = time.monotonic()
    if workload_completed_at is not None:
        analysis_start = workload_completed_at
    else:
        analysis_start = max(
            started_at + startup_grace_seconds,
            completed_at - analysis_window_seconds,
        )
    gate = evaluate_gate(
        states,
        analysis_start_seconds=analysis_start,
        thresholds=thresholds,
    )
    failures = list(gate.failures)
    warnings = list(gate.warnings)
    if interrupted:
        failures.append('soak was interrupted')
    if workload_timed_out:
        failures.append('workload exceeded the soak duration and was terminated')
    if workload_command and workload is None:
        if workload_start_error is not None:
            failures.append(f'workload failed to start: {workload_start_error}')
        else:
            failures.append('workload did not start before the soak ended')
    if workload_return_code not in (None, 0):
        failures.append(f'workload exited with status {workload_return_code}')

    workload_result = WorkloadResult(
        executable=workload_command[0] if workload_command else None,
        argument_count=max(len(workload_command) - 1, 0) if workload_command else 0,
        started_at_seconds=(workload_started_at - started_at if workload_started_at is not None else None),
        completed_at_seconds=(workload_completed_at - started_at if workload_completed_at is not None else None),
        return_code=workload_return_code,
        timed_out=workload_timed_out,
    )
    report = {
        'schema_version': 1,
        'verdict': 'pass' if not failures else 'fail',
        'started_at': started_at_wall,
        'completed_at': _utc_now(),
        'elapsed_seconds': completed_at - started_at,
        'analysis_start_seconds': analysis_start - started_at,
        'config': {
            'duration_seconds': duration_seconds,
            'sample_interval_seconds': sample_interval_seconds,
            'startup_grace_seconds': startup_grace_seconds,
            'cooldown_seconds': cooldown_seconds,
            'analysis_window_seconds': analysis_window_seconds,
            'http_timeout_seconds': http_timeout_seconds,
            'thresholds': dataclasses.asdict(thresholds),
            'targets': [
                {
                    'name': target.name,
                    'kind': target.kind,
                    'location': target.location,
                }
                for target in targets
            ],
        },
        'workload': dataclasses.asdict(workload_result),
        'failures': list(dict.fromkeys(failures)),
        'warnings': list(dict.fromkeys(warnings)),
        'targets': gate.targets,
    }
    return report, 0 if report['verdict'] == 'pass' else 1


def _positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError('value must be a finite number greater than zero')
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError('value must be a finite number greater than or equal to zero')
    return parsed


def _ratio(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError('ratio must be between zero and one')
    return parsed


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Monitor LangBot Cloud process/cgroup resources and enforce a post-load stability gate.',
    )
    parser.add_argument('--endpoint', action='append', default=[], metavar='NAME=URL')
    parser.add_argument('--cgroup', action='append', default=[], metavar='NAME=PATH')
    parser.add_argument('--pid', action='append', default=[], metavar='NAME=PID')
    parser.add_argument('--duration', type=parse_duration, default=parse_duration('24h'))
    parser.add_argument('--sample-interval', type=parse_duration, default=parse_duration('15s'))
    parser.add_argument('--startup-grace', type=parse_duration, default=parse_duration('5m'))
    parser.add_argument('--cooldown', type=parse_duration, default=parse_duration('30m'))
    parser.add_argument('--analysis-window', type=parse_duration, default=parse_duration('30m'))
    parser.add_argument('--http-timeout', type=parse_duration, default=parse_duration('5s'))
    parser.add_argument('--max-memory-growth-mib', type=_positive_float, default=64.0)
    parser.add_argument('--max-memory-slope-mib-per-hour', type=_positive_float, default=32.0)
    parser.add_argument('--max-tail-cpu-cores', type=_positive_float, default=0.5)
    parser.add_argument('--max-throttled-period-ratio', type=_ratio, default=0.25)
    parser.add_argument('--max-transient-gauge-growth', type=_nonnegative_float, default=0.0)
    parser.add_argument(
        '--allow-rejections',
        action='store_true',
        help='Do not fail when blocking-executor capacity rejection counters increase.',
    )
    parser.add_argument(
        '--require-hard-limits',
        action='store_true',
        help='Require finite CPU, memory, swap and PID limits on every cgroup target.',
    )
    parser.add_argument(
        '--max-event-loop-lag-ms',
        type=_positive_float,
        default=1000.0,
    )
    parser.add_argument(
        '--max-event-loop-p95-lag-ms',
        type=_positive_float,
        default=250.0,
    )
    parser.add_argument(
        '--allow-missing-event-loop-metrics',
        action='store_true',
        help='Permit endpoint targets that do not expose resources.event_loop.',
    )
    parser.add_argument('--samples-file', type=Path)
    parser.add_argument('--report-file', type=Path)
    parser.add_argument(
        '--workload',
        nargs=argparse.REMAINDER,
        help='Command to start after startup grace; its completion begins the cooldown tail.',
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    try:
        targets = build_targets(
            endpoints=args.endpoint,
            cgroups=args.cgroup,
            pids=args.pid,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if not targets:
        parser.error('at least one --endpoint, --cgroup or --pid target is required')
    if len(targets) > MAX_TARGETS:
        parser.error(f'at most {MAX_TARGETS} targets may be monitored')
    if args.startup_grace >= args.duration:
        parser.error('--startup-grace must be shorter than --duration')
    if args.sample_interval >= args.duration:
        parser.error('--sample-interval must be shorter than --duration')
    workload_command = tuple(args.workload or ())
    if args.workload is not None and not workload_command:
        parser.error('--workload requires a command')
    thresholds = Thresholds(
        max_memory_growth_bytes=int(args.max_memory_growth_mib * BYTES_PER_MIB),
        max_memory_slope_bytes_per_hour=args.max_memory_slope_mib_per_hour * BYTES_PER_MIB,
        max_tail_cpu_cores=args.max_tail_cpu_cores,
        max_throttled_period_ratio=args.max_throttled_period_ratio,
        allow_rejections=args.allow_rejections,
        max_transient_gauge_growth=args.max_transient_gauge_growth,
        require_hard_limits=args.require_hard_limits,
        max_event_loop_lag_ms=args.max_event_loop_lag_ms,
        max_event_loop_p95_lag_ms=args.max_event_loop_p95_lag_ms,
        require_event_loop_metrics=not args.allow_missing_event_loop_metrics,
    )
    samples_stream = _open_output(args.samples_file)
    try:
        report, exit_code = run_soak(
            targets=targets,
            duration_seconds=args.duration,
            sample_interval_seconds=args.sample_interval,
            startup_grace_seconds=args.startup_grace,
            cooldown_seconds=args.cooldown,
            analysis_window_seconds=args.analysis_window,
            http_timeout_seconds=args.http_timeout,
            thresholds=thresholds,
            workload_command=workload_command or None,
            samples_stream=samples_stream,
        )
    finally:
        if samples_stream is not None:
            samples_stream.close()
    rendered_report = json.dumps(report, indent=2, sort_keys=True)
    if args.report_file is not None:
        args.report_file.parent.mkdir(parents=True, exist_ok=True)
        args.report_file.write_text(rendered_report + '\n', encoding='utf-8')
    print(rendered_report)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
