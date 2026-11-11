#!/usr/bin/env python3
"""Exercise long-lived SDK runtime registries and verify plateau behavior."""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import gc
import hashlib
import json
import logging
import os
import resource
import sys
import tempfile
import time
import tracemalloc
from dataclasses import asdict, dataclass
from unittest import mock

from langbot_plugin.box.backend import BaseSandboxBackend
from langbot_plugin.box.models import (
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxSessionInfo,
    BoxSpec,
)
from langbot_plugin.box.runtime import BoxRuntime
from langbot_plugin.box.server import BoxGenerationFence
from langbot_plugin.entities.io.actions.enums import CommonAction
from langbot_plugin.entities.io.context import (
    ActionContext,
    InstallationBinding,
    PluginWorkerPolicy,
    RuntimeIdentity,
)
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.context import RuntimeContext
from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.runtime.io.handler import Handler


_UTC = dt.timezone.utc


@dataclass(frozen=True, slots=True)
class ProbeScale:
    rpc_calls_per_phase: int
    installations: int
    workspace_fences: int
    box_sessions_per_phase: int


SCALES = {
    "quick": ProbeScale(
        rpc_calls_per_phase=2_500,
        installations=500,
        workspace_fences=1_000,
        box_sessions_per_phase=500,
    ),
    "audit": ProbeScale(
        rpc_calls_per_phase=25_000,
        installations=5_000,
        workspace_fences=10_000,
        box_sessions_per_phase=2_500,
    ),
}


@dataclass(frozen=True, slots=True)
class ProcessSample:
    rss_bytes: int
    rss_source: str
    traced_current_bytes: int
    traced_peak_bytes: int
    asyncio_tasks: int
    open_fds: int | None


def _current_rss() -> tuple[int, str]:
    try:
        import psutil

        return psutil.Process().memory_info().rss, "psutil-current"
    except (ImportError, OSError):
        pass

    if sys.platform.startswith("linux"):
        try:
            resident_pages = int(
                open("/proc/self/statm", encoding="ascii").read().split()[1]
            )
            return resident_pages * os.sysconf("SC_PAGE_SIZE"), "procfs-current"
        except (OSError, ValueError, IndexError):
            pass

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(peak), "getrusage-peak"
    return int(peak * 1024), "getrusage-peak"


def _open_fd_count() -> int | None:
    for path in ("/proc/self/fd", "/dev/fd"):
        try:
            return len(os.listdir(path))
        except OSError:
            continue
    return None


def _sample_process() -> ProcessSample:
    gc.collect()
    rss_bytes, rss_source = _current_rss()
    traced_current, traced_peak = tracemalloc.get_traced_memory()
    return ProcessSample(
        rss_bytes=rss_bytes,
        rss_source=rss_source,
        traced_current_bytes=traced_current,
        traced_peak_bytes=traced_peak,
        asyncio_tasks=len(asyncio.all_tasks()),
        open_fds=_open_fd_count(),
    )


class _LoopbackConnection(Connection):
    def __init__(self) -> None:
        self.handler: Handler | None = None
        self.closed = False

    async def send(self, message: str) -> None:
        if self.closed:
            raise RuntimeError("Loopback connection is closed")
        payload = json.loads(message)
        response = ActionResponse.success({})
        response.seq_id = payload["seq_id"]
        assert self.handler is not None
        await self.handler._route_response(response.seq_id, response.model_dump())

    async def receive(self) -> str:
        raise RuntimeError("Loopback receive is not used by this probe")

    async def close(self) -> None:
        self.closed = True


class _FakeBackend(BaseSandboxBackend):
    name = "probe"

    def __init__(self) -> None:
        super().__init__(logging.getLogger("runtime-resource-probe"))
        self.started = 0
        self.stopped = 0

    async def is_available(self) -> bool:
        return True

    async def start_session(self, spec: BoxSpec) -> BoxSessionInfo:
        self.started += 1
        now = dt.datetime.now(_UTC)
        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name=self.name,
            backend_session_id=f"probe-{self.started}",
            image=spec.image,
            network=spec.network,
            host_path=spec.host_path,
            host_path_mode=spec.host_path_mode,
            mount_path=spec.mount_path,
            persistent=spec.persistent,
            cpus=spec.cpus,
            memory_mb=spec.memory_mb,
            pids_limit=spec.pids_limit,
            read_only_rootfs=spec.read_only_rootfs,
            workspace_quota_mb=spec.workspace_quota_mb,
            created_at=now,
            last_used_at=now,
        )

    async def exec(
        self,
        session: BoxSessionInfo,
        spec: BoxSpec,
    ) -> BoxExecutionResult:
        return BoxExecutionResult(
            session_id=session.session_id,
            backend_name=self.name,
            status=BoxExecutionStatus.COMPLETED,
            exit_code=0,
            stdout="",
            stderr="",
            duration_ms=0,
        )

    async def stop_session(self, session: BoxSessionInfo) -> None:
        del session
        self.stopped += 1


