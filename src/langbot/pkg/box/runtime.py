from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import logging

from .backend import BaseSandboxBackend, DockerBackend, PodmanBackend
from .errors import BoxBackendUnavailableError, BoxSessionConflictError, BoxSessionNotFoundError, BoxValidationError
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
