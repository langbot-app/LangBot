from __future__ import annotations

import io
import json
from collections import deque
from pathlib import Path

import pytest

from scripts import cloud_runtime_soak as soak


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8')


def _process_stat(pid: int, *, user_ticks: int, system_ticks: int) -> str:
    fields = [
        'S',
        '0',
        '0',
        '0',
        '0',
        '0',
        '0',
        '0',
        '0',
        '0',
        '0',
        str(user_ticks),
        str(system_ticks),
        '0',
        '0',
        '0',
        '0',
        '0',
        '0',
        '0',
    ]
    return f'{pid} (worker with spaces) ' + ' '.join(fields)


def _sample(timestamp: float, **metrics: float) -> soak.MetricSample:
    return soak.MetricSample(
        monotonic_seconds=timestamp,
        wall_time=f'sample-{timestamp}',
        metrics=metrics,
    )


def _state(
    kind: str,
    samples: list[soak.MetricSample],
    *,
    baseline: dict[str, float] | None = None,
    latest: dict[str, float] | None = None,
) -> soak.TargetState:
    return soak.TargetState(
        target=soak.Target(name='target', kind=kind, location='/target'),
        samples=deque(samples),
        baseline_metrics=baseline or dict(samples[0].metrics),
        last_metrics=latest or dict(samples[-1].metrics),
        attempted_samples=len(samples),
        successful_samples=len(samples),
    )


def _thresholds(**overrides) -> soak.Thresholds:
    values = {
        'max_memory_growth_bytes': 64 * soak.BYTES_PER_MIB,
        'max_memory_slope_bytes_per_hour': 32 * soak.BYTES_PER_MIB,
        'max_tail_cpu_cores': 0.5,
        'max_throttled_period_ratio': 0.25,
        'allow_rejections': False,
        'max_transient_gauge_growth': 0,
        'require_hard_limits': False,
        'max_event_loop_lag_ms': 1000,
        'max_event_loop_p95_lag_ms': 250,
        'require_event_loop_metrics': True,
    }
    values.update(overrides)
    return soak.Thresholds(**values)


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('1', 1),
        ('1.5s', 1.5),
        ('2m', 120),
        ('3H', 10_800),
        ('1d', 86_400),
    ],
)
def test_parse_duration(value: str, expected: float) -> None:
    assert soak.parse_duration(value) == expected


@pytest.mark.parametrize('value', ['', '0s', '-1s', 'wat'])
def test_parse_duration_rejects_invalid_values(value: str) -> None:
    with pytest.raises(Exception):
        soak.parse_duration(value)


def test_build_targets_rejects_secret_bearing_health_url() -> None:
    with pytest.raises(ValueError, match='must not contain credentials'):
        soak.build_targets(
            endpoints=['core=https://user:secret@example.test/healthz'],
            cgroups=[],
            pids=[],
        )

    with pytest.raises(ValueError, match='query parameters'):
        soak.build_targets(
            endpoints=['core=https://example.test/healthz?token=secret'],
            cgroups=[],
            pids=[],
        )


def test_read_cgroup_snapshot_reads_v2_pressure_and_limits(tmp_path: Path) -> None:
    _write(tmp_path / 'memory.current', '1048576\n')
    _write(tmp_path / 'memory.peak', '2097152\n')
    _write(tmp_path / 'memory.swap.current', '4096\n')
    _write(tmp_path / 'memory.max', '1073741824\n')
    _write(tmp_path / 'memory.swap.max', 'max\n')
    _write(tmp_path / 'pids.current', '7\n')
    _write(tmp_path / 'pids.max', '128\n')
    _write(
        tmp_path / 'cpu.stat',
        'usage_usec 1234\nnr_periods 20\nnr_throttled 2\nthrottled_usec 99\n',
    )
    _write(tmp_path / 'memory.events', 'high 1\nmax 2\noom 0\noom_kill 0\n')
    _write(tmp_path / 'pids.events', 'max 3\n')
    _write(tmp_path / 'cpu.max', '100000 100000\n')

    metrics = soak.read_cgroup_snapshot(tmp_path)

    assert metrics['memory.current_bytes'] == 1_048_576
    assert metrics['memory.max_bytes'] == 1_073_741_824
    assert 'memory.swap.max_bytes' not in metrics
    assert metrics['cpu.usage_usec'] == 1234
    assert metrics['cpu.nr_throttled'] == 2
    assert metrics['memory.events.max'] == 2
    assert metrics['pids.events.max'] == 3
    assert metrics['cpu.quota_usec'] == 100_000


