from __future__ import annotations

import typing
import os
import sys
import logging

from .. import note, app


@note.note_class("PrintVersion", 3)
class PrintVersion(note.LaunchNote):
    """打印版本信息
    """

    async def need_show(self) -> bool:
        return True

    async def yield_note(self) -> typing.AsyncGenerator[typing.Tuple[str, int], None]:

        yield f"当前版本：{self.ap.ver_mgr.get_current_version()}", logging.INFO
