from ..aamgr import AbstractCommandNode, Context


@AbstractCommandNode.register(
    parent=None,
    name="continue",
    description="继续未完成的响应",
    usage="!continue",
    aliases=[],
    privilege=1
)
class ContinueCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import pkg.openai.session
        import config
        session_name = ctx.session_name

        reply = []

        session = pkg.openai.session.get_session(session_name)

        text = session.append()

        reply = [text]

        return True, reply
