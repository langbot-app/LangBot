"""BoxRuntimeClient abstraction for remote Box Runtime access."""

from __future__ import annotations

import abc
import logging
from typing import TYPE_CHECKING

import aiohttp

from .errors import (
    BoxBackendUnavailableError,
    BoxError,
    BoxManagedProcessConflictError,
    BoxManagedProcessNotFoundError,
    BoxRuntimeUnavailableError,
    BoxSessionConflictError,
    BoxSessionNotFoundError,
    BoxValidationError,
)
from .models import (
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxManagedProcessInfo,
    BoxManagedProcessSpec,
    BoxSpec,
    get_box_config,
)
from ..utils import platform

if TYPE_CHECKING:
    from ..core import app as core_app

_ERROR_CODE_MAP: dict[str, type[BoxError]] = {
    'validation_error': BoxValidationError,
    'session_not_found': BoxSessionNotFoundError,
    'session_conflict': BoxSessionConflictError,
    'managed_process_not_found': BoxManagedProcessNotFoundError,
    'managed_process_conflict': BoxManagedProcessConflictError,
    'backend_unavailable': BoxBackendUnavailableError,
    'runtime_unavailable': BoxRuntimeUnavailableError,
    'internal_error': BoxError,
}


def resolve_box_runtime_url(ap: 'core_app.Application') -> str:
    runtime_url = str(get_box_config(ap).get('runtime_url', '')).strip()
    if runtime_url:
        return runtime_url

    if platform.get_platform() == 'docker':
        return 'http://langbot_box_runtime:5410'
    return 'http://127.0.0.1:5410'


class BoxRuntimeClient(abc.ABC):
    """Abstract interface that BoxService uses to talk to a Box Runtime."""

    @abc.abstractmethod
    async def initialize(self) -> None: ...

    @abc.abstractmethod
    async def execute(self, spec: BoxSpec) -> BoxExecutionResult: ...

    @abc.abstractmethod
    async def shutdown(self) -> None: ...

    @abc.abstractmethod
    async def get_status(self) -> dict: ...

    @abc.abstractmethod
    async def get_sessions(self) -> list[dict]: ...

    @abc.abstractmethod
    async def get_backend_info(self) -> dict: ...

    @abc.abstractmethod
    async def delete_session(self, session_id: str) -> None: ...

    @abc.abstractmethod
    async def create_session(self, spec: BoxSpec) -> dict: ...

    @abc.abstractmethod
    async def start_managed_process(self, session_id: str, spec: BoxManagedProcessSpec) -> BoxManagedProcessInfo: ...

    @abc.abstractmethod
    async def get_managed_process(self, session_id: str) -> BoxManagedProcessInfo: ...

    @abc.abstractmethod
    async def get_session(self, session_id: str) -> dict: ...


