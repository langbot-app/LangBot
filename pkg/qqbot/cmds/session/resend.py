from .. import aamgr


@aamgr.AbstractCommandNode.register(
    parent=None,
    name="resend",
    description="重新获取上一次问题的回复",
    usage="!resend",
    aliases=[],
    privilege=1
)
class ResendCommand(aamgr.AbstractCommandNode):
    @classmethod
    def process(cls, ctx: aamgr.Context) -> tuple[bool, list]:
        from ....openai import session as openai_session
        from ....utils import context
        from ....qqbot import message

        session_name = ctx.session_name
        reply = []

        session = openai_session.get_session(session_name)
        to_send = session.undo()

        mgr = context.get_qqbot_manager()

        config = context.get_config_manager().data

        reply = message.process_normal_message(to_send, mgr, config,
                                                        ctx.launcher_type, ctx.launcher_id,
                                                        ctx.sender_id)

        return True, reply