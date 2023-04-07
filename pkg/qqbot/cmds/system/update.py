from ..aamgr import AbstractCommandNode, Context
import threading
import traceback


@AbstractCommandNode.register(
    parent=None,
    name="update",
    description="更新程序",
    usage="!update",
    aliases=[],
    privilege=2
)
class UpdateCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        reply = []
        import pkg.utils.updater
        import pkg.utils.reloader
        import pkg.utils.context

        def update_task():
            try:
                if pkg.utils.updater.update_all():
                    pkg.utils.reloader.reload_all(notify=False)
                    pkg.utils.context.get_qqbot_manager().notify_admin("更新完成")
                else:
                    pkg.utils.context.get_qqbot_manager().notify_admin("无新版本")
            except Exception as e0:
                traceback.print_exc()
                pkg.utils.context.get_qqbot_manager().notify_admin("更新失败:{}".format(e0))
                return

        threading.Thread(target=update_task, daemon=True).start()

        reply = ["[bot]正在更新，请耐心等待，请勿重复发起更新..."]

        return True, reply