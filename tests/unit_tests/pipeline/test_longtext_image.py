from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot.pkg.pipeline.longtext.strategies.image import Text2ImageStrategy
from langbot.pkg.pipeline.longtext.strategies import image


class _WideFont:
    def getlength(self, text: str) -> int:
        return len(text) * 100


def test_image_strategy_line_split_always_consumes_input():
    strategy = Text2ImageStrategy(Mock())

    lines = strategy._split_text_lines('abc', 1, _WideFont())

    assert lines == ['a', 'b', 'c']
    assert ''.join(lines) == 'abc'


def test_image_strategy_numeric_boundaries_are_found_in_linear_order():
    strategy = Text2ImageStrategy(Mock())

    assert strategy.indexNumber('a12-b12-c345') == [['12', 1], ['12', 5], ['345', 9]]


def test_image_strategy_rejects_unbounded_line_count_before_allocating_canvas(monkeypatch):
    strategy = Text2ImageStrategy(Mock())
    monkeypatch.setattr(image, '_MAX_TEXT_TO_IMAGE_LINES', 2)

    with pytest.raises(ValueError, match='2 lines'):
        strategy._split_text_lines('one\ntwo\nthree', 1000, _WideFont())


@pytest.mark.asyncio
async def test_image_strategy_falls_back_to_forward_for_oversized_text(monkeypatch):
    app = Mock()
    strategy = Text2ImageStrategy(app)
    monkeypatch.setattr(image, '_MAX_TEXT_TO_IMAGE_CHARS', 4)
    query = SimpleNamespace(adapter=SimpleNamespace(bot_account_id='bot'))

    components = await strategy.process('12345', query)

    assert len(components) == 1
    assert isinstance(components[0], platform_message.Forward)
    app.logger.warning.assert_called_once()