class SDKRuntimeProbe:
    """Own the same Runtime and Box objects across two churn phases."""

    def __init__(self, scale: ProbeScale) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(
            prefix="langbot-sdk-resource-probe-"
        )
        self.loopback = _LoopbackConnection()
        self.handler = Handler(
            self.loopback,
            file_storage_dir=self._temp_dir.name,
        )
        self.loopback.handler = self.handler

        self.runtime_context = RuntimeContext()
        self.runtime_context.bind_runtime(
            RuntimeIdentity(
                instance_uuid="runtime-resource-probe",
                runtime_id="runtime-resource-probe",
            ),
            PluginWorkerPolicy(
                max_cpus=1.0,
                max_memory_mb=512,
                max_pids=128,
                max_open_files=256,
                max_file_size_mb=64,
                max_workers=16,
                max_total_cpus=16.0,
                max_total_memory_mb=8_192,
                max_installations=max(scale.installations, 16),
                require_hard_limits=False,
            ),
            "shared",
        )
        self.generation_fence = BoxGenerationFence(max_records=scale.workspace_fences)
        self.backend = _FakeBackend()
        with mock.patch.dict(os.environ, {"LANGBOT_BOX_CONFIG": ""}):
            self.box_runtime = BoxRuntime(
                logging.getLogger("runtime-resource-probe"),
                backends=[self.backend],
                session_ttl_sec=0,
                max_sessions=64,
            )
        self.box_runtime._backend = self.backend

    async def run_phase(self, scale: ProbeScale, phase: int) -> None:
        await self._churn_rpc(scale.rpc_calls_per_phase)
        self._churn_installation_fences(scale.installations, phase)
        self._churn_workspace_fences(scale.workspace_fences, phase)
        await self._churn_box_sessions(
            (phase - 1) * scale.box_sessions_per_phase,
            scale.box_sessions_per_phase,
        )
        await asyncio.sleep(0)

    async def _churn_rpc(self, count: int) -> None:
        for _ in range(count):
            await self.handler.call_action(CommonAction.PING, {})

    def _churn_installation_fences(self, count: int, phase: int) -> None:
        for index in range(count):
            binding = InstallationBinding(
                instance_uuid="runtime-resource-probe",
                workspace_uuid=f"workspace-{index}",
                placement_generation=1,
                installation_uuid=f"installation-{index}",
                runtime_revision=phase,
                artifact_digest=hashlib.sha256(
                    f"artifact-{index}".encode()
                ).hexdigest(),
            )
            self.runtime_context.activate_installation_binding(binding)
            self.runtime_context.deactivate_installation_binding(binding)

    def _churn_workspace_fences(self, count: int, phase: int) -> None:
        for index in range(count):
            self.generation_fence.observe(
                ActionContext(
                    instance_uuid="runtime-resource-probe",
                    workspace_uuid=f"workspace-{index}",
                    placement_generation=phase,
                )
            )

    async def _churn_box_sessions(self, start: int, count: int) -> None:
        for index in range(start, start + count):
            session_id = f"session-{index}"
            context = ActionContext(
                instance_uuid="runtime-resource-probe",
                workspace_uuid=f"box-workspace-{index}",
                placement_generation=1,
            )
            await self.box_runtime.create_session(
                BoxSpec(
                    session_id=session_id,
                    cmd="",
                    read_only_rootfs=False,
                ),
                action_context=context,
            )
            assert len(self.box_runtime.get_sessions_for_workspace(context)) == 1
            await self.box_runtime.delete_session(session_id)

    def retained_state(self) -> dict[str, int]:
        return {
            "rpc_waiters": len(self.handler.resp_waiters),
            "rpc_stream_queues": len(self.handler.resp_queues),
            "rpc_action_tasks": len(self.handler._action_tasks),
            "active_installation_bindings": len(
                self.runtime_context._installation_bindings
            ),
            "installation_watermarks": len(
                self.runtime_context._installation_watermarks
            ),
            "workspace_generation_records": len(self.generation_fence._current),
            "workspace_generation_events": len(self.generation_fence._stale_events),
            "workspace_generation_tasks": len(self.generation_fence._active_tasks),
            "workspace_generation_task_indexes": len(
                self.generation_fence._active_task_keys_by_workspace
            ),
            "box_sessions": len(self.box_runtime._sessions),
            "box_workspace_indexes": len(self.box_runtime._session_ids_by_workspace),
            "box_expirable_session_indexes": len(
                self.box_runtime._expirable_session_ids
            ),
            "box_managed_process_indexes": len(
                self.box_runtime._managed_process_session_ids
            ),
            "box_creating_tasks": len(self.box_runtime._creating_session_tasks),
            "box_closing_tasks": len(self.box_runtime._closing_session_tasks),
            "box_background_tasks": len(self.box_runtime._background_tasks),
            "box_session_locks": len(self.box_runtime._session_operation_locks),
        }

    def assert_bounded(self, scale: ProbeScale) -> None:
        state = self.retained_state()
        expected_maximums = {
            "rpc_waiters": 0,
            "rpc_stream_queues": 0,
            "rpc_action_tasks": 0,
            "active_installation_bindings": 0,
            "installation_watermarks": scale.installations,
            "workspace_generation_records": scale.workspace_fences,
            "workspace_generation_events": 0,
            "workspace_generation_tasks": 0,
            "workspace_generation_task_indexes": 0,
            "box_sessions": 0,
            "box_workspace_indexes": 0,
            "box_expirable_session_indexes": 0,
            "box_managed_process_indexes": 0,
            "box_creating_tasks": 0,
            "box_closing_tasks": 0,
            "box_background_tasks": 0,
            "box_session_locks": 1,
        }
        violations = {
            key: (state[key], maximum)
            for key, maximum in expected_maximums.items()
            if state[key] > maximum
        }
        if violations:
            raise AssertionError(f"SDK retained-state limits failed: {violations}")

    async def close(self) -> None:
        await self.box_runtime.shutdown()
        await self.handler.close()
        self._temp_dir.cleanup()


