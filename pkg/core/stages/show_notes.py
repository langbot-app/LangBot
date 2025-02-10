from __future__ import annotations

from .. import stage, app, note
from ..notes import n001_classic_msgs, n002_selection_mode_on_windows, n003_print_version


@stage.stage_class("ShowNotesStage")
class ShowNotesStage(stage.BootingStage):
    """显示启动信息阶段
    """

    async def run(self, ap: app.Application):

        # 排序
        note.preregistered_notes.sort(key=lambda x: x.number)

        for note_cls in note.preregistered_notes:
            try:
                note_inst = note_cls(ap)
                if await note_inst.need_show():
                    async for ret in note_inst.yield_note():
                        if not ret:
                            continue
                        msg, level = ret
                        if msg:
                            ap.logger.log(level, msg)
            except Exception as e:
                continue
