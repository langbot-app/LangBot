from ..mgr import AbstractCommandNode, Context


@AbstractCommandNode.register(
    parent=None,
    name="test",
    description="测试指令",
    usage="!test",
    aliases=[],
    privilege=0
)
class TestCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        reply = []
            
        reply.append('测试指令')

        return True, reply
