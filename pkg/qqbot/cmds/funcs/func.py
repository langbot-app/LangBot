from ..aamgr import AbstractCommandNode, Context
import logging


@AbstractCommandNode.register(
    parent=None,
    name="func",
    description="管理内容函数",
    usage="!func",
    aliases=[],
    privilege=1
)
class FuncCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        from pkg.plugin.models import host

        reply = []

        reply_str = "当前已加载的内容函数：\n\n"

        index = 1
        for func in host.__callable_functions__:
            reply_str += "{}. {}{}:\n{}\n\n".format(index, ("(已禁用) " if not func['enabled'] else ""), func['name'], func['description'])

        reply = [reply_str]

        return True, reply
        