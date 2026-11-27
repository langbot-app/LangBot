from __future__ import annotations

import asyncio
import collections
import time
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Callable

from langbot_plugin.entities.io.context import PluginWorkerPolicy


async def _complete_state_transition(
    operation: Coroutine[object, object, None],
) -> None:
    """Finish one tiny coordinator mutation even if its caller is cancelled.

    A supervisor cancellation must not strand the circuit in half-open state.
    Shield the mutation and preserve the caller's cancellation after the
    coordinator lock has been released.
    """

    task = asyncio.create_task(operation)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            # A caller can be cancelled repeatedly while the mutation is
            # waiting for the state lock. Keep joining the shielded task until
            # the transition is complete; otherwise a half-open probe can be
            # stranded permanently.
            cancelled = True
    task.result()
    if cancelled:
        raise asyncio.CancelledError


@dataclass(slots=True)
class _CircuitState:
    failure_times: collections.deque[float]
    open_until: float = 0.0
    half_open_probe_inflight: bool = False


@dataclass(slots=True)
class RestartPermit:
    """One globally admitted worker restart attempt.

    The launch slot is held only until the worker finishes registration.  A
    half-open probe remains logically owned until it survives the stable
    window, fails, or is abandoned by cancellation.
    """

    _coordinator: PluginRestartCoordinator
    installation_key: str
    is_half_open_probe: bool
    _launch_slot_held: bool = True
    _probe_active: bool = False

    def __post_init__(self) -> None:
        self._probe_active = self.is_half_open_probe

    def mark_ready(self) -> None:
        """Release scarce launch admission after successful initialization."""

        if not self._launch_slot_held:
            return
        self._launch_slot_held = False
        self._coordinator._release_launch_slot()

    async def mark_stable(self) -> None:
        """Close a half-open circuit after the probe remains healthy."""

        self.mark_ready()
        if not self._probe_active:
            return
        await _complete_state_transition(
            self._coordinator._record_probe_success(self.installation_key)
        )
        self._probe_active = False

    async def record_failure(self) -> None:
        """Record an unexpected exit and release every owned admission."""

        self.mark_ready()
        was_probe = self._probe_active
        if was_probe:
            await _complete_state_transition(
                self._coordinator._record_failure(
                    self.installation_key,
                    was_probe=True,
                )
            )
        else:
            await self._coordinator._record_failure(
                self.installation_key,
                was_probe=False,
            )
        self._probe_active = False

    async def abandon(self) -> None:
        """Release admission without treating intentional cancellation as failure."""

        self.mark_ready()
        if not self._probe_active:
            await self._coordinator._discard_empty_circuit(self.installation_key)
            return
        await _complete_state_transition(
            self._coordinator._abandon_probe(self.installation_key)
        )
        self._probe_active = False


