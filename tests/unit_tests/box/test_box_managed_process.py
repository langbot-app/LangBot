from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import Mock

import pytest

from langbot.pkg.box.backend import BaseSandboxBackend
from langbot.pkg.box.models import BoxManagedProcessSpec, BoxManagedProcessStatus, BoxSessionInfo, BoxSpec
from langbot.pkg.box.runtime import BoxRuntime

_UTC = dt.timezone.utc


class FakeManagedProcessBackend(BaseSandboxBackend):
    name = 'fake-managed'

    def __init__(self, logger: Mock):
        super().__init__(logger)

    async def is_available(self) -> bool:
        return True

    async def start_session(self, spec: BoxSpec) -> BoxSessionInfo:
        now = dt.datetime.now(_UTC)
        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name=self.name,
            backend_session_id=f'backend-{spec.session_id}',
            image=spec.image,
            network=spec.network,
            host_path=spec.host_path,
            host_path_mode=spec.host_path_mode,
            cpus=spec.cpus,
            memory_mb=spec.memory_mb,
            pids_limit=spec.pids_limit,
            read_only_rootfs=spec.read_only_rootfs,
            created_at=now,
            last_used_at=now,
        )

    async def exec(self, session: BoxSessionInfo, spec: BoxSpec):
        raise NotImplementedError

    async def stop_session(self, session: BoxSessionInfo):
        return None

    async def start_managed_process(self, session: BoxSessionInfo, spec: BoxManagedProcessSpec) -> asyncio.subprocess.Process:
        return await asyncio.create_subprocess_exec(
            'sh',
            '-lc',
            'cat',
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )


@pytest.mark.asyncio
async def test_runtime_start_managed_process_tracks_status():
    logger = Mock()
    runtime = BoxRuntime(logger=logger, backends=[FakeManagedProcessBackend(logger)], session_ttl_sec=300)
    await runtime.initialize()

    session_spec = BoxSpec.model_validate({'cmd': 'echo bootstrap', 'session_id': 'mcp-session'})
    await runtime.create_session(session_spec)

    process_info = await runtime.start_managed_process(
        'mcp-session',
        BoxManagedProcessSpec(command='python', args=['-m', 'demo'], cwd='/workspace'),
    )

    assert process_info['session_id'] == 'mcp-session'
    assert process_info['status'] == BoxManagedProcessStatus.RUNNING.value
    assert process_info['command'] == 'python'
    assert process_info['args'] == ['-m', 'demo']

    queried = runtime.get_managed_process('mcp-session')
    assert queried['status'] == BoxManagedProcessStatus.RUNNING.value

    await runtime.shutdown()


@pytest.mark.asyncio
async def test_runtime_does_not_reap_session_with_running_managed_process():
    logger = Mock()
    runtime = BoxRuntime(logger=logger, backends=[FakeManagedProcessBackend(logger)], session_ttl_sec=1)
    await runtime.initialize()

    session_spec = BoxSpec.model_validate({'cmd': 'echo bootstrap', 'session_id': 'mcp-session'})
    await runtime.create_session(session_spec)
    await runtime.start_managed_process(
        'mcp-session',
        BoxManagedProcessSpec(command='python', args=['-m', 'demo'], cwd='/workspace'),
    )

    runtime._sessions['mcp-session'].info.last_used_at = dt.datetime.now(_UTC) - dt.timedelta(seconds=120)
    await runtime._reap_expired_sessions_locked()

    assert 'mcp-session' in runtime._sessions

    await runtime.shutdown()
