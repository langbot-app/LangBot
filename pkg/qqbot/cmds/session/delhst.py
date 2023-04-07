from ..aamgr import AbstractCommandNode, Context


@AbstractCommandNode.register(
    parent=None,
    name="delhst",
    description="删除指定会话的所有历史记录",
    usage="!delhst <会话名称>\n!delhst all",
    aliases=[],
    privilege=2
)
class DelHistoryCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import pkg.openai.session
        import pkg.utils.context
        params = ctx.params
        reply = []
        if len(params) == 0:
            reply = [
            "[bot]err:请输入要删除的会话名: group_<群号> 或者 person_<QQ号>, 或使用 !delhst all 删除所有会话的历史记录"]
        else:
            if params[0] == 'all':
                return False, []
            else:
                if pkg.utils.context.get_database_manager().delete_all_history(params[0]):
                    reply = ["[bot]已删除会话 {} 的所有历史记录".format(params[0])]
                else:
                    reply = ["[bot]未找到会话 {} 的历史记录".format(params[0])]

        return True, reply
    

@AbstractCommandNode.register(
    parent=DelHistoryCommand,
    name="all",
    description="删除所有会话的全部历史记录",
    usage="!delhst all",
    aliases=[],
    privilege=2
)
class DelAllHistoryCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import pkg.utils.context
        reply = []
        pkg.utils.context.get_database_manager().delete_all_session_history()
        reply = ["[bot]已删除所有会话的历史记录"]
        return True, reply
    