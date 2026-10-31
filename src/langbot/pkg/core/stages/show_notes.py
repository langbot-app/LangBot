from __future__ import annotations

from .. import stage, app, note
from .. import entities as core_entities
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

                    ap.task_mgr.create_task(
                        ayield_note(note_inst),
                        kind='launch-note',
                        name=f'launch-note-{note_cls.__name__}',
                        scopes=[core_entities.LifecycleControlScope.APPLICATION],
                        instance_uuid=ap.workspace_service.instance_uuid,
                    )
            except Exception:
                continue
