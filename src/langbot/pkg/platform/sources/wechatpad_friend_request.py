import asyncio
import xml.etree.ElementTree as ET

from langbot.libs.wechatpad_api.client import WeChatPadClient
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger


async def handle_wechatpad_friend_request(
    bot: WeChatPadClient,
    logger: abstract_platform_logger.AbstractEventLogger,
    data: dict,
) -> None:
    try:
        content = data.get('content')
        if not isinstance(content, dict) or not content.get('str'):
            raise ValueError('friend request content is empty')

        request = ET.fromstring(content['str'])
        scene = request.get('scene')
        v3 = request.get('encryptusername') or request.get('fromusername')
        v4 = request.get('ticket')
        chatroom_username = request.get('chatroomusername') or ''
        if not scene or not v3 or not v4:
            raise ValueError('friend request is missing scene, v3, or v4')

        result = await asyncio.to_thread(
            bot.accept_friend_request,
            scene=int(scene),
            v3=v3,
            v4=v4,
            chatroom_username=chatroom_username,
        )
        response_code = result.get('Code') if isinstance(result, dict) else None
        response_data = result.get('Data') if isinstance(result, dict) else None
        base_response = response_data.get('base_response') if isinstance(response_data, dict) else None
        response_ret = base_response.get('ret') if isinstance(base_response, dict) else None
        if response_code != 200 or (response_ret is not None and response_ret != 0):
            await logger.error(
                f'Failed to accept WeChatPad friend request: message_id={data.get("new_msg_id")}, '
                f'response_code={response_code}, response_ret={response_ret}'
            )
            return

        await logger.info(f'Accepted WeChatPad friend request: message_id={data.get("new_msg_id")}')
    except Exception as exc:
        await logger.error(
            f'Failed to process WeChatPad friend request: message_id={data.get("new_msg_id")}, error={exc}'
        )
