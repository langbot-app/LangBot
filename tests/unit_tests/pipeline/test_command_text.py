from __future__ import annotations

import pytest

from langbot.pkg.pipeline.command_text import (
    command_name_from_chain,
    command_text_from_chain,
    strip_command_prefix,
)
from langbot_plugin.api.entities.builtin.platform.message import At, MessageChain, Plain, Source


def test_command_text_ignores_source_and_mention():
    chain = MessageChain(
        [
            Source(id='msg-1', time=0),
            At(target='bot-1'),
            Plain(text='!stop'),
        ]
    )

    assert command_text_from_chain(chain) == '!stop'
    assert command_name_from_chain(chain, ['!']) == 'stop'
    assert strip_command_prefix('!stop', ['!']) == 'stop'


def test_command_text_keeps_plain_text_without_source():
    chain = MessageChain([Plain(text='hello')])

    assert command_text_from_chain(chain) == 'hello'
    assert command_name_from_chain(chain, ['!']) is None


def test_command_prefix_uses_configured_prefix_length():
    assert strip_command_prefix('！list', ['!', '！']) == 'list'


@pytest.mark.parametrize('prefixes', [[], ['/']])
def test_command_name_requires_configured_prefix(prefixes):
    assert command_name_from_chain(MessageChain([Plain(text='!stop')]), prefixes) is None
