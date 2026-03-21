from __future__ import annotations

import asyncio
import collections
import dataclasses
import datetime as dt
import logging
import uuid

from .backend import BaseSandboxBackend, DockerBackend, PodmanBackend
from .errors import (
    BoxBackendUnavailableError,
    BoxManagedProcessConflictError,
    BoxManagedProcessNotFoundError,
    BoxSessionConflictError,
    BoxSessionNotFoundError,
    BoxValidationError,
)
from .models import (
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxManagedProcessInfo,
    BoxManagedProcessSpec,
    BoxManagedProcessStatus,
    BoxSessionInfo,
    BoxSpec,
)

_UTC = dt.timezone.utc
_MANAGED_PROCESS_STDERR_PREVIEW_LIMIT = 4000


@dataclasses.dataclass(slots=True)
class _ManagedProcess:
    spec: BoxManagedProcessSpec
    process: asyncio.subprocess.Process
    started_at: dt.datetime
    attach_lock: asyncio.Lock
    stderr_chunks: collections.deque[str]
    exit_code: int | None = None
    exited_at: dt.datetime | None = None

    @property
    def is_running(self) -> bool:
        return self.exit_code is None and self.process.returncode is None


@dataclasses.dataclass(slots=True)
class _RuntimeSession:
    info: BoxSessionInfo
    lock: asyncio.Lock
    managed_process: _ManagedProcess | None = None


