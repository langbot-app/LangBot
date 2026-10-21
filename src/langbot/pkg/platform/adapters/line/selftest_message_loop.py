#!/usr/bin/env python
"""WO-LINE-02 自測：message.received 收發閉環純邏輯（非 SDK 依賴）。

仅测可离线验证的纯 Python 分支：
  - LineEventConverter._sdk_to_payload（dict 分支：LINE webhook JSON → 归一化事件）
  - LineEventConverter.target2yiri（消息事件 → MessageReceivedEvent）
  - LineMessageConverter.target2yiri / yiri2target（两向 MessageChain ↔ LINE payload）
  - LineAdapter._extract_reply_token
SDK 存取已封装于 _sdk_to_payload / _LINE_SDK / _sdk_*，本自測不触发（content_provider=None）。

需于 repo 环境执行（SDK 在位，PYTHONPATH 含 src/）。
"""

import asyncio
import datetime
import sys
from pathlib import Path

# 兼容 repo 执行（src/ 入 path）
_src = Path(__file__).resolve().parents[1] / 'src'
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from langbot.pkg.platform.adapters.line.adapter import LineAdapter  # noqa: E402
from langbot.pkg.platform.adapters.line.event_converter import LineEventConverter  # noqa: E402
from langbot.pkg.platform.adapters.line.message_converter import LineMessageConverter  # noqa: E402
import langbot_plugin.api.entities.builtin.platform.events as platform_events  # noqa: E402
import langbot_plugin.api.entities.builtin.platform.message as platform_message  # noqa: E402

results: list[bool] = []


def check(name: str, cond: bool) -> None:
    results.append(bool(cond))
    print(f'[{"PASS" if cond else "FAIL"}] {name}')


async def main() -> None:
    # 1) _sdk_to_payload（dict 分支）
    raw = {
        'type': 'message',
        'destination': 'U-bot',
        'events': [
            {
                'type': 'message',
                'id': 'msg-1',
                'timestamp': 1634000000000,
                'sender': {'id': 'U-user-1', 'name': 'Alice'},
                'replyToken': 'rtk-1',
                'message': {'type': 'Text', 'id': 'msg-1', 'text': 'hello'},
            },
            {
                'type': 'message',
                'id': 'msg-2',
                'timestamp': 1634000001000,
                'sender': {'id': 'U-user-1'},
                'message': {'type': 'Image', 'id': 'msg-2'},
            },
        ],
    }
    events, meta = LineEventConverter._sdk_to_payload(raw)
    check('_sdk_to_payload events 数 == 2', len(events) == 2)
    check('归一化 sender.id', events[0]['sender']['id'] == 'U-user-1')
    check('归一化 reply_token', events[0]['reply_token'] == 'rtk-1')
    check('归一化 message_id', events[0]['message_id'] == 'msg-1')
    check('meta.destination', meta['destination'] == 'U-bot')

    # 2) target2yiri 文本 -> MessageReceivedEvent
    ev = await LineEventConverter.target2yiri(events[0], '')
    check('target2yiri 产出 MessageReceivedEvent', isinstance(ev, platform_events.MessageReceivedEvent))
    if isinstance(ev, platform_events.MessageReceivedEvent):
        check('Event.type == message.received', ev.type == 'message.received')
        check('Event.sender.id == U-user-1', ev.sender.id == 'U-user-1')
        check('Event.sender.nickname == Alice', ev.sender.nickname == 'Alice')
        check('Event.chat_id == U-user-1', ev.chat_id == 'U-user-1')
        check('Event.chat_type == private', ev.chat_type == 'private')
        check('Event.message_chain 首元件为 Source', isinstance(ev.message_chain[0], platform_message.Source))
        check(
            'Event.message_chain 含 Plain（无 source）',
            any(isinstance(c, platform_message.Plain) for c in ev.message_chain),
        )

    # 3) target2yiri 图片（content_provider=None → 媒体下载抛 NotSupportedError）
    from langbot.pkg.platform.adapters.line.errors import NotSupportedError

    try:
        await LineEventConverter.target2yiri(events[1], '')
        check('Image 无 content_provider 抛 NotSupportedError', False)
    except NotSupportedError:
        check('Image 无 content_provider 抛 NotSupportedError', True)

    # 4) yiri2target（MessageChain -> LINE payload）
    chain = platform_message.MessageChain(
        [
            platform_message.Source(id='msg-1', time=datetime.datetime(2021, 10, 13, 0, 0, 0)),
            platform_message.Plain(text='hello '),
            platform_message.At(target='U-user-1'),
        ]
    )
    payload = await LineMessageConverter.yiri2target(chain)
    check('yiri2target payload 数 == 2（Plain+At）', len(payload) == 2)
    check("payload[0] text == 'hello '", payload[0] == {'type': 'text', 'text': 'hello '})
    check('payload[1] At 格式', payload[1].get('type') == 'text' and '@U-user-1' in payload[1]['text'])

    # 5) 未映射元件 -> NotSupportedError
    try:
        await LineMessageConverter.yiri2target(platform_message.MessageChain([platform_message.Forward(node_list=[])]))
        check('Forward 抛 NotSupportedError（line:forward_message）', False)
    except NotSupportedError as exc:
        check('Forward 抛 NotSupportedError（line:forward_message）', exc.api_name == 'line:forward_message')

    # 6) _extract_reply_token（归一化 dict）
    token = LineAdapter._extract_reply_token({'reply_token': 'rtk-999'})
    check('_extract_reply_token 归一化 dict', token == 'rtk-999')

    print(f'\n=== WO-LINE-02 selftest: {sum(results)}/{len(results)} 通过 ===')
    sys.exit(0 if all(results) else 1)


if __name__ == '__main__':
    asyncio.run(main())
