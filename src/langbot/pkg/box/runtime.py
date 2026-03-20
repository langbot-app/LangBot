from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import logging

from .backend import BaseSandboxBackend, DockerBackend, PodmanBackend
from .errors import BoxBackendUnavailableError, BoxSessionConflictError
from .models import BoxExecutionResult, BoxExecutionStatus, BoxSessionInfo, BoxSpec

_UTC = dt.timezone.utc


@dataclasses.dataclass(slots=True)
class _RuntimeSession:
    info: BoxSessionInfo
    lock: asyncio.Lock


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

    async def initialize(self):
        self._backend = await self._select_backend()

    async def execute(self, spec: BoxSpec) -> BoxExecutionResult:
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
        return [
            {
                'session_id': s.info.session_id,
                'backend_name': s.info.backend_name,
                'backend_session_id': s.info.backend_session_id,
                'image': s.info.image,
                'network': s.info.network.value,
                'host_path': s.info.host_path,
                'host_path_mode': s.info.host_path_mode.value,
                'cpus': s.info.cpus,
                'memory_mb': s.info.memory_mb,
                'pids_limit': s.info.pids_limit,
                'read_only_rootfs': s.info.read_only_rootfs,
                'created_at': s.info.created_at.isoformat(),
                'last_used_at': s.info.last_used_at.isoformat(),
            }
            for s in self._sessions.values()
        ]

    async def get_status(self) -> dict:
        backend_info = await self.get_backend_info()
        return {
            'backend': backend_info,
            'active_sessions': len(self._sessions),
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
        ]

        for session_id in expired_session_ids:
            await self._drop_session_locked(session_id)

    async def _drop_session_locked(self, session_id: str):
        runtime_session = self._sessions.pop(session_id, None)
        if runtime_session is None or self._backend is None:
            return

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
        if session.network != spec.network:
            raise BoxSessionConflictError(
                f'sandbox_exec session {spec.session_id} already exists with network={session.network.value}'
            )
        if session.image != spec.image:
            raise BoxSessionConflictError(
                f'sandbox_exec session {spec.session_id} already exists with image={session.image}'
            )
        if session.host_path != spec.host_path:
            raise BoxSessionConflictError(
                f'sandbox_exec session {spec.session_id} already exists with host_path={session.host_path}'
            )
        if session.host_path_mode != spec.host_path_mode:
            raise BoxSessionConflictError(
                f'sandbox_exec session {spec.session_id} already exists with host_path_mode={session.host_path_mode.value}'
            )
        if session.cpus != spec.cpus:
            raise BoxSessionConflictError(
                f'sandbox_exec session {spec.session_id} already exists with cpus={session.cpus}'
            )
        if session.memory_mb != spec.memory_mb:
            raise BoxSessionConflictError(
                f'sandbox_exec session {spec.session_id} already exists with memory_mb={session.memory_mb}'
            )
        if session.pids_limit != spec.pids_limit:
            raise BoxSessionConflictError(
                f'sandbox_exec session {spec.session_id} already exists with pids_limit={session.pids_limit}'
            )
        if session.read_only_rootfs != spec.read_only_rootfs:
            raise BoxSessionConflictError(
                f'sandbox_exec session {spec.session_id} already exists with read_only_rootfs={session.read_only_rootfs}'
            )