def test_read_process_snapshot_aggregates_descendants(tmp_path: Path) -> None:
    for pid, rss_kib, threads, user_ticks, system_ticks in (
        (100, 1000, 2, 100, 50),
        (200, 500, 1, 20, 10),
    ):
        process_root = tmp_path / str(pid)
        _write(
            process_root / 'status',
            f'Name:\tworker\nVmRSS:\t{rss_kib} kB\nThreads:\t{threads}\n',
        )
        _write(
            process_root / 'stat',
            _process_stat(
                pid,
                user_ticks=user_ticks,
                system_ticks=system_ticks,
            ),
        )
        (process_root / 'fd').mkdir()
        (process_root / 'fd' / '0').touch()
        (process_root / 'fd' / '1').touch()
        (process_root / 'task' / str(pid)).mkdir(parents=True)
    _write(tmp_path / '100' / 'task' / '100' / 'children', '200\n')
    _write(tmp_path / '200' / 'task' / '200' / 'children', '\n')

    metrics = soak.read_process_snapshot(100, proc_root=tmp_path, clock_ticks=100)

    assert metrics == {
        'rss_bytes': 1500 * 1024,
        'cpu_seconds': 1.8,
        'threads': 3,
        'open_fds': 4,
        'processes': 2,
    }


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.status = 200
        self.headers = {'Content-Type': 'application/json'}
        self._body = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def getcode(self) -> int:
        return self.status

    def read(self, limit: int) -> bytes:
        return self._body[:limit]


def test_read_endpoint_snapshot_flattens_resource_metrics() -> None:
    def opener(_request, *, timeout: float):
        assert timeout == 2
        return _FakeResponse(
            {
                'code': 0,
                'resources': {
                    'blocking_executor': {
                        'pending': 0,
                        'global_rejected_total': 2,
                    },
                    'restart_coordinator': {
                        'active_launches': 1,
                        'circuit_open_total': 3,
                    },
                },
            }
        )

    metrics = soak.read_endpoint_snapshot(
        'http://langbot.test/healthz',
        timeout_seconds=2,
        opener=opener,
    )

    assert metrics['http.ok'] == 1
    assert metrics['body.resources.blocking_executor.pending'] == 0
    assert metrics['body.resources.blocking_executor.global_rejected_total'] == 2
    assert metrics['body.resources.restart_coordinator.active_launches'] == 1
    assert metrics['body.resources.restart_coordinator.circuit_open_total'] == 3


def test_read_endpoint_snapshot_fails_closed_on_not_ready() -> None:
    def opener(_request, *, timeout: float):
        return _FakeResponse({'ready': False})

    with pytest.raises(RuntimeError, match='not ready'):
        soak.read_endpoint_snapshot(
            'http://box.test/readyz',
            timeout_seconds=2,
            opener=opener,
        )


def test_evaluate_gate_accepts_stable_process_tail() -> None:
    state = _state(
        'process',
        [
            _sample(0, rss_bytes=100 * soak.BYTES_PER_MIB, cpu_seconds=0),
            _sample(1800, rss_bytes=101 * soak.BYTES_PER_MIB, cpu_seconds=10),
            _sample(3600, rss_bytes=100 * soak.BYTES_PER_MIB, cpu_seconds=20),
        ],
    )

    result = soak.evaluate_gate(
        [state],
        analysis_start_seconds=0,
        thresholds=_thresholds(),
    )

    assert result.passed
    assert result.targets['process:target']['cpu.average_cores'] < 0.01


def test_evaluate_gate_detects_material_memory_leak_and_idle_cpu() -> None:
    state = _state(
        'process',
        [
            _sample(0, rss_bytes=100 * soak.BYTES_PER_MIB, cpu_seconds=0),
            _sample(1800, rss_bytes=150 * soak.BYTES_PER_MIB, cpu_seconds=1800),
            _sample(3600, rss_bytes=200 * soak.BYTES_PER_MIB, cpu_seconds=3600),
        ],
    )

    result = soak.evaluate_gate(
        [state],
        analysis_start_seconds=0,
        thresholds=_thresholds(),
    )

    assert not result.passed
    assert any('grew 100.00 MiB' in failure for failure in result.failures)
    assert any('tail CPU averaged 1.000 cores' in failure for failure in result.failures)


