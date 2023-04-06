from ..aamgr import AbstractCommandNode, Context
import datetime


@AbstractCommandNode.register(
    parent=None,
    name="del",
    description="删除当前会话的历史记录",
    usage="!del <序号>\n!del all",
    aliases=[],
    privilege=1
)
class DelCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import pkg.openai.session
        session_name = ctx.session_name
        params = ctx.params
        reply = []
        if len(params) == 0:
            reply = ["[bot]参数不足, 格式: !del <序号>\n可以通过!list查看序号"]
        else:
            if params[0] == 'all':
                return False, []
            elif params[0].isdigit():
                if pkg.openai.session.get_session(session_name).delete_history(int(params[0])):
                    reply = ["[bot]已删除历史会话 #{}".format(params[0])]
                else:
                    reply = ["[bot]没有历史会话 #{}".format(params[0])]
            else:
                reply = ["[bot]参数错误, 格式: !del <序号>\n可以通过!list查看序号"]

        return True, reply


@AbstractCommandNode.register(
    parent=DelCommand,
    name="all",
    description="删除当前会话的全部历史记录",
    usage="!del all",
    aliases=[],
    privilege=1
)
class DelAllCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import pkg.openai.session
        session_name = ctx.session_name
        reply = []
        pkg.openai.session.get_session(session_name).delete_all_history()
        reply = ["[bot]已删除所有历史会话"]
        return True, reply