class RemoteBoxRuntimeClient(BoxRuntimeClient):
    """HTTP client that talks to a standalone Box Runtime service."""

    def __init__(self, base_url: str, logger: logging.Logger):
        self._base_url = base_url.rstrip('/')
        self._logger = logger
        self._session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _check_response(self, resp: aiohttp.ClientResponse) -> None:
        if resp.status < 400:
            return
        try:
            body = await resp.json()
            error_info = body.get('error', {})
            code = error_info.get('code', '')
            message = error_info.get('message', '')
        except Exception:
            resp.raise_for_status()
            return
        exc_class = _ERROR_CODE_MAP.get(code, BoxError)
        raise exc_class(message)

    async def initialize(self) -> None:
        session = self._get_session()
        try:
            async with session.get(f'{self._base_url}/v1/health') as resp:
                await self._check_response(resp)
                self._logger.info(f'LangBot Box runtime connected: {self._base_url}')
        except aiohttp.ClientError as exc:
            raise BoxRuntimeUnavailableError(f'box runtime unavailable: {exc}') from exc

    async def execute(self, spec: BoxSpec) -> BoxExecutionResult:
        session = self._get_session()
        payload = spec.model_dump(mode='json')
        try:
            async with session.post(
                f'{self._base_url}/v1/sessions/{spec.session_id}/exec',
                json=payload,
            ) as resp:
                await self._check_response(resp)
                data = await resp.json()
        except aiohttp.ClientError as exc:
            raise BoxRuntimeUnavailableError(f'box runtime unavailable: {exc}') from exc
        return BoxExecutionResult(
            session_id=data['session_id'],
            backend_name=data['backend_name'],
            status=BoxExecutionStatus(data['status']),
            exit_code=data.get('exit_code'),
            stdout=data.get('stdout', ''),
            stderr=data.get('stderr', ''),
            duration_ms=data['duration_ms'],
        )

    async def shutdown(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_status(self) -> dict:
        session = self._get_session()
        try:
            async with session.get(f'{self._base_url}/v1/status') as resp:
                await self._check_response(resp)
                return await resp.json()
        except aiohttp.ClientError as exc:
            raise BoxRuntimeUnavailableError(f'box runtime unavailable: {exc}') from exc

    async def get_sessions(self) -> list[dict]:
        session = self._get_session()
        try:
            async with session.get(f'{self._base_url}/v1/sessions') as resp:
                await self._check_response(resp)
                return await resp.json()
        except aiohttp.ClientError as exc:
            raise BoxRuntimeUnavailableError(f'box runtime unavailable: {exc}') from exc

    async def get_session(self, session_id: str) -> dict:
        session = self._get_session()
        try:
            async with session.get(f'{self._base_url}/v1/sessions/{session_id}') as resp:
                await self._check_response(resp)
                return await resp.json()
        except aiohttp.ClientError as exc:
            raise BoxRuntimeUnavailableError(f'box runtime unavailable: {exc}') from exc

    async def get_backend_info(self) -> dict:
        session = self._get_session()
        try:
            async with session.get(f'{self._base_url}/v1/health') as resp:
                await self._check_response(resp)
                return await resp.json()
        except aiohttp.ClientError as exc:
            raise BoxRuntimeUnavailableError(f'box runtime unavailable: {exc}') from exc

    async def delete_session(self, session_id: str) -> None:
        session = self._get_session()
        try:
            async with session.delete(
                f'{self._base_url}/v1/sessions/{session_id}',
            ) as resp:
                await self._check_response(resp)
        except aiohttp.ClientError as exc:
            raise BoxRuntimeUnavailableError(f'box runtime unavailable: {exc}') from exc

    async def create_session(self, spec: BoxSpec) -> dict:
        session = self._get_session()
        payload = spec.model_dump(mode='json')
        try:
            async with session.post(
                f'{self._base_url}/v1/sessions/{spec.session_id}',
                json=payload,
            ) as resp:
                await self._check_response(resp)
                return await resp.json()
        except aiohttp.ClientError as exc:
            raise BoxRuntimeUnavailableError(f'box runtime unavailable: {exc}') from exc

    async def start_managed_process(self, session_id: str, spec: BoxManagedProcessSpec) -> BoxManagedProcessInfo:
        session = self._get_session()
        payload = spec.model_dump(mode='json')
        try:
            async with session.post(
                f'{self._base_url}/v1/sessions/{session_id}/managed-process',
                json=payload,
            ) as resp:
                await self._check_response(resp)
                data = await resp.json()
        except aiohttp.ClientError as exc:
            raise BoxRuntimeUnavailableError(f'box runtime unavailable: {exc}') from exc
        return BoxManagedProcessInfo.model_validate(data)

    async def get_managed_process(self, session_id: str) -> BoxManagedProcessInfo:
        session = self._get_session()
        try:
            async with session.get(
                f'{self._base_url}/v1/sessions/{session_id}/managed-process',
            ) as resp:
                await self._check_response(resp)
                data = await resp.json()
        except aiohttp.ClientError as exc:
            raise BoxRuntimeUnavailableError(f'box runtime unavailable: {exc}') from exc
        return BoxManagedProcessInfo.model_validate(data)

    def get_managed_process_websocket_url(self, session_id: str) -> str:
        if self._base_url.startswith('https://'):
            scheme = 'wss://'
            suffix = self._base_url[len('https://'):]
        elif self._base_url.startswith('http://'):
            scheme = 'ws://'
            suffix = self._base_url[len('http://'):]
        else:
            scheme = 'ws://'
            suffix = self._base_url
        return f'{scheme}{suffix}/v1/sessions/{session_id}/managed-process/ws'