async def _run(args: argparse.Namespace) -> dict:
    scale = SCALES[args.scale]
    tracemalloc.start()
    started_at = time.monotonic()
    probe = SDKRuntimeProbe(scale)
    try:
        baseline = _sample_process()
        await probe.run_phase(scale, 1)
        probe.assert_bounded(scale)
        phase_one = _sample_process()
        state_one = probe.retained_state()

        await probe.run_phase(scale, 2)
        probe.assert_bounded(scale)
        phase_two = _sample_process()
        state_two = probe.retained_state()

        if state_two != state_one:
            raise AssertionError(
                f"SDK retained state did not plateau: phase_one={state_one}, "
                f"phase_two={state_two}"
            )
        traced_growth = phase_two.traced_current_bytes - phase_one.traced_current_bytes
        rss_growth = phase_two.rss_bytes - phase_one.rss_bytes
        max_traced_growth = int(args.max_traced_growth_mib * 1024 * 1024)
        max_rss_growth = int(args.max_rss_growth_mib * 1024 * 1024)
        if traced_growth > max_traced_growth:
            raise AssertionError(
                f"Second-phase traced memory grew by {traced_growth} bytes "
                f"(limit {max_traced_growth})"
            )
        if rss_growth > max_rss_growth:
            raise AssertionError(
                f"Second-phase RSS grew by {rss_growth} bytes (limit {max_rss_growth})"
            )

        return {
            "component": "langbot-plugin-sdk",
            "scale": args.scale,
            "work_per_phase": asdict(scale),
            "elapsed_seconds": round(time.monotonic() - started_at, 3),
            "samples": {
                "baseline": asdict(baseline),
                "phase_one": asdict(phase_one),
                "phase_two": asdict(phase_two),
            },
            "second_phase_growth": {
                "rss_bytes": rss_growth,
                "traced_current_bytes": traced_growth,
            },
            "retained_state": {
                "phase_one": state_one,
                "phase_two": state_two,
            },
            "passed": True,
        }
    finally:
        await probe.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", choices=tuple(SCALES), default="quick")
    parser.add_argument("--max-traced-growth-mib", type=float, default=8.0)
    parser.add_argument("--max-rss-growth-mib", type=float, default=64.0)
    parser.add_argument("--json", action="store_true", help="Print compact JSON")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = asyncio.run(_run(args))
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
