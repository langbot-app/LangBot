from types import SimpleNamespace

from langbot.pkg.telemetry.execution import ExecutionCounters
from langbot.pkg.telemetry.trace import TraceState
from langbot.pkg.utils import constants


def test_cloud_counts_are_not_sampled(monkeypatch):
    monkeypatch.setattr(constants, 'edition', 'cloud')
    counters = ExecutionCounters(SimpleNamespace(telemetry_config={'execution_trace': 'sampled'}))
    assert counters.trace_mode() == 'all'
    state = TraceState('00000001')
    counters.configure(state)
    assert state.emit_nodes is True
    assert counters._chain_emitted(state) is True


def test_community_retains_sampling(monkeypatch):
    monkeypatch.setattr(constants, 'edition', 'community')
    counters = ExecutionCounters(SimpleNamespace(telemetry_config={'execution_trace': 'sampled'}))
    assert counters.trace_mode() == 'sampled'


def test_dns_survives_saturated_executor():
    import socket
    import threading
    from langbot.pkg.utils.bounded_executor import BoundedThreadPoolExecutor

    gate = threading.Event()
    executor = BoundedThreadPoolExecutor(max_workers=1, max_pending=0)
    try:
        blocked = executor.submit(gate.wait)
        assert executor.submit(socket.getaddrinfo, '127.0.0.1', 443).result(timeout=2)
    finally:
        gate.set()
        blocked.result(timeout=2)
        executor.shutdown()
