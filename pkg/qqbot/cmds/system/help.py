from ..aamgr import AbstractCommandNode, Context


@AbstractCommandNode.register(
    parent=None,
    name="help",
    description="显示自定义的帮助信息",
    usage="!help",
    aliases=[],
    privilege=1
)
class HelpCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import tips
        reply = ["[bot] "+tips.help_message + "\n请输入 !cmd 查看指令列表"]

        # 警告config.help_message过时
        import config
        if hasattr(config, "help_message"):
            reply[0] += "\n\n警告：config.py中的help_message已过时，不再生效，请使用tips.py中的help_message替代"

        return True, reply
    