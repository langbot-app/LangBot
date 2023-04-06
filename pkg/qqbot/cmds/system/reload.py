from ..aamgr import AbstractCommandNode, Context
import threading

@AbstractCommandNode.register(
    parent=None,
    name="reload",
    description="执行热重载",
    usage="!reload",
    aliases=[],
    privilege=2
)
class ReloadCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        reply = []

        import pkg.utils.reloader
        def reload_task():
            pkg.utils.reloader.reload_all()

        threading.Thread(target=reload_task, daemon=True).start()

        return True, reply