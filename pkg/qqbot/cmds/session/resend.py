from ..aamgr import AbstractCommandNode, Context
import datetime


@AbstractCommandNode.register(
    parent=None,
    name="resend",
    description="重新获取上一次问题的回复",
    usage="!resend",
    aliases=[],
    privilege=1
)
class ResendCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import pkg.openai.session
        import config
        session_name = ctx.session_name
        reply = []

        session = pkg.openai.session.get_session(session_name)
        to_send = session.undo()

        mgr = pkg.utils.context.get_qqbot_manager()

        reply = pkg.qqbot.message.process_normal_message(to_send, mgr, config,
                                                        ctx.launcher_type, ctx.launcher_id,
                                                        ctx.sender_id)

        return True, reply