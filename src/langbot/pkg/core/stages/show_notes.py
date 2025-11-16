from __future__ import annotations

import asyncio

from .. import stage, app, note
from ...utils import importutil

from .. import notes

importutil.import_modules_in_pkg(notes)


@stage.stage_class('ShowNotesStage')
class ShowNotesStage(stage.BootingStage):
    """Show notes stage"""

    async def run(self, ap: app.Application):
        # Sort
        note.preregistered_notes.sort(key=lambda x: x.number)

        for note_cls in note.preregistered_notes:
            try:
                note_inst = note_cls(ap)
                if await note_inst.need_show():

                    async def ayield_note(note_inst: note.LaunchNote):
                        async for ret in note_inst.yield_note():
                            if not ret:
                                continue
                            msg, level = ret
                            if msg:
                                ap.logger.log(level, msg)

                    asyncio.create_task(ayield_note(note_inst))
            except Exception:
                continue
