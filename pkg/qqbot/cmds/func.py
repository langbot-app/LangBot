from pkg.qqbot.cmds.model import command

import logging

from mirai import Image

import config
import pkg.openai.session

@command(
    "draw",
    "使用DALL·E模型作画",
    "!draw <图片提示语>",
    [],
    False
)
def cmd_draw(cmd: str, params: list, session_name: str,
             text_message: str, launcher_type: str, launcher_id: int,
                sender_id: int, is_admin: bool) -> list:
    """使用DALL·E模型作画"""
    reply = []
    
    if len(params) == 0:
        reply = ["[bot]err:请输入图片描述文字"]
    else:
        session = pkg.openai.session.get_session(session_name)

        res = session.draw_image(" ".join(params))

        logging.debug("draw_image result:{}".format(res))
        reply = [Image(url=res['data'][0]['url'])]
        if not (hasattr(config, 'include_image_description')
                and not config.include_image_description):
            reply.append(" ".join(params))

    return reply