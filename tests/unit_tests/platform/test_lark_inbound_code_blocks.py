"""Lark rich-text code blocks must reach the bot as text instead of being dropped."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from langbot.pkg.platform.adapters.lark.message_converter import LarkMessageConverter
from langbot.pkg.platform.sources.lark import LarkMessageConverter as LegacyLarkMessageConverter
from langbot_plugin.api.entities.builtin.platform import message as platform_message


@pytest.fixture(params=[LegacyLarkMessageConverter, LarkMessageConverter], ids=['legacy', 'omni'])
def converter(request):
    return request.param


def post_message(content):
    return SimpleNamespace(
        message_id='post-msg',
        message_type='post',
        create_time='1714000000000',
        content=json.dumps({'title': '', 'content': content}),
        mentions=[],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'code_block',
    [
        {'tag': 'code_block', 'language': 'GO', 'text': 'func main() int64 {\n    return 0\n}'},
        {'tag': 'code_block', 'language': 'PYTHON', 'text': 'def hello():\n    print("你好")\n'},
        {'tag': 'code_block', 'text': '    indented\n\nlast line'},
    ],
    ids=['official-go-example', 'python-unicode', 'no-language'],
)
async def test_inbound_post_preserves_code_block_text(converter, code_block):
    api_client = MagicMock()

    chain = await converter.target2yiri(post_message([[code_block]]), api_client)

    assert len(chain) == 2
    assert isinstance(chain[0], platform_message.Source)
    assert chain[0].id == 'post-msg'
    assert isinstance(chain[1], platform_message.Plain)
    assert chain[1].text == code_block['text']
    assert api_client.mock_calls == []


@pytest.mark.asyncio
async def test_inbound_post_preserves_code_between_text_and_mentions(converter):
    api_client = MagicMock()
    chain = await converter.target2yiri(
        post_message(
            [
                [{'tag': 'at', 'user_id': 'ou_bot', 'user_name': 'Bot'}, {'tag': 'text', 'text': 'Explain: '}],
                [{'tag': 'code_block', 'language': 'PYTHON', 'text': 'print(1 + 2)'}],
                [{'tag': 'text', 'text': ' What is the result?'}],
            ]
        ),
        api_client,
    )

    assert [type(component) for component in chain] == [
        platform_message.Source,
        platform_message.At,
        platform_message.Plain,
        platform_message.Plain,
        platform_message.Plain,
    ]
    assert [component.text for component in chain if isinstance(component, platform_message.Plain)] == [
        'Explain: ',
        'print(1 + 2)',
        ' What is the result?',
    ]
    assert api_client.mock_calls == []
