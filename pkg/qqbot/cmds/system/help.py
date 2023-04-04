from ..mgr import AbstractCommandNode, Context


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
        import config
        reply = [(config.help_message if hasattr(config, 'help_message') else "") + "\n请输入 !cmds 查看指令列表"]

        return True, reply
    