class PluginRestartCoordinator:
    """Bound concurrent launches and suppress cross-tenant restart storms."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._configured = False
        self._max_concurrent_restarts = 0
        self._failure_threshold = 0
        self._failure_window_seconds = 0.0
        self._circuit_open_seconds = 0.0
        self._launch_semaphore: asyncio.BoundedSemaphore | None = None
        self._gate_waiter_semaphore: asyncio.BoundedSemaphore | None = None
        self._state_lock = asyncio.Lock()
        self._state_changed = asyncio.Event()
        self._circuits: dict[str, _CircuitState] = {}
        self._active_launches = 0
        self._gate_waiters = 0
        self._restart_attempts_total = 0
        self._restart_failures_total = 0
        self._circuit_open_total = 0
        self._max_tracked_circuits = 0

    def configure(self, policy: PluginWorkerPolicy) -> None:
        """Apply the immutable Runtime worker policy exactly once."""

        limits = (
            policy.max_concurrent_restarts,
            policy.restart_failure_threshold,
            float(policy.restart_failure_window_seconds),
            float(policy.restart_circuit_open_seconds),
            policy.max_pending_registrations,
        )
        if self._configured:
            current = (
                self._max_concurrent_restarts,
                self._failure_threshold,
                self._failure_window_seconds,
                self._circuit_open_seconds,
                self._max_tracked_circuits,
            )
            if current != limits:
                raise ValueError("Plugin restart policy cannot be changed at runtime")
            return

        self._max_concurrent_restarts = limits[0]
        self._failure_threshold = limits[1]
        self._failure_window_seconds = limits[2]
        self._circuit_open_seconds = limits[3]
        self._launch_semaphore = asyncio.BoundedSemaphore(self._max_concurrent_restarts)
        self._gate_waiter_semaphore = asyncio.BoundedSemaphore(
            self._max_concurrent_restarts
        )
        self._max_tracked_circuits = limits[4]
        self._circuits.clear()
        self._configured = True

    def _require_launch_configuration(self) -> asyncio.BoundedSemaphore:
        if not self._configured or self._launch_semaphore is None:
            raise RuntimeError("Plugin restart coordinator is not configured")
        return self._launch_semaphore

    def _require_gate_waiter_configuration(self) -> asyncio.BoundedSemaphore:
        if not self._configured or self._gate_waiter_semaphore is None:
            raise RuntimeError("Plugin restart coordinator is not configured")
        return self._gate_waiter_semaphore

    def _reap_inactive_circuits_locked(self, now: float) -> None:
        for installation_key, circuit in list(self._circuits.items()):
            self._trim_failures(circuit, now)
            if (
                not circuit.failure_times
                and circuit.open_until <= now
                and not circuit.half_open_probe_inflight
            ):
                self._circuits.pop(installation_key, None)

    def _circuit_for(self, installation_key: str, now: float) -> _CircuitState:
        circuit = self._circuits.get(installation_key)
        if circuit is None:
            self._reap_inactive_circuits_locked(now)
            if len(self._circuits) >= self._max_tracked_circuits:
                raise RuntimeError("Plugin restart circuit capacity reached")
            circuit = _CircuitState(
                failure_times=collections.deque(maxlen=self._failure_threshold)
            )
            self._circuits[installation_key] = circuit
        return circuit

    def _trim_failures(self, circuit: _CircuitState, now: float) -> None:
        cutoff = now - self._failure_window_seconds
        while circuit.failure_times and circuit.failure_times[0] < cutoff:
            circuit.failure_times.popleft()

    def _notify_state_change_locked(self) -> None:
        previous = self._state_changed
        self._state_changed = asyncio.Event()
        previous.set()

    def _release_launch_slot(self) -> None:
        semaphore = self._require_launch_configuration()
        if self._active_launches <= 0:
            raise RuntimeError("Plugin restart launch admission underflow")
        self._active_launches -= 1
        semaphore.release()

    async def acquire(self, installation_key: str = "__global__") -> RestartPermit:
        """Wait for one launch slot and any active circuit-breaker gate."""

        launch_semaphore = self._require_launch_configuration()
        gate_waiter_semaphore = self._require_gate_waiter_configuration()
        installation_key = str(installation_key or "__global__")
        while True:
            wait_event: asyncio.Event | None = None
            wait_timeout: float | None = None
            async with self._state_lock:
                now = self._clock()
                self._reap_inactive_circuits_locked(now)
                circuit = self._circuits.get(installation_key)
                if circuit is not None:
                    self._trim_failures(circuit, now)
                    if circuit.open_until > now:
                        wait_event = self._state_changed
                        wait_timeout = circuit.open_until - now
                    elif circuit.open_until > 0 and circuit.half_open_probe_inflight:
                        wait_event = self._state_changed

            if wait_event is not None:
                await gate_waiter_semaphore.acquire()
                try:
                    self._gate_waiters += 1
                    try:
                        if wait_timeout is None:
                            await wait_event.wait()
                        else:
                            try:
                                await asyncio.wait_for(
                                    wait_event.wait(),
                                    timeout=wait_timeout,
                                )
                            except asyncio.TimeoutError:
                                pass
                    finally:
                        self._gate_waiters -= 1
                finally:
                    gate_waiter_semaphore.release()
                continue

            await launch_semaphore.acquire()
            launch_slot_owned = True
            try:
                async with self._state_lock:
                    now = self._clock()
                    self._reap_inactive_circuits_locked(now)
                    circuit = self._circuits.get(installation_key)
                    if circuit is None:
                        self._restart_attempts_total += 1
                        self._active_launches += 1
                        launch_slot_owned = False
                        return RestartPermit(
                            self,
                            installation_key=installation_key,
                            is_half_open_probe=False,
                        )
                    self._trim_failures(circuit, now)
                    if circuit.open_until > now:
                        continue
                    elif circuit.open_until > 0 and circuit.half_open_probe_inflight:
                        continue
                    elif circuit.open_until > 0:
                        circuit.half_open_probe_inflight = True
                        self._restart_attempts_total += 1
                        self._active_launches += 1
                        launch_slot_owned = False
                        return RestartPermit(
                            self,
                            installation_key=installation_key,
                            is_half_open_probe=True,
                        )
                    self._restart_attempts_total += 1
                    self._active_launches += 1
                    launch_slot_owned = False
                    return RestartPermit(
                        self,
                        installation_key=installation_key,
                        is_half_open_probe=False,
                    )
            finally:
                if launch_slot_owned:
                    launch_semaphore.release()

    async def record_unadmitted_failure(
        self,
        installation_key: str = "__global__",
    ) -> None:
        """Count a failed initial launch before restart admission begins."""

        self._require_launch_configuration()
        await self._record_failure(installation_key, was_probe=False)

    async def _discard_empty_circuit(self, installation_key: str) -> None:
        async with self._state_lock:
            circuit = self._circuits.get(installation_key)
            if (
                circuit is not None
                and not circuit.failure_times
                and circuit.open_until == 0.0
                and not circuit.half_open_probe_inflight
            ):
                self._circuits.pop(installation_key, None)

    async def _record_failure(self, installation_key: str, *, was_probe: bool) -> None:
        async with self._state_lock:
            now = self._clock()
            circuit = self._circuit_for(installation_key, now)
            self._trim_failures(circuit, now)
            circuit.failure_times.append(now)
            self._restart_failures_total += 1
            if was_probe:
                circuit.half_open_probe_inflight = False

            should_open = (
                was_probe
                or circuit.open_until > now
                or len(circuit.failure_times) >= self._failure_threshold
            )
            if should_open:
                was_open = circuit.open_until > now or circuit.half_open_probe_inflight
                circuit.open_until = max(
                    circuit.open_until,
                    now + self._circuit_open_seconds,
                )
                circuit.half_open_probe_inflight = False
                if not was_open:
                    self._circuit_open_total += 1
                self._notify_state_change_locked()

    async def _record_probe_success(self, installation_key: str) -> None:
        async with self._state_lock:
            now = self._clock()
            circuit = self._circuit_for(installation_key, now)
            if not circuit.half_open_probe_inflight:
                return
            circuit.half_open_probe_inflight = False
            circuit.open_until = 0.0
            circuit.failure_times.clear()
            self._circuits.pop(installation_key, None)
            self._notify_state_change_locked()

    async def _abandon_probe(self, installation_key: str) -> None:
        async with self._state_lock:
            now = self._clock()
            circuit = self._circuit_for(installation_key, now)
            if not circuit.half_open_probe_inflight:
                return
            circuit.half_open_probe_inflight = False
            self._notify_state_change_locked()

    def snapshot(self) -> dict[str, int | float | bool | str]:
        """Return O(1), identity-free health counters."""

        if not self._configured:
            return {"configured": False}
        now = self._clock()
        self._reap_inactive_circuits_locked(now)
        open_circuits = 0
        half_open_circuits = 0
        half_open_probe_inflight = False
        failures_in_window = 0
        open_remaining_seconds = 0.0
        for circuit in self._circuits.values():
            self._trim_failures(circuit, now)
            failures_in_window += len(circuit.failure_times)
            open_remaining_seconds = max(
                open_remaining_seconds,
                circuit.open_until - now,
                0.0,
            )
            if circuit.open_until > now:
                open_circuits += 1
            elif circuit.open_until > 0 or circuit.half_open_probe_inflight:
                half_open_circuits += 1
            half_open_probe_inflight = (
                half_open_probe_inflight or circuit.half_open_probe_inflight
            )
        if open_circuits:
            state = "open"
        elif half_open_circuits:
            state = "half_open"
        else:
            state = "closed"
        return {
            "configured": True,
            "state": state,
            "active_launches": self._active_launches,
            "gate_waiters": self._gate_waiters,
            "max_concurrent_restarts": self._max_concurrent_restarts,
            "failures_in_window": failures_in_window,
            "failure_threshold": self._failure_threshold,
            "open_remaining_seconds": open_remaining_seconds,
            "half_open_probe_inflight": half_open_probe_inflight,
            "open_circuits": open_circuits,
            "half_open_circuits": half_open_circuits,
            "tracked_circuits": len(self._circuits),
            "restart_attempts_total": self._restart_attempts_total,
            "restart_failures_total": self._restart_failures_total,
            "circuit_open_total": self._circuit_open_total,
        }
