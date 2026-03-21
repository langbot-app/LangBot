"""BoxRuntimeClient abstraction for Box Runtime access."""

from __future__ import annotations

import abc
import logging
from typing import Any, TYPE_CHECKING

from langbot_plugin.runtime.io.handler import Handler

from .actions import LangBotToBoxAction
from .errors import BoxError, BoxRuntimeUnavailableError
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


def resolve_box_ws_relay_url(ap: 'core_app.Application') -> str:
    """Derive the ws relay base URL used for managed-process attach."""
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


def _translate_action_error(exc: Exception) -> BoxError:
    """Convert an ActionCallError message back into the appropriate BoxError subclass."""
    from .errors import (
        BoxBackendUnavailableError,
        BoxManagedProcessConflictError,
        BoxManagedProcessNotFoundError,
        BoxSessionConflictError,
        BoxSessionNotFoundError,
        BoxValidationError,
    )
    msg = str(exc)
    _ERROR_PREFIX_MAP: list[tuple[str, type[BoxError]]] = [
        ('BoxValidationError:', BoxValidationError),
        ('BoxSessionNotFoundError:', BoxSessionNotFoundError),
        ('BoxSessionConflictError:', BoxSessionConflictError),
        ('BoxManagedProcessNotFoundError:', BoxManagedProcessNotFoundError),
        ('BoxManagedProcessConflictError:', BoxManagedProcessConflictError),
        ('BoxBackendUnavailableError:', BoxBackendUnavailableError),
    ]
    for prefix, cls in _ERROR_PREFIX_MAP:
        if prefix in msg:
            return cls(msg)
    return BoxError(msg)


class ActionRPCBoxClient(BoxRuntimeClient):
    """Client that talks to BoxRuntime via the action RPC protocol."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._handler: Handler | None = None

    @property
    def handler(self) -> Handler:
        if self._handler is None:
            raise BoxRuntimeUnavailableError('box runtime not connected')
        return self._handler

    def set_handler(self, handler: Handler) -> None:
        self._handler = handler

    async def _call(self, action: LangBotToBoxAction, data: dict[str, Any], timeout: float = 15.0) -> dict[str, Any]:
        try:
            return await self.handler.call_action(action, data, timeout=timeout)
        except BoxRuntimeUnavailableError:
            raise
        except Exception as exc:
            raise _translate_action_error(exc) from exc

    async def initialize(self) -> None:
        try:
            await self._call(LangBotToBoxAction.HEALTH, {})
            self._logger.info('LangBot Box runtime connected via action RPC.')
        except Exception as exc:
            raise BoxRuntimeUnavailableError(f'box runtime unavailable: {exc}') from exc

    async def execute(self, spec: BoxSpec) -> BoxExecutionResult:
        data = await self._call(LangBotToBoxAction.EXEC, spec.model_dump(mode='json'), timeout=300.0)
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
        if self._handler is not None:
            try:
                await self._call(LangBotToBoxAction.SHUTDOWN, {})
            except Exception:
                pass
            self._handler = None

    async def get_status(self) -> dict:
        return await self._call(LangBotToBoxAction.STATUS, {})

    async def get_sessions(self) -> list[dict]:
        data = await self._call(LangBotToBoxAction.GET_SESSIONS, {})
        return data['sessions']

    async def get_session(self, session_id: str) -> dict:
        return await self._call(LangBotToBoxAction.GET_SESSION, {'session_id': session_id})

    async def get_backend_info(self) -> dict:
        return await self._call(LangBotToBoxAction.GET_BACKEND_INFO, {})

    async def delete_session(self, session_id: str) -> None:
        await self._call(LangBotToBoxAction.DELETE_SESSION, {'session_id': session_id})

    async def create_session(self, spec: BoxSpec) -> dict:
        return await self._call(LangBotToBoxAction.CREATE_SESSION, spec.model_dump(mode='json'))

    async def start_managed_process(self, session_id: str, spec: BoxManagedProcessSpec) -> BoxManagedProcessInfo:
        data = await self._call(
            LangBotToBoxAction.START_MANAGED_PROCESS,
            {'session_id': session_id, 'spec': spec.model_dump(mode='json')},
        )
        return BoxManagedProcessInfo.model_validate(data)

    async def get_managed_process(self, session_id: str) -> BoxManagedProcessInfo:
        data = await self._call(LangBotToBoxAction.GET_MANAGED_PROCESS, {'session_id': session_id})
        return BoxManagedProcessInfo.model_validate(data)

    def get_managed_process_websocket_url(self, session_id: str, ws_relay_base_url: str) -> str:
        base = ws_relay_base_url
        if base.startswith('https://'):
            scheme = 'wss://'
            suffix = base[len('https://'):]
        elif base.startswith('http://'):
            scheme = 'ws://'
            suffix = base[len('http://'):]
        else:
            scheme = 'ws://'
            suffix = base
        return f'{scheme}{suffix}/v1/sessions/{session_id}/managed-process/ws'
