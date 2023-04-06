from ..aamgr import AbstractCommandNode, Context
import logging

from mirai import Image
import config


@AbstractCommandNode.register(
    parent=None,
    name="draw",
    description="使用DALL·E生成图片",
    usage="!draw <图片提示语>",
    aliases=[],
    privilege=1
)
class DrawCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import pkg.openai.session

        reply = []
        
        if len(ctx.params) == 0:
            reply = ["[bot]err: 未提供图片描述文字"]
        else:
            session = pkg.openai.session.get_session(ctx.session_name)

            res = session.draw_image(" ".join(ctx.params))

            logging.debug("draw_image result:{}".format(res))
            reply = [Image(url=res['data'][0]['url'])]
            if not (hasattr(config, 'include_image_description')
                    and not config.include_image_description):
                reply.append(" ".join(ctx.params))

        return True, reply