class BoxRuntime:
    def __init__(
        self,
        logger: logging.Logger,
        backends: list[BaseSandboxBackend] | None = None,
        session_ttl_sec: int = 300,
    ):
        self.logger = logger
        self.backends = backends or [PodmanBackend(logger), DockerBackend(logger)]
        self.session_ttl_sec = session_ttl_sec
        self._backend: BaseSandboxBackend | None = None
        self._sessions: dict[str, _RuntimeSession] = {}
        self._lock = asyncio.Lock()
        self.instance_id = uuid.uuid4().hex[:12]

    async def initialize(self):
        self._backend = await self._select_backend()
        if self._backend is not None:
            self._backend.instance_id = self.instance_id
            try:
                await self._backend.cleanup_orphaned_containers(self.instance_id)
            except Exception as exc:
                self.logger.warning(f'LangBot Box orphan container cleanup failed: {exc}')

    async def execute(self, spec: BoxSpec) -> BoxExecutionResult:
        if not spec.cmd:
            raise BoxValidationError('cmd must not be empty')
        session = await self._get_or_create_session(spec)

        async with session.lock:
            self.logger.info(
                'LangBot Box execute: '
                f'session_id={spec.session_id} '
                f'backend_session_id={session.info.backend_session_id} '
                f'backend={session.info.backend_name} '
                f'workdir={spec.workdir} '
                f'timeout_sec={spec.timeout_sec}'
            )
            result = await (await self._get_backend()).exec(session.info, spec)

        async with self._lock:
            now = dt.datetime.now(_UTC)
            if spec.session_id in self._sessions:
                self._sessions[spec.session_id].info.last_used_at = now

            if result.status == BoxExecutionStatus.TIMED_OUT:
                await self._drop_session_locked(spec.session_id)

        return result

    async def shutdown(self):
        async with self._lock:
            session_ids = list(self._sessions.keys())
            for session_id in session_ids:
                await self._drop_session_locked(session_id)

    async def create_session(self, spec: BoxSpec) -> dict:
        session = await self._get_or_create_session(spec)
        return self._session_to_dict(session.info)

    async def delete_session(self, session_id: str) -> None:
        async with self._lock:
            if session_id not in self._sessions:
                raise BoxSessionNotFoundError(f'session {session_id} not found')
            await self._drop_session_locked(session_id)

    async def start_managed_process(self, session_id: str, spec: BoxManagedProcessSpec) -> dict:
        async with self._lock:
            runtime_session = self._sessions.get(session_id)
            if runtime_session is None:
                raise BoxSessionNotFoundError(f'session {session_id} not found')

        async with runtime_session.lock:
            existing = runtime_session.managed_process
            if existing is not None and existing.is_running:
                raise BoxManagedProcessConflictError(f'session {session_id} already has a managed process')

            backend = await self._get_backend()
            process = await backend.start_managed_process(runtime_session.info, spec)
            managed_process = _ManagedProcess(
                spec=spec,
                process=process,
                started_at=dt.datetime.now(_UTC),
                attach_lock=asyncio.Lock(),
                stderr_chunks=collections.deque(),
            )
            runtime_session.managed_process = managed_process
            runtime_session.info.last_used_at = dt.datetime.now(_UTC)
            asyncio.create_task(self._drain_managed_process_stderr(runtime_session.info.session_id, managed_process))
            asyncio.create_task(self._watch_managed_process(runtime_session.info.session_id, managed_process))
            return self._managed_process_to_dict(runtime_session.info.session_id, managed_process)

    def get_managed_process(self, session_id: str) -> dict:
        runtime_session = self._sessions.get(session_id)
        if runtime_session is None:
            raise BoxSessionNotFoundError(f'session {session_id} not found')
        if runtime_session.managed_process is None:
            raise BoxManagedProcessNotFoundError(f'session {session_id} has no managed process')
        return self._managed_process_to_dict(session_id, runtime_session.managed_process)

    # ── Observability ─────────────────────────────────────────────────

    async def get_backend_info(self) -> dict:
        backend = self._backend
        if backend is None:
            return {'name': None, 'available': False}
        try:
            available = await backend.is_available()
        except Exception:
            available = False
        return {'name': backend.name, 'available': available}

    def get_sessions(self) -> list[dict]:
        return [self._session_to_dict(s.info) for s in self._sessions.values()]

    def get_session(self, session_id: str) -> dict:
        runtime_session = self._sessions.get(session_id)
        if runtime_session is None:
            raise BoxSessionNotFoundError(f'session {session_id} not found')
        result = self._session_to_dict(runtime_session.info)
        if runtime_session.managed_process is not None:
            result['managed_process'] = self._managed_process_to_dict(
                session_id, runtime_session.managed_process
            )
        return result

    async def get_status(self) -> dict:
        backend_info = await self.get_backend_info()
        return {
            'backend': backend_info,
            'active_sessions': len(self._sessions),
            'managed_processes': sum(
                1
                for runtime_session in self._sessions.values()
                if runtime_session.managed_process is not None and runtime_session.managed_process.is_running
            ),
            'session_ttl_sec': self.session_ttl_sec,
        }

    async def _get_or_create_session(self, spec: BoxSpec) -> _RuntimeSession:
        async with self._lock:
            await self._reap_expired_sessions_locked()

            existing = self._sessions.get(spec.session_id)
            if existing is not None:
                self._assert_session_compatible(existing.info, spec)
                existing.info.last_used_at = dt.datetime.now(_UTC)
                self.logger.info(
                    'LangBot Box session reused: '
                    f'session_id={spec.session_id} '
                    f'backend_session_id={existing.info.backend_session_id} '
                    f'backend={existing.info.backend_name}'
                )
                return existing

            backend = await self._get_backend()
            info = await backend.start_session(spec)
            runtime_session = _RuntimeSession(info=info, lock=asyncio.Lock())
            self._sessions[spec.session_id] = runtime_session
            self.logger.info(
                'LangBot Box session created: '
                f'session_id={spec.session_id} '
                f'backend_session_id={info.backend_session_id} '
                f'backend={info.backend_name} '
                f'image={info.image} '
                f'network={info.network.value} '
                f'host_path={info.host_path} '
                f'host_path_mode={info.host_path_mode.value}'
            )
            return runtime_session

    async def _get_backend(self) -> BaseSandboxBackend:
        if self._backend is None:
            self._backend = await self._select_backend()
        if self._backend is None:
            raise BoxBackendUnavailableError(
                'LangBot Box backend unavailable. Install and start Podman or Docker before using sandbox_exec.'
            )
        return self._backend

    async def _select_backend(self) -> BaseSandboxBackend | None:
        for backend in self.backends:
            try:
                await backend.initialize()
                if await backend.is_available():
                    self.logger.info(f'LangBot Box using backend: {backend.name}')
                    return backend
            except Exception as exc:
                self.logger.warning(f'LangBot Box backend {backend.name} probe failed: {exc}')

        self.logger.warning('LangBot Box backend unavailable: neither Podman nor Docker is ready')
        return None

    async def _reap_expired_sessions_locked(self):
        if self.session_ttl_sec <= 0:
            return

        deadline = dt.datetime.now(_UTC) - dt.timedelta(seconds=self.session_ttl_sec)
        expired_session_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.info.last_used_at < deadline
            and not (session.managed_process is not None and session.managed_process.is_running)
        ]

        for session_id in expired_session_ids:
            await self._drop_session_locked(session_id)

    async def _drop_session_locked(self, session_id: str):
        runtime_session = self._sessions.pop(session_id, None)
        if runtime_session is None or self._backend is None:
            return

        await self._terminate_managed_process(runtime_session)

        try:
            self.logger.info(
                'LangBot Box session cleanup: '
                f'session_id={session_id} '
                f'backend_session_id={runtime_session.info.backend_session_id} '
                f'backend={runtime_session.info.backend_name}'
            )
            await self._backend.stop_session(runtime_session.info)
        except Exception as exc:
            self.logger.warning(f'Failed to clean up box session {session_id}: {exc}')

    def _assert_session_compatible(self, session: BoxSessionInfo, spec: BoxSpec):
        _COMPAT_FIELDS = (
            'network', 'image', 'host_path', 'host_path_mode',
            'cpus', 'memory_mb', 'pids_limit', 'read_only_rootfs',
        )
        for field in _COMPAT_FIELDS:
            session_val = getattr(session, field)
            spec_val = getattr(spec, field)
            if session_val != spec_val:
                display = session_val.value if hasattr(session_val, 'value') else session_val
                raise BoxSessionConflictError(
                    f'sandbox_exec session {spec.session_id} already exists with {field}={display}'
                )

    async def _drain_managed_process_stderr(self, session_id: str, managed_process: _ManagedProcess) -> None:
        stream = managed_process.process.stderr
        if stream is None:
            return

        try:
            while True:
                chunk = await stream.readline()
                if not chunk:
                    break
                text = chunk.decode('utf-8', errors='replace').rstrip()
                if not text:
                    continue
                managed_process.stderr_chunks.append(text)
                preview = '\n'.join(managed_process.stderr_chunks)
                while len(preview) > _MANAGED_PROCESS_STDERR_PREVIEW_LIMIT and managed_process.stderr_chunks:
                    managed_process.stderr_chunks.popleft()
                    preview = '\n'.join(managed_process.stderr_chunks)
                self.logger.info(f'LangBot Box managed process stderr: session_id={session_id} {text}')
        except Exception as exc:
            self.logger.warning(f'Failed to drain managed process stderr for {session_id}: {exc}')

    async def _watch_managed_process(self, session_id: str, managed_process: _ManagedProcess) -> None:
        return_code = await managed_process.process.wait()
        managed_process.exit_code = return_code
        managed_process.exited_at = dt.datetime.now(_UTC)
        runtime_session = self._sessions.get(session_id)
        if runtime_session is not None:
            runtime_session.info.last_used_at = managed_process.exited_at
        self.logger.info(
            'LangBot Box managed process exited: '
            f'session_id={session_id} return_code={return_code}'
        )

    async def _terminate_managed_process(self, runtime_session: _RuntimeSession) -> None:
        managed_process = runtime_session.managed_process
        if managed_process is None or not managed_process.is_running:
            return

        process = managed_process.process
        try:
            if process.stdin is not None:
                process.stdin.close()
        except Exception:
            pass

        try:
            await asyncio.wait_for(asyncio.shield(process.wait()), timeout=5)
        except asyncio.TimeoutError:
            if process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(asyncio.shield(process.wait()), timeout=5)
            except asyncio.TimeoutError:
                if process.returncode is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                await process.wait()
        finally:
            managed_process.exit_code = process.returncode
            managed_process.exited_at = dt.datetime.now(_UTC)

    def _managed_process_to_dict(self, session_id: str, managed_process: _ManagedProcess) -> dict:
        stderr_preview = '\n'.join(managed_process.stderr_chunks)
        status = BoxManagedProcessStatus.RUNNING if managed_process.is_running else BoxManagedProcessStatus.EXITED
        return BoxManagedProcessInfo(
            session_id=session_id,
            status=status,
            command=managed_process.spec.command,
            args=managed_process.spec.args,
            cwd=managed_process.spec.cwd,
            env_keys=sorted(managed_process.spec.env.keys()),
            attached=managed_process.attach_lock.locked(),
            started_at=managed_process.started_at,
            exited_at=managed_process.exited_at,
            exit_code=managed_process.exit_code,
            stderr_preview=stderr_preview,
        ).model_dump(mode='json')

    @staticmethod
    def _session_to_dict(info: BoxSessionInfo) -> dict:
        return {
            'session_id': info.session_id,
            'backend_name': info.backend_name,
            'backend_session_id': info.backend_session_id,
            'image': info.image,
            'network': info.network.value,
            'host_path': info.host_path,
            'host_path_mode': info.host_path_mode.value,
            'cpus': info.cpus,
            'memory_mb': info.memory_mb,
            'pids_limit': info.pids_limit,
            'read_only_rootfs': info.read_only_rootfs,
            'created_at': info.created_at.isoformat(),
            'last_used_at': info.last_used_at.isoformat(),
        }
