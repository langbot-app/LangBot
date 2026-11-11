from __future__ import annotations

import abc
from typing import Callable, Coroutine, Any

from langbot_plugin.runtime.io.connection import Connection


class Controller(abc.ABC):
    """The abstract base class for all controllers."""

    @abc.abstractmethod
    async def run(
        self,
        new_connection_callback: Callable[[Connection], Coroutine[Any, Any, None]],
    ) -> None:
        pass
