import pytest

from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain, Quote


@pytest.mark.parametrize('quote_first', [False, True])
@pytest.mark.parametrize('origin_text', [None, 'quoted content'])
def test_quote_preserves_command_text(quote_first, origin_text):
    origin = MessageChain([] if origin_text is None else [Plain(text=origin_text)])
    quote = Quote(id='1', origin=origin)
    plain = Plain(text='!help')
    chain = MessageChain([quote, plain] if quote_first else [plain, quote])

    assert str(chain) == '!help'
