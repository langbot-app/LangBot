from .. import aamgr


@aamgr.AbstractCommandNode.register(
    parent=None,
    name="prompt",
    description="获取当前会话的前文",
    usage="!prompt",
    aliases=[],
    privilege=1
)
class PromptCommand(aamgr.AbstractCommandNode):
    @classmethod
    def process(cls, ctx: aamgr.Context) -> tuple[bool, list]:
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