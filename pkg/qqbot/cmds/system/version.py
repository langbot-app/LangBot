from ..aamgr import AbstractCommandNode, Context


@AbstractCommandNode.register(
    parent=None,
    name="version",
    description="查看版本信息",
    usage="!version",
    aliases=[],
    privilege=1
)
class VersionCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        reply = []
        import pkg.utils.updater
    
        reply_str = "[bot]当前版本:\n{}\n".format(pkg.utils.updater.get_current_version_info())
        try:
            if pkg.utils.updater.is_new_version_available():
                reply_str += "\n有新版本可用，请使用命令 !update 进行更新"
        except:
            pass

        reply = [reply_str]

        return True, reply