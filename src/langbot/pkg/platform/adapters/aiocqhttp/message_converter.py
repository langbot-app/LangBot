from __future__ import annotations

import datetime
import typing

import aiocqhttp

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.platform import message as platform_message


FACE_NAMES = {
    '14': '微笑',
    '21': '可爱',
    '23': '傲慢',
    '24': '饥饿',
    '25': '困',
    '26': '惊恐',
    '27': '流汗',
    '28': '憨笑',
    '29': '悠闲',
    '30': '奋斗',
    '32': '疑问',
    '33': '嘘',
    '34': '晕',
    '38': '敲打',
    '39': '再见',
    '42': '爱情',
    '43': '跳跳',
    '49': '拥抱',
    '53': '蛋糕',
    '63': '玫瑰',
    '66': '爱心',
    '74': '太阳',
    '75': '月亮',
    '76': '赞',
    '78': '握手',
    '79': '胜利',
    '85': '飞吻',
    '89': '西瓜',
    '96': '冷汗',
    '97': '擦汗',
    '98': '抠鼻',
    '99': '鼓掌',
    '100': '糗大了',
    '101': '坏笑',
    '102': '左哼哼',
    '103': '右哼哼',
    '104': '哈欠',
    '106': '委屈',
    '111': '可怜',
    '120': '拳头',
    '122': '爱你',
    '123': 'NO',
    '124': 'OK',
    '129': '挥手',
    '144': '喝彩',
    '147': '棒棒糖',
    '171': '茶',
    '173': '泪奔',
    '174': '无奈',
    '175': '卖萌',
    '179': 'doge',
    '180': '惊喜',
    '182': '笑哭',
    '201': '点赞',
    '203': '托脸',
    '212': '托腮',
    '264': '捂脸',
    '271': '吃瓜',
    '285': '摸鱼',
}


class AiocqhttpMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain,
    ) -> tuple[aiocqhttp.Message, typing.Union[int, str, None], datetime.datetime | None]:
        target = aiocqhttp.Message()
        source_id: typing.Union[int, str, None] = None
        source_time: datetime.datetime | None = None

        for component in message_chain:
            if isinstance(component, platform_message.Source):
                source_id = component.id
                source_time = component.time
            elif isinstance(component, platform_message.Plain):
                target.append(aiocqhttp.MessageSegment.text(component.text))
            elif isinstance(component, platform_message.At):
                target.append(aiocqhttp.MessageSegment.at(component.target))
            elif isinstance(component, platform_message.AtAll):
                target.append(aiocqhttp.MessageSegment.at('all'))
            elif isinstance(component, platform_message.Image):
                file_arg = AiocqhttpMessageConverter._file_arg(component)
                if file_arg:
                    target.append(aiocqhttp.MessageSegment.image(file_arg))
            elif isinstance(component, platform_message.Voice):
                file_arg = AiocqhttpMessageConverter._file_arg(component)
                if file_arg:
                    target.append(aiocqhttp.MessageSegment.record(file_arg))
            elif isinstance(component, platform_message.File):
                file_arg = component.url or component.path or component.base64 or component.id
                target.append({'type': 'file', 'data': {'file': file_arg, 'name': component.name or 'file'}})
            elif isinstance(component, platform_message.Face):
                if component.face_type == 'rps':
                    target.append(aiocqhttp.MessageSegment.rps())
                elif component.face_type == 'dice':
                    target.append(aiocqhttp.MessageSegment.dice())
                else:
                    target.append(aiocqhttp.MessageSegment.face(component.face_id))
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    if node.message_chain:
                        node_message, _, _ = await AiocqhttpMessageConverter.yiri2target(node.message_chain)
                        target.extend(node_message)
            elif isinstance(component, platform_message.Quote) and component.id is not None:
                target.append(aiocqhttp.MessageSegment.reply(component.id))
            else:
                target.append(aiocqhttp.MessageSegment.text(str(component)))

        return target, source_id, source_time

    @staticmethod
    async def target2yiri(
        message: typing.Any,
        message_id: typing.Union[int, str] = -1,
        timestamp: float | None = None,
        bot: aiocqhttp.CQHttp | None = None,
    ) -> platform_message.MessageChain:
        target = aiocqhttp.Message(message)
        message_time = datetime.datetime.fromtimestamp(timestamp) if timestamp else datetime.datetime.now()
        components: list[platform_message.MessageComponent] = [
            platform_message.Source(id=message_id, time=message_time),
        ]

        for segment in target:
            if segment.type == 'text':
                components.append(platform_message.Plain(text=segment.data.get('text', '')))
            elif segment.type == 'at':
                qq = str(segment.data.get('qq', ''))
                components.append(platform_message.AtAll() if qq == 'all' else platform_message.At(target=qq))
            elif segment.type == 'image':
                if segment.data.get('emoji_package_id'):
                    components.append(
                        platform_message.Face(
                            face_id=int(segment.data.get('emoji_package_id') or 0),
                            face_name=segment.data.get('summary', ''),
                        )
                    )
                else:
                    components.append(
                        platform_message.Image(
                            image_id=str(segment.data.get('file', '')),
                            url=segment.data.get('url') or segment.data.get('file') or '',
                        )
                    )
            elif segment.type == 'record':
                components.append(
                    platform_message.Voice(
                        voice_id=str(segment.data.get('file', '')),
                        url=segment.data.get('url') or segment.data.get('file') or '',
                    )
                )
            elif segment.type == 'file':
                components.append(
                    platform_message.File(
                        id=str(segment.data.get('file_id') or segment.data.get('file') or ''),
                        name=segment.data.get('name') or segment.data.get('file') or '',
                        size=int(segment.data.get('size') or segment.data.get('file_size') or 0),
                        url=segment.data.get('url') or segment.data.get('file_url') or '',
                    )
                )
            elif segment.type == 'reply':
                quote = await AiocqhttpMessageConverter._quote_from_reply_segment(segment, bot)
                components.append(quote)
            elif segment.type == 'face':
                face_id = str(segment.data.get('id', 0))
                face_name = ''
                raw = segment.data.get('raw')
                if isinstance(raw, dict):
                    face_name = str(raw.get('faceText') or '')
                components.append(
                    platform_message.Face(
                        face_id=int(face_id or 0),
                        face_name=face_name.replace('/', '') or FACE_NAMES.get(face_id, ''),
                    )
                )
            elif segment.type == 'rps':
                components.append(
                    platform_message.Face(
                        face_type='rps',
                        face_id=int(segment.data.get('result') or 0),
                        face_name='猜拳',
                    )
                )
            elif segment.type == 'dice':
                components.append(
                    platform_message.Face(
                        face_type='dice',
                        face_id=int(segment.data.get('result') or 0),
                        face_name='骰子',
                    )
                )
            else:
                components.append(platform_message.Unknown(text=f'{segment.type}:{segment.data}'))

        return platform_message.MessageChain(components)

    @staticmethod
    def _file_arg(component: platform_message.Image | platform_message.Voice) -> str:
        if component.base64:
            _, _, payload = component.base64.partition(',')
            return f'base64://{payload or component.base64}'
        if component.url:
            return component.url
        if component.path:
            return str(component.path)
        return ''

    @staticmethod
    async def _quote_from_reply_segment(
        segment: aiocqhttp.MessageSegment,
        bot: aiocqhttp.CQHttp | None,
    ) -> platform_message.Quote:
        reply_id = segment.data.get('id')
        origin = platform_message.MessageChain([])
        sender_id = None
        group_id = None
        target_id = None
        if bot is not None and reply_id is not None:
            try:
                message_data = await bot.get_msg(message_id=int(reply_id))
                sender_id = message_data.get('sender', {}).get('user_id') or message_data.get('user_id')
                group_id = message_data.get('group_id')
                target_id = group_id or sender_id
                origin = await AiocqhttpMessageConverter.target2yiri(
                    message_data.get('message', []),
                    message_data.get('message_id', reply_id),
                    message_data.get('time'),
                    bot=None,
                )
            except Exception:
                origin = platform_message.MessageChain([])
        return platform_message.Quote(
            id=reply_id,
            group_id=group_id,
            sender_id=sender_id,
            target_id=target_id,
            origin=origin,
        )
