from __future__ import annotations

import typing
import logging

from .. import note


@note.note_class('PrintVersion', 3)
class PrintVersion(note.LaunchNote):
    """Print Version Information"""

    async def need_show(self) -> bool:
        return True

    async def yield_note(self) -> typing.AsyncGenerator[typing.Tuple[str, int], None]:
        yield f'Current Version: {self.ap.ver_mgr.get_current_version()}', logging.INFO
