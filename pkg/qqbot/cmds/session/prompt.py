from ..aamgr import AbstractCommandNode, Context
import datetime


@AbstractCommandNode.register(
    parent=None,
    name="prompt",
    description="获取当前会话的前文",
    usage="!prompt",
    aliases=[],
    privilege=1
)
class PromptCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import pkg.openai.session
        session_name = ctx.session_name
        params = ctx.params
        reply = []

        msgs = ""
        session: list = pkg.openai.session.get_session(session_name).prompt
        for msg in session:
            if len(params) != 0 and params[0] in ['-all', '-a']:
                msgs = msgs + "{}: {}\n\n".format(msg['role'], msg['content'])
            elif len(msg['content']) > 30:
                msgs = msgs + "[{}]: {}...\n\n".format(msg['role'], msg['content'][:30])
            else:
                msgs = msgs + "[{}]: {}\n\n".format(msg['role'], msg['content'])
        reply = ["[bot]当前对话所有内容：\n{}".format(msgs)]

        return True, reply