"""Base class for connectors that may manage a local runtime subprocess."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

from . import platform

if TYPE_CHECKING:
    from ..core import app as core_app


RuntimeTransport = Literal['stdio', 'websocket']


class ManagedRuntimeConnector:
    """Base class for connectors that either launch a local runtime or reach an external one.

    The transport rule is shared by every concrete connector (plugin, box, ...)
    and is the same on Windows, Linux and macOS:

      - an explicit runtime endpoint, Docker, or a ``--standalone-*`` flag means
        the runtime is an external process, reached over WebSocket;
      - otherwise Core launches the runtime as a child process and talks to it
        over the child's stdio pipes.
    """

    ap: 'core_app.Application'

    def __init__(self, ap: 'core_app.Application'):
        self.ap = ap
        self._lifecycle_lock = asyncio.Lock()
        self._closing = False

    @staticmethod
    def select_runtime_transport(*, standalone: bool, endpoint: str = '') -> RuntimeTransport:
        """Choose how Core connects to its runtime.

        Args:
            standalone: Whether the matching ``--standalone-*`` flag was passed.
            endpoint: An explicitly configured runtime endpoint, if any.
        """
        if endpoint or standalone or platform.get_platform() == 'docker':
            return 'websocket'
        return 'stdio'
