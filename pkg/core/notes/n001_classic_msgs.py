from __future__ import annotations

import typing

from .. import note


@note.note_class('ClassicNotes', 1)
class ClassicNotes(note.LaunchNote):
    """经典启动信息"""

    async def need_show(self) -> bool:
        return True

    async def yield_note(self) -> typing.AsyncGenerator[typing.Tuple[str, int], None]:
        yield await self.ap.ann_mgr.show_announcements()

        yield await self.ap.ver_mgr.show_version_update()
