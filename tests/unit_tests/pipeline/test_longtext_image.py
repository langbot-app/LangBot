from unittest.mock import Mock

from langbot.pkg.pipeline.longtext.strategies.image import Text2ImageStrategy


class _WideFont:
    def getlength(self, text: str) -> int:
        return len(text) * 100


def test_image_strategy_line_split_always_consumes_input():
    strategy = Text2ImageStrategy(Mock())

    lines = strategy._split_text_lines('abc', 1, _WideFont())

    assert lines == ['a', 'b', 'c']
    assert ''.join(lines) == 'abc'
