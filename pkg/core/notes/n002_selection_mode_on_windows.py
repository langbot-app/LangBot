from __future__ import annotations

import typing
import os
import logging

from .. import note


@note.note_class('SelectionModeOnWindows', 2)
class SelectionModeOnWindows(note.LaunchNote):
    """Windows 上的选择模式提示信息"""

    async def need_show(self) -> bool:
        return os.name == 'nt'

    async def yield_note(self) -> typing.AsyncGenerator[typing.Tuple[str, int], None]:
        yield (
            """您正在使用 Windows 系统，若窗口左上角显示处于”选择“模式，程序将被暂停运行，此时请右键窗口中空白区域退出选择模式。""",
            logging.INFO,
        )