def test_evaluate_gate_counts_oom_and_throttling_across_workload() -> None:
    baseline = {
        'memory.current_bytes': 100,
        'memory.events.high': 0,
        'memory.events.max': 0,
        'memory.events.oom': 0,
        'memory.events.oom_kill': 0,
        'pids.events.max': 0,
        'cpu.usage_usec': 0,
        'cpu.nr_periods': 0,
        'cpu.nr_throttled': 0,
    }
    latest = {
        **baseline,
        'memory.events.oom_kill': 1,
        'pids.events.max': 2,
        'cpu.usage_usec': 1_000_000,
        'cpu.nr_periods': 100,
        'cpu.nr_throttled': 30,
    }
    state = _state(
        'cgroup',
        [
            _sample(100, **{**baseline, 'cpu.usage_usec': 500_000}),
            _sample(200, **latest),
        ],
        baseline=baseline,
        latest=latest,
    )

    result = soak.evaluate_gate(
        [state],
        analysis_start_seconds=100,
        thresholds=_thresholds(max_tail_cpu_cores=100),
    )

    assert any('memory.events.oom_kill by 1' in failure for failure in result.failures)
    assert any('pids.events.max by 2' in failure for failure in result.failures)
    assert any('throttled-period ratio 0.300' in failure for failure in result.failures)


def test_evaluate_gate_can_require_all_hard_cgroup_limits() -> None:
    metrics = {
        'memory.current_bytes': 100,
        'memory.max_bytes': 1000,
        'memory.events.high': 0,
        'memory.events.max': 0,
        'memory.events.oom': 0,
        'memory.events.oom_kill': 0,
        'pids.current': 1,
        'pids.events.max': 0,
        'cpu.usage_usec': 0,
        'cpu.nr_periods': 0,
        'cpu.nr_throttled': 0,
    }
    state = _state(
        'cgroup',
        [_sample(0, **metrics), _sample(60, **metrics)],
    )

    result = soak.evaluate_gate(
        [state],
        analysis_start_seconds=0,
        thresholds=_thresholds(require_hard_limits=True),
    )

    assert any('missing hard cgroup limits: cpu, pids, swap' in failure for failure in result.failures)


def test_evaluate_gate_detects_executor_rejection_and_stuck_pending() -> None:
    prefix = 'body.resources.blocking_executor'
    state = _state(
        'endpoint',
        [
            _sample(
                0,
                **{
                    f'{prefix}.pending': 1,
                    f'{prefix}.global_rejected_total': 0,
                },
            ),
            _sample(
                60,
                **{
                    f'{prefix}.pending': 2,
                    f'{prefix}.global_rejected_total': 1,
                },
            ),
        ],
    )

    result = soak.evaluate_gate(
        [state],
        analysis_start_seconds=0,
        thresholds=_thresholds(),
    )

    assert any('global_rejected_total by 1' in failure for failure in result.failures)
    assert any('pending above zero' in failure for failure in result.failures)


def test_evaluate_gate_detects_restart_circuit_and_stuck_launch() -> None:
    prefix = 'body.resources.restart_coordinator'
    state = _state(
        'endpoint',
        [
            _sample(
                0,
                **{
                    f'{prefix}.active_launches': 1,
                    f'{prefix}.gate_waiters': 2,
                    f'{prefix}.half_open_probe_inflight': 1,
                    f'{prefix}.open_remaining_seconds': 60,
                    f'{prefix}.circuit_open_total': 0,
                },
            ),
            _sample(
                60,
                **{
                    f'{prefix}.active_launches': 1,
                    f'{prefix}.gate_waiters': 2,
                    f'{prefix}.half_open_probe_inflight': 1,
                    f'{prefix}.open_remaining_seconds': 1,
                    f'{prefix}.circuit_open_total': 1,
                },
            ),
        ],
    )

    result = soak.evaluate_gate(
        [state],
        analysis_start_seconds=0,
        thresholds=_thresholds(),
    )

    assert any('circuit_open_total by 1' in failure for failure in result.failures)
    assert any('active_launches above zero' in failure for failure in result.failures)
    assert any('gate_waiters above zero' in failure for failure in result.failures)
    assert any('half_open_probe_inflight above zero' in failure for failure in result.failures)
    assert any('open_remaining_seconds above zero' in failure for failure in result.failures)


