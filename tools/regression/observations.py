"""Linux process-tree and HTTP observations shared by the regression tools."""

from __future__ import annotations

import contextlib
import json
import math
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

MAX_HTTP_BODY_BYTES = 1024 * 1024
MAX_FLATTENED_HTTP_METRICS = 256
MAX_PROCESS_TREE_SIZE = 4096
_DIRECT_HTTP_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def read_optional_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding='utf-8').strip()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return None


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
            children = read_optional_text(task_path / 'children')
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
    text = read_optional_text(path)
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


def _read_process_io(path: Path) -> dict[str, int]:
    """Read monotonic process I/O counters when procfs exposes them."""

    counters: dict[str, int] = {}
    text = read_optional_text(path)
    if text is None:
        return counters
    for line in text.splitlines():
        key, separator, raw = line.partition(':')
        if not separator:
            continue
        field = key.strip()
        if field not in {'read_bytes', 'write_bytes', 'syscr', 'syscw'}:
            continue
        with contextlib.suppress(ValueError):
            counters[field] = int(raw.strip())
    return counters


def _read_process_cpu_seconds(path: Path, clock_ticks: int) -> float:
    text = read_optional_text(path)
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
    io_counters = {'read_bytes': 0, 'write_bytes': 0, 'syscr': 0, 'syscw': 0}
    io_available = False
    for process_id in process_ids:
        process_root = proc_root / str(process_id)
        process_rss, process_threads = _read_process_status(process_root / 'status')
        rss_bytes += process_rss
        threads += process_threads
        open_fds += _count_open_fds(process_root / 'fd')
        cpu_seconds += _read_process_cpu_seconds(process_root / 'stat', ticks)
        process_io = _read_process_io(process_root / 'io')
        if process_io:
            io_available = True
        for key, value in process_io.items():
            io_counters[key] += value
    result = {
        'rss_bytes': float(rss_bytes),
        'cpu_seconds': cpu_seconds,
        'threads': float(threads),
        'open_fds': float(open_fds),
        'processes': float(len(process_ids)),
    }
    if io_available:
        result.update({f'io_{key}': float(value) for key, value in io_counters.items()})
    return result


def _read_numeric_file(path: Path) -> float | None:
    value = read_optional_text(path)
    if value is None or value == 'max':
        return None
    with contextlib.suppress(ValueError):
        return float(value)
    return None


def _read_cgroup_snapshot(root: Path = Path('/sys/fs/cgroup')) -> dict[str, float]:
    """Read cgroup v2 limits/throttling counters if available."""

    result: dict[str, float] = {}
    memory_current = _read_numeric_file(root / 'memory.current')
    memory_max = _read_numeric_file(root / 'memory.max')
    if memory_current is not None:
        result['memory_current_bytes'] = memory_current
    if memory_max is not None:
        result['memory_max_bytes'] = memory_max
    cpu_stat = read_optional_text(root / 'cpu.stat')
    if cpu_stat:
        for line in cpu_stat.splitlines():
            key, separator, raw = line.partition(' ')
            if separator and key in {'usage_usec', 'nr_throttled', 'throttled_usec'}:
                with contextlib.suppress(ValueError):
                    result[f'cpu_{key}'] = float(raw.strip())
    io_stat = read_optional_text(root / 'io.stat')
    if io_stat:
        read_bytes = write_bytes = 0
        for line in io_stat.splitlines():
            for token in line.split()[1:]:
                key, separator, raw = token.partition('=')
                if not separator:
                    continue
                with contextlib.suppress(ValueError):
                    if key == 'rbytes':
                        read_bytes += int(raw)
                    elif key == 'wbytes':
                        write_bytes += int(raw)
        result['io_read_bytes'] = float(read_bytes)
        result['io_write_bytes'] = float(write_bytes)
    return result


def _read_pressure(path: Path) -> dict[str, float]:
    result: dict[str, float] = {}
    text = read_optional_text(path)
    if not text:
        return result
    for line in text.splitlines():
        fields = dict(item.split('=', 1) for item in line.split()[1:] if '=' in item)
        for key in ('avg10', 'avg60', 'avg300', 'total'):
            with contextlib.suppress(ValueError, KeyError):
                result[f'{line.split()[0]}_{key}'] = float(fields[key])
    return result


def read_system_snapshot(
    *,
    proc_root: Path = Path('/proc'),
    cgroup_root: Path = Path('/sys/fs/cgroup'),
) -> dict[str, object]:
    """Collect host/cgroup memory, throttling, I/O and pressure evidence."""

    result: dict[str, object] = {'cgroup': _read_cgroup_snapshot(cgroup_root)}
    meminfo: dict[str, float] = {}
    text = read_optional_text(proc_root / 'meminfo')
    if text:
        for line in text.splitlines():
            key, separator, raw = line.partition(':')
            if separator:
                fields = raw.split()
                with contextlib.suppress(ValueError):
                    meminfo[key] = float(fields[0]) * (1024 if len(fields) > 1 and fields[1] == 'kB' else 1)
    result['memory'] = meminfo
    result['pressure'] = {name: _read_pressure(proc_root / 'pressure' / name) for name in ('cpu', 'memory', 'io')}
    return result


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
    require_ready_json: bool = False,
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
    if not 200 <= status < 300 or (require_ready_json and status != 200):
        raise RuntimeError(f'health endpoint returned HTTP {status}')

    metrics = {
        'http.status': float(status),
        'http.latency_ms': (time.monotonic() - started_at) * 1000,
        'http.ok': 1.0,
    }
    if require_ready_json or 'json' in content_type.lower() or body.lstrip().startswith((b'{', b'[')):
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError('health endpoint returned invalid JSON') from exc
        if require_ready_json and not isinstance(payload, Mapping):
            raise RuntimeError('readiness endpoint must return a JSON object')
        if isinstance(payload, Mapping):
            if 'code' in payload and payload['code'] != 0:
                raise RuntimeError(f'health endpoint reported code={payload["code"]!r}')
            if payload.get('live') is False or payload.get('ready') is False:
                raise RuntimeError('health endpoint reported not ready')
        metrics.update(_flatten_numeric_json(payload))
    return metrics