def test_evaluate_gate_detects_stuck_mcp_projection_cleanup() -> None:
    prefix = 'body.resources.runtimes'
    state = _state(
        'endpoint',
        [
            _sample(
                0,
                **{
                    f'{prefix}.mcp_projection_retirements': 3,
                    f'{prefix}.mcp_projection_reconcile_active': 1,
                },
            ),
            _sample(
                60,
                **{
                    f'{prefix}.mcp_projection_retirements': 1,
                    f'{prefix}.mcp_projection_reconcile_active': 1,
                },
            ),
        ],
    )

    result = soak.evaluate_gate(
        [state],
        analysis_start_seconds=0,
        thresholds=_thresholds(),
    )

    assert any('mcp_projection_retirements above zero' in failure for failure in result.failures)
    assert any('mcp_projection_reconcile_active above zero' in failure for failure in result.failures)


def test_evaluate_gate_detects_directory_and_database_capacity_violation() -> None:
    prefix = 'body.resources'
    state = _state(
        'endpoint',
        [
            _sample(
                0,
                **{
                    f'{prefix}.directory.active_workspaces': 1000,
                    f'{prefix}.directory.max_active_workspaces': 1000,
                    f'{prefix}.database_pool.checked_out': 20,
                    f'{prefix}.database_pool.configured_capacity': 20,
                },
            ),
            _sample(
                60,
                **{
                    f'{prefix}.directory.active_workspaces': 1001,
                    f'{prefix}.directory.max_active_workspaces': 1000,
                    f'{prefix}.database_pool.checked_out': 21,
                    f'{prefix}.database_pool.configured_capacity': 20,
                },
            ),
        ],
    )

    result = soak.evaluate_gate(
        [state],
        analysis_start_seconds=0,
        thresholds=_thresholds(),
    )

    assert any('directory.active_workspaces' in failure for failure in result.failures)
    assert any('database_pool.checked_out' in failure for failure in result.failures)


def test_evaluate_gate_requires_capacity_gauges_from_named_core_endpoint() -> None:
    state = _state(
        'endpoint',
        [_sample(0, **{'http.ok': 1}), _sample(60, **{'http.ok': 1})],
    )
    state.target = soak.Target(name='core', kind='endpoint', location='/core')

    result = soak.evaluate_gate(
        [state],
        analysis_start_seconds=0,
        thresholds=_thresholds(require_event_loop_metrics=False),
    )

    assert any('required capacity gauge' in failure for failure in result.failures)


def test_evaluate_gate_detects_event_loop_stall_and_sustained_lag() -> None:
    prefix = 'body.resources.event_loop'
    samples = [
        _sample(
            0,
            **{
                f'{prefix}.running': 1,
                f'{prefix}.samples_total': 10,
                f'{prefix}.recent_max_lag_ms': 20,
                f'{prefix}.recent_p95_lag_ms': 10,
            },
        ),
        _sample(
            60,
            **{
                f'{prefix}.running': 1,
                f'{prefix}.samples_total': 70,
                f'{prefix}.recent_max_lag_ms': 1500,
                f'{prefix}.recent_p95_lag_ms': 300,
            },
        ),
    ]
    state = _state('endpoint', samples)
    state.observed_max_metrics = {
        metric: max(sample.metrics[metric] for sample in samples) for metric in samples[0].metrics
    }

    result = soak.evaluate_gate(
        [state],
        analysis_start_seconds=0,
        thresholds=_thresholds(),
    )

    assert any('event-loop lag reached 1500.00 ms' in item for item in result.failures)
    assert any('recent p95 reached 300.00 ms' in item for item in result.failures)


def test_evaluate_gate_requires_running_event_loop_monitor() -> None:
    state = _state(
        'endpoint',
        [_sample(0, **{'http.ok': 1}), _sample(60, **{'http.ok': 1})],
    )

    result = soak.evaluate_gate(
        [state],
        analysis_start_seconds=0,
        thresholds=_thresholds(),
    )

    assert any('did not expose event-loop health metrics' in item for item in result.failures)


def test_write_json_line_streams_one_record() -> None:
    stream = io.StringIO()
    soak._write_json_line(stream, {'z': 1, 'a': 2})
    assert stream.getvalue() == '{"a":2,"z":1}\n'


def test_main_requires_a_target() -> None:
    with pytest.raises(SystemExit) as exc_info:
        soak.main(['--duration', '2s', '--sample-interval', '1s', '--startup-grace', '1s'])
    assert exc_info.value.code == 2